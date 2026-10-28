"""TypeScript and JavaScript parser: classes, functions, imports, calls and HTTP requests.

Covers Angular (decorators, `inject()` and constructor injection) and
React (components declared as arrow functions).
"""

import posixpath
from pathlib import Path

import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from repo_xray.model import Call, HttpCall, Import, SourceFile, Symbol
from repo_xray.parsers.treesitter import doc_comment, end_line, line, string_value, text

_TYPESCRIPT = Parser(Language(tree_sitter_typescript.language_typescript()))
_TSX = Parser(Language(tree_sitter_typescript.language_tsx()))

TYPE_KINDS = {
    "class_declaration": "class",
    "abstract_class_declaration": "class",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
}
FUNCTION_NODES = ("function_declaration", "generator_function_declaration")
FUNCTION_VALUES = ("arrow_function", "function_expression", "function")
HTTP_VERBS = {"get", "post", "put", "patch", "delete", "head"}
HTTP_CLIENTS = {"axios", "ky", "$http", "superagent"}


def parse(source: bytes, relative_path: Path) -> SourceFile:
    suffix = relative_path.suffix.lower()
    parser = _TYPESCRIPT if suffix == ".ts" else _TSX
    root = parser.parse(source).root_node
    name = relative_path.with_suffix("").as_posix()
    info = SourceFile(
        path=relative_path.as_posix(),
        language="typescript" if suffix in (".ts", ".tsx") else "javascript",
        name=name,
        package=relative_path.parent.as_posix(),
        line_count=len(source.splitlines()),
    )
    _Collector(info).visit(root)
    return info


