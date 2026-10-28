"""Extract modules, classes and functions from Python source with `ast`.

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
class ModuleInfo:
    path: str  # relative to the project root, with forward slashes
    name: str  # dotted module name
    is_package: bool
    line_count: int
    docstring: str | None = None
    symbols: list[Symbol] = field(default_factory=list)


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
    return analyze_source((root / relative_path).read_bytes(), relative_path)


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
        self._visit_scope(node, symbol)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, is_async=True)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        kind = "method" if self.scopes[-1][0] == "class" else "function"
        symbol = self._add_symbol(node, kind)
        symbol.is_async = is_async
        self._visit_scope(node, symbol)

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

    def _visit_scope(self, node: ast.AST, symbol: Symbol) -> None:
        self.scopes.append((symbol.kind, symbol.qualname))
        self.generic_visit(node)
        self.scopes.pop()
