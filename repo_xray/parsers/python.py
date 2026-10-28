"""Python parser: modules, classes, functions, imports and calls with `ast`.

The analysed project is parsed, never imported or executed (see ADR-0002).
"""

import ast
from pathlib import Path

from repo_xray.model import Call, Import, SourceFile, Symbol


def module_name(relative_path: Path) -> str:
    """`pkg/sub/mod.py` -> `pkg.sub.mod`; `pkg/__init__.py` -> `pkg`."""
    parts = list(relative_path.with_suffix("").parts)
    if parts[-1] == "__init__" and len(parts) > 1:
        parts.pop()
    return ".".join(parts)


def parse(source: bytes | str, relative_path: Path) -> SourceFile:
    """Parse one module. Raises SyntaxError or ValueError on invalid source."""
    tree = ast.parse(source, filename=relative_path.as_posix())
    name = module_name(relative_path)
    is_package = relative_path.name == "__init__.py"
    info = SourceFile(
        path=relative_path.as_posix(),
        language="python",
        name=name,
        package=name if is_package else name.rpartition(".")[0],
        line_count=len(source.splitlines()),
        is_package=is_package,
        docstring=ast.get_docstring(tree),
    )
    _Collector(info).visit(tree)
    return info


class _Collector(ast.NodeVisitor):
    """Walks a module keeping a stack of enclosing scopes."""

    def __init__(self, info: SourceFile):
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
