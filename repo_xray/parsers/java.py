"""Java parser: package, types, methods, annotations, imports, calls and Spring endpoints."""

from pathlib import Path

import tree_sitter_java
from tree_sitter import Language, Node, Parser

from repo_xray.model import Call, Endpoint, Import, SourceFile, Symbol
from repo_xray.parsers.treesitter import doc_comment, end_line, line, string_value, text

_PARSER = Parser(Language(tree_sitter_java.language()))

TYPE_KINDS = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "record_declaration": "record",
    "annotation_type_declaration": "interface",
}
METHOD_NODES = ("method_declaration", "constructor_declaration", "compact_constructor_declaration")

# Spring MVC mapping annotations and the HTTP method each one implies.
MAPPINGS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "PatchMapping": "PATCH",
    "DeleteMapping": "DELETE",
    "RequestMapping": "ANY",
}
# Receivers simple enough to keep as written: `repo.save`, `this.repo.save`, `Foo.bar`.
SIMPLE_RECEIVERS = ("identifier", "field_access", "this", "super")


def parse(source: bytes, relative_path: Path) -> SourceFile:
    root = _PARSER.parse(source).root_node
    package = ""
    for child in root.named_children:
        if child.type == "package_declaration":
            package = text(child.named_children[-1])
    stem = relative_path.stem
    info = SourceFile(
        path=relative_path.as_posix(),
        language="java",
        name=f"{package}.{stem}" if package else stem,
        package=package,
        line_count=len(source.splitlines()),
    )
    _Collector(info, package or stem).visit(root)
    return info