class _Collector:
    def __init__(self, info: SourceFile):
        self.info = info
        self.scopes: list[Symbol | None] = [None]

    @property
    def scope(self) -> str:
        current = self.scopes[-1]
        return current.qualname if current else self.info.name

    def visit(self, node: Node) -> None:
        handler = _HANDLERS.get(node.type)
        if handler:
            handler(self, node)
        else:
            self.visit_children(node)

    def visit_children(self, node: Node) -> None:
        for child in node.named_children:
            self.visit(child)

    # Declarations

    def visit_type(self, node: Node) -> None:
        symbol = self._add_symbol(node, TYPE_KINDS[node.type], text(node.child_by_field_name("name")))
        symbol.decorators = [text(d)[1:] for d in _decorators(node)]
        symbol.bases = _bases(node)
        self._visit_body(node, symbol)

    def visit_function(self, node: Node) -> None:
        symbol = self._add_symbol(node, "function", text(node.child_by_field_name("name")))
        symbol.is_async = _is_async(node)
        self._visit_body(node, symbol)

    def visit_variable(self, node: Node) -> None:
        """`const Card = () => {...}` declares a function (a React component, a hook...)."""
        value = node.child_by_field_name("value")
        name = node.child_by_field_name("name")
        if value is None or value.type not in FUNCTION_VALUES or name is None or name.type != "identifier":
            self.visit_children(node)
            return
        symbol = self._add_symbol(_declaration_root(node), "function", text(name))
        symbol.is_async = _is_async(value)
        self._visit_body(value, symbol)

    def visit_method(self, node: Node) -> None:
        name = text(node.child_by_field_name("name"))
        symbol = self._add_symbol(node, "method", name)
        symbol.decorators = [text(d)[1:] for d in _decorators(node)]
        symbol.is_async = _is_async(node)
        if name == "constructor":
            self._add_constructor_fields(node)
        self._visit_body(node, symbol)

    def visit_field(self, node: Node) -> None:
        owner = self.scopes[-1]
        name = text(node.child_by_field_name("name"))
        value = node.child_by_field_name("value")
        if value is not None and value.type in FUNCTION_VALUES:
            symbol = self._add_symbol(node, "method", name)
            symbol.is_async = _is_async(value)
            self._visit_body(value, symbol)
            return
        if owner is not None:
            field_type = _annotation_type(node.child_by_field_name("type")) or _injected_type(value)
            if field_type:
                owner.fields[name] = field_type
        self.visit_children(node)

    def _add_constructor_fields(self, node: Node) -> None:
        """`constructor(private api: OrdersApi)` declares the field `api`."""
        owner = self.scopes[-1]
        parameters = node.child_by_field_name("parameters")
        if owner is None or parameters is None:
            return
        for parameter in parameters.named_children:
            is_property = any(c.type in ("accessibility_modifier", "readonly") for c in parameter.children)
            pattern = parameter.child_by_field_name("pattern")
            field_type = _annotation_type(parameter.child_by_field_name("type"))
            if is_property and pattern is not None and field_type:
                owner.fields[text(pattern)] = field_type

    def _add_symbol(self, node: Node, kind: str, name: str) -> Symbol:
        documented = node.parent if node.parent is not None and node.parent.type == "export_statement" else node
        symbol = Symbol(
            kind=kind,
            name=name,
            qualname=f"{self.scope}.{name}",
            parent=self.scope,
            lineno=line(node),
            end_lineno=end_line(node),
            docstring=doc_comment(documented),
        )
        self.info.symbols.append(symbol)
        return symbol

    def _visit_body(self, node: Node, symbol: Symbol) -> None:
        self.scopes.append(symbol)
        body = node.child_by_field_name("body")
        if body is not None and body.type in ("statement_block", "class_body", "interface_body", "enum_body"):
            self.visit_children(body)
        elif body is not None:
            self.visit(body)  # an arrow function whose body is a single expression
        self.scopes.pop()

    # Imports and calls

    def visit_import(self, node: Node) -> None:
        source = string_value(node.child_by_field_name("source")) or ""
        module = self._resolve_module(source)
        clause = next((c for c in node.named_children if c.type == "import_clause"), None)
        imported: list[tuple[str | None, str | None]] = []
        for part in clause.named_children if clause else []:
            if part.type == "identifier":
                imported.append(("default", text(part)))
            elif part.type == "namespace_import":
                imported.append(("*", text(part.named_children[-1])))
            elif part.type == "named_imports":
                for specifier in part.named_children:
                    if specifier.type == "import_specifier":
                        alias = specifier.child_by_field_name("alias")
                        imported.append((text(specifier.child_by_field_name("name")), text(alias) or None))
        for name, alias in imported or [(None, None)]:
            self.info.imports.append(Import(
                module=module, name=name, alias=alias, level=0, lineno=line(node), scope=self.scope))

    def _resolve_module(self, source: str) -> str:
        """`../config/api-url` from `src/app/core/api` -> `src/app/core/config/api-url`."""
        if not source.startswith("."):
            return source
        return posixpath.normpath(posixpath.join(self.info.package, source))

    def visit_call(self, node: Node) -> None:
        function = node.child_by_field_name("function")
        callee = _dotted(function)
        if callee:
            self.info.calls.append(Call(caller=self.scope, callee=callee, lineno=line(node)))
            self._detect_http_call(callee, node)
        self.visit_children(node)

    def visit_new(self, node: Node) -> None:
        constructor = _dotted(node.child_by_field_name("constructor"))
        if constructor:
            self.info.calls.append(Call(caller=self.scope, callee=f"new {constructor}", lineno=line(node)))
        self.visit_children(node)

    def _detect_http_call(self, callee: str, node: Node) -> None:
        receiver, _, verb = callee.rpartition(".")
        arguments = [a for a in node.child_by_field_name("arguments").named_children if a.type != "comment"]
        if callee == "fetch":
            method = _fetch_method(arguments[1]) if len(arguments) > 1 else "GET"
        elif verb in HTTP_VERBS and _is_http_client(receiver):
            method = verb.upper()
        else:
            return
        if arguments:
            self.info.http_calls.append(HttpCall(
                method=method, url=_url_template(arguments[0]), caller=self.scope, lineno=line(node)))


