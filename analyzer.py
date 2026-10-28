"""Extract modules, classes, functions, imports and calls from Python source with `ast`.

The analysed project is parsed, never imported or executed (see ADR-0002).
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path

from scanner import ScanResult


@dataclass
class Symbol:
    kind: str  # "class", "function" or "method"
    name: str
    qualname: str  # dotted, starting with the module name
    parent: str  # qualname of the enclosing module, class or function
    lineno: int
    end_lineno: int
    docstring: str | None
    decorators: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)  # classes only
    is_async: bool = False


@dataclass
class Import:
    module: str  # absolute dotted module; relative imports are resolved
    name: str | None  # the imported name in `from module import name`
    alias: str | None
    level: int  # number of leading dots, 0 for absolute imports
    lineno: int
    scope: str  # qualname of the scope where the import happens


@dataclass
class Call:
    caller: str  # qualname of the scope that makes the call
    callee: str  # the called expression as written, e.g. `self.repo.save`
    lineno: int


@dataclass
class ModuleInfo:
    path: str  # relative to the project root, with forward slashes
    name: str  # dotted module name
    is_package: bool
    line_count: int
    docstring: str | None = None
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    error: str | None = None  # set when the file could not be parsed


def module_name(relative_path: Path) -> str:
    """`pkg/sub/mod.py` -> `pkg.sub.mod`; `pkg/__init__.py` -> `pkg`."""
    parts = list(relative_path.with_suffix("").parts)
    if parts[-1] == "__init__" and len(parts) > 1:
        parts.pop()
    return ".".join(parts)


def analyze_source(source: str | bytes, relative_path: Path) -> ModuleInfo:
    """Analyse one module's source code."""
    tree = ast.parse(source, filename=relative_path.as_posix())
    line_count = len(source.splitlines())
    info = ModuleInfo(
        path=relative_path.as_posix(),
        name=module_name(relative_path),
        is_package=relative_path.name == "__init__.py",
        line_count=line_count,
        docstring=ast.get_docstring(tree),
    )
    _Collector(info).visit(tree)
    return info


def analyze_file(root: Path, relative_path: Path) -> ModuleInfo:
    """Analyse one file. A broken file is reported in `error` instead of
    raising, so one bad file never stops the analysis of a whole project."""
    try:
        return analyze_source((root / relative_path).read_bytes(), relative_path)
    except SyntaxError as exc:
        error = f"SyntaxError: {exc.msg} (line {exc.lineno})"
    except (ValueError, RecursionError, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    return ModuleInfo(
        path=relative_path.as_posix(),
        name=module_name(relative_path),
        is_package=relative_path.name == "__init__.py",
        line_count=0,
        error=error,
    )


def analyze_project(scan_result: ScanResult) -> list[ModuleInfo]:
    return [analyze_file(scan_result.root, path) for path in scan_result.files]


class _Collector(ast.NodeVisitor):
    """Walks a module keeping a stack of enclosing scopes."""

    def __init__(self, info: ModuleInfo):
        self.info = info
        self.scopes: list[tuple[str, str]] = [("module", info.name)]  # (kind, qualname)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        symbol = self._add_symbol(node, "class")
        symbol.bases = [ast.unparse(base) for base in node.bases]
        self._visit_scope(node, symbol, outer=[*node.decorator_list, *node.bases, *node.keywords])

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, is_async=True)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        kind = "method" if self.scopes[-1][0] == "class" else "function"
        symbol = self._add_symbol(node, kind)
        symbol.is_async = is_async
        outer = [*node.decorator_list, node.args]
        if node.returns:
            outer.append(node.returns)
        self._visit_scope(node, symbol, outer)

    def visit_Call(self, node: ast.Call) -> None:
        callee = _dotted_name(node.func)
        if callee:
            self.info.calls.append(Call(caller=self.scopes[-1][1], callee=callee, lineno=node.lineno))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._add_import(node, alias.name, None, alias.asname, level=0)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = self._absolute_module(node.module, node.level)
        for alias in node.names:
            self._add_import(node, module, alias.name, alias.asname, node.level)

    def _add_import(self, node: ast.stmt, module: str, name: str | None, alias: str | None, level: int) -> None:
        self.info.imports.append(Import(
            module=module,
            name=name,
            alias=alias,
            level=level,
            lineno=node.lineno,
            scope=self.scopes[-1][1],
        ))

    def _absolute_module(self, module: str | None, level: int) -> str:
        """Turn `from ..utils import x` into `pkg.utils` based on this module's package."""
        if level == 0:
            return module or ""
        package = self.info.name.split(".")
        if not self.info.is_package:
            package.pop()
        levels_up = level - 1
        if levels_up > len(package):
            # Points outside the analysed folder: keep it as written.
            return "." * level + (module or "")
        base = package[: len(package) - levels_up]
        if module:
            base.append(module)
        return ".".join(base)

    def _add_symbol(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> Symbol:
        parent = self.scopes[-1][1]
        symbol = Symbol(
            kind=kind,
            name=node.name,
            qualname=f"{parent}.{node.name}",
            parent=parent,
            lineno=node.lineno,
            end_lineno=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            decorators=[ast.unparse(d) for d in node.decorator_list],
        )
        self.info.symbols.append(symbol)
        return symbol

    def _visit_scope(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
                     symbol: Symbol, outer: list[ast.AST]) -> None:
        # Decorators, bases and default values run in the enclosing scope,
        # so calls inside them belong to the parent, not to this symbol.
        for child in outer:
            self.visit(child)
        self.scopes.append((symbol.kind, symbol.qualname))
        for statement in node.body:
            self.visit(statement)
        self.scopes.pop()


def _dotted_name(node: ast.expr) -> str | None:
    """`foo` -> "foo", `self.repo.save` -> "self.repo.save"; None for `get()()` and similar."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base else None
    return None