class _Collector:
    """Walks the syntax tree keeping the enclosing type or method and the route prefix."""

    def __init__(self, info: SourceFile, root_scope: str):
        self.info = info
        self.scopes: list[Symbol | None] = [None]
        self.root_scope = root_scope
        self.route_prefixes: list[list[str]] = [[""]]

    @property
    def scope(self) -> str:
        current = self.scopes[-1]
        return current.qualname if current else self.root_scope

    def visit(self, node: Node) -> None:
        if node.type in TYPE_KINDS:
            self._visit_type(node)
        elif node.type in METHOD_NODES:
            self._visit_method(node)
        elif node.type == "import_declaration":
            self._add_import(node)
        elif node.type == "field_declaration":
            self._add_field(node)
            self._visit_children(node)
        elif node.type == "method_invocation":
            self._add_invocation(node)
            self._visit_children(node)
        elif node.type == "object_creation_expression":
            self._add_call(f"new {_simple_type(node.child_by_field_name('type'))}", node)
            self._visit_children(node)
        elif node.type == "method_reference":
            self._add_method_reference(node)
        else:
            self._visit_children(node)

    def _visit_children(self, node: Node) -> None:
        for child in node.named_children:
            self.visit(child)

    def _visit_type(self, node: Node) -> None:
        name = text(node.child_by_field_name("name"))
        annotations = _annotations(node)
        symbol = Symbol(
            kind=TYPE_KINDS[node.type],
            name=name,
            qualname=f"{self.scope}.{name}",
            parent=self.scope,
            lineno=line(node),
            end_lineno=end_line(node),
            docstring=doc_comment(node),
            decorators=[text(a)[1:] for a in annotations],
            bases=_bases(node),
        )
        if node.type == "record_declaration":
            parameters = node.child_by_field_name("parameters")
            for parameter in parameters.named_children if parameters else []:
                symbol.fields[text(parameter.child_by_field_name("name"))] = _simple_type(
                    parameter.child_by_field_name("type"))
        self.info.symbols.append(symbol)

        prefixes = [p for a in annotations if _annotation_name(a) == "RequestMapping" for p in _mapping_paths(a)]
        self.scopes.append(symbol)
        self.route_prefixes.append(prefixes or [""])
        body = node.child_by_field_name("body")
        if body is not None:
            self._visit_children(body)
        self.route_prefixes.pop()
        self.scopes.pop()

    def _visit_method(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        name = text(name_node) if name_node else self.scopes[-1].name
        annotations = _annotations(node)
        symbol = Symbol(
            kind="method",
            name=name,
            qualname=f"{self.scope}.{name}",
            parent=self.scope,
            lineno=line(node),
            end_lineno=end_line(node),
            docstring=doc_comment(node),
            decorators=[text(a)[1:] for a in annotations],
        )
        self.info.symbols.append(symbol)
        self._add_endpoints(symbol, annotations)

        self.scopes.append(symbol)
        body = node.child_by_field_name("body")
        if body is not None:
            self._visit_children(body)
        self.scopes.pop()

    def _add_endpoints(self, symbol: Symbol, annotations: list[Node]) -> None:
        summary = _operation_summary(annotations) or symbol.docstring
        for annotation in annotations:
            http_method = MAPPINGS.get(_annotation_name(annotation))
            if http_method is None:
                continue
            if http_method == "ANY":
                http_method = _request_method(annotation)
            for prefix in self.route_prefixes[-1]:
                for path in _mapping_paths(annotation):
                    self.info.endpoints.append(Endpoint(
                        method=http_method,
                        path=_join_route(prefix, path),
                        handler=symbol.qualname,
                        lineno=symbol.lineno,
                        summary=summary,
                    ))

    def _add_import(self, node: Node) -> None:
        target = text(next(c for c in node.named_children if c.type in ("scoped_identifier", "identifier")))
        is_wildcard = any(c.type == "asterisk" for c in node.named_children)
        module, _, name = (target, "", "*") if is_wildcard else target.rpartition(".")
        self.info.imports.append(Import(
            module=module, name=name, alias=None, level=0, lineno=line(node), scope=self.scope))

    def _add_field(self, node: Node) -> None:
        owner = self.scopes[-1]
        if owner is None:
            return
        field_type = _simple_type(node.child_by_field_name("type"))
        for declarator in node.named_children:
            if declarator.type == "variable_declarator":
                owner.fields[text(declarator.child_by_field_name("name"))] = field_type

    def _add_invocation(self, node: Node) -> None:
        name = text(node.child_by_field_name("name"))
        receiver = node.child_by_field_name("object")
        if receiver is None:
            self._add_call(name, node)
        elif receiver.type in SIMPLE_RECEIVERS:
            self._add_call(f"{text(receiver)}.{name}", node)

    def _add_method_reference(self, node: Node) -> None:
        parts = [text(c) for c in node.named_children]
        if len(parts) == 2:
            self._add_call(f"{parts[0]}.{parts[1]}", node)

    def _add_call(self, callee: str, node: Node) -> None:
        self.info.calls.append(Call(caller=self.scope, callee=callee, lineno=line(node)))


def _annotations(node: Node) -> list[Node]:
    modifiers = next((c for c in node.children if c.type == "modifiers"), None)
    if modifiers is None:
        return []
    return [c for c in modifiers.named_children if c.type in ("annotation", "marker_annotation")]


def _annotation_name(annotation: Node) -> str:
    return text(annotation.child_by_field_name("name")).rpartition(".")[2]


def _annotation_arguments(annotation: Node) -> list[tuple[str, Node]]:
    """`@X("a", method = GET)` -> [("value", "a"), ("method", GET)]."""
    arguments = annotation.child_by_field_name("arguments")
    pairs = []
    for child in arguments.named_children if arguments else []:
        if child.type == "element_value_pair":
            pairs.append((text(child.named_children[0]), child.child_by_field_name("value")))
        elif child.type != "comment":
            pairs.append(("value", child))
    return pairs


def _mapping_paths(annotation: Node) -> list[str]:
    paths = []
    for key, value in _annotation_arguments(annotation):
        if key not in ("value", "path"):
            continue
        items = value.named_children if value.type == "element_value_array_initializer" else [value]
        paths.extend(s for s in (string_value(item) for item in items) if s is not None)
    return paths or [""]


def _request_method(annotation: Node) -> str:
    for key, value in _annotation_arguments(annotation):
        if key == "method":
            return text(value).rpartition(".")[2].strip("{} ") or "ANY"
    return "ANY"


def _operation_summary(annotations: list[Node]) -> str | None:
    for annotation in annotations:
        if _annotation_name(annotation) == "Operation":
            for key, value in _annotation_arguments(annotation):
                if key == "summary":
                    return string_value(value)
    return None


def _join_route(prefix: str, path: str) -> str:
    route = "/" + "/".join(part.strip("/") for part in (prefix, path) if part.strip("/"))
    return route


def _bases(node: Node) -> list[str]:
    bases = []
    for child in node.named_children:
        if child.type in ("superclass", "super_interfaces", "extends_interfaces"):
            for type_node in child.named_children:
                items = type_node.named_children if type_node.type == "type_list" else [type_node]
                bases.extend(_simple_type(item) for item in items)
    return bases


def _simple_type(node: Node | None) -> str:
    """`List<Foo>` -> `List`, `com.x.Foo` -> `Foo`; the name used to look the type up."""
    if node is None:
        return ""
    if node.type == "generic_type":
        node = node.named_children[0]
    return text(node).rpartition(".")[2]