_HANDLERS = {
    **{kind: _Collector.visit_type for kind in TYPE_KINDS},
    **{kind: _Collector.visit_function for kind in FUNCTION_NODES},
    "variable_declarator": _Collector.visit_variable,
    "method_definition": _Collector.visit_method,
    "public_field_definition": _Collector.visit_field,
    "import_statement": _Collector.visit_import,
    "call_expression": _Collector.visit_call,
    "new_expression": _Collector.visit_new,
}


def _declaration_root(declarator: Node) -> Node:
    """The statement that holds a declarator, so the doc comment above it is found."""
    node = declarator
    while node.parent is not None and node.parent.type in ("lexical_declaration", "variable_declaration"):
        node = node.parent
    return node


def _decorators(node: Node) -> list[Node]:
    own = [c for c in node.children if c.type == "decorator"]
    parent = node.parent
    if parent is not None and parent.type == "export_statement":
        own = [c for c in parent.children if c.type == "decorator"] + own
    if node.type == "method_definition" and parent is not None:
        # Decorators of class members are siblings placed right before the member.
        previous = node.prev_sibling
        while previous is not None and previous.type == "decorator":
            own.insert(0, previous)
            previous = previous.prev_sibling
    return own


def _bases(node: Node) -> list[str]:
    bases = []
    for child in node.named_children:
        if child.type in ("class_heritage", "extends_type_clause"):
            for clause in [child] if child.type == "extends_type_clause" else child.named_children:
                bases.extend(_simple_type(t) for t in clause.named_children)
    return [b for b in bases if b]


def _is_async(node: Node) -> bool:
    return any(c.type == "async" for c in node.children)


def _annotation_type(node: Node | None) -> str:
    if node is None:
        return ""
    inner = node.named_children[0] if node.type == "type_annotation" and node.named_children else node
    return _simple_type(inner)


def _injected_type(value: Node | None) -> str:
    """`inject(OrdersApi)` -> `OrdersApi` (Angular's function-based injection)."""
    if value is None or value.type != "call_expression" or text(value.child_by_field_name("function")) != "inject":
        return ""
    arguments = value.child_by_field_name("arguments").named_children
    return _simple_type(arguments[0]) if arguments else ""


def _simple_type(node: Node) -> str:
    if node.type == "generic_type":
        node = node.child_by_field_name("name") or node.named_children[0]
    if node.type in ("type_identifier", "identifier", "nested_type_identifier", "member_expression"):
        return text(node).rpartition(".")[2]
    return ""


def _dotted(node: Node | None) -> str | None:
    """`this.http.get` -> "this.http.get"; None for `getApi().get` and similar."""
    if node is None:
        return None
    if node.type in ("identifier", "this", "super", "property_identifier"):
        return text(node)
    if node.type == "member_expression":
        base = _dotted(node.child_by_field_name("object"))
        prop = node.child_by_field_name("property")
        return f"{base}.{text(prop)}" if base and prop is not None else None
    if node.type == "non_null_expression":
        return _dotted(node.named_children[0])
    return None


def _is_http_client(receiver: str) -> bool:
    last = receiver.rpartition(".")[2]
    return last in HTTP_CLIENTS or "http" in last.lower()


def _fetch_method(options: Node) -> str:
    if options.type == "object":
        for pair in options.named_children:
            if pair.type == "pair" and text(pair.child_by_field_name("key")).strip("'\"") == "method":
                value = string_value(pair.child_by_field_name("value"))
                if value:
                    return value.upper()
    return "GET"


def _url_template(node: Node) -> str:
    """URL argument as a template: dynamic parts become `{expression}`."""
    literal = string_value(node)
    if literal is not None:
        return literal
    if node.type == "template_string":
        parts = []
        for child in node.named_children:
            if child.type == "template_substitution":
                parts.append("{" + text(child)[2:-1].strip() + "}")
            else:
                parts.append(text(child))
        return "".join(parts)
    if node.type == "binary_expression" and text(node.child_by_field_name("operator")) == "+":
        return _url_template(node.child_by_field_name("left")) + _url_template(node.child_by_field_name("right"))
    if node.type == "parenthesized_expression" and node.named_children:
        return _url_template(node.named_children[0])
    return "{" + text(node) + "}"
