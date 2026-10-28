"""Work out which function or method each call reaches.

Parsers record calls as written (`resenas.publicar`). This module follows
field types, imports and interfaces to the code that runs:
`resenas` is a `ResenasUseCase`, which `ResenaService` implements, so the
call reaches `ResenaService.publicar`. Calls on local variables or on
values returned by other calls stay unresolved; that limitation is
accepted (ADR-0002).
"""

from collections import defaultdict
from dataclasses import dataclass, field

from repo_xray.model import SourceFile, Symbol

TYPE_KINDS = ("class", "interface", "enum", "record")
SELF_NAMES = ("this", "self", "super")


@dataclass
class CallGraph:
    symbols: dict[str, Symbol] = field(default_factory=dict)
    file_of: dict[str, SourceFile] = field(default_factory=dict)  # symbol qualname -> its file
    callees: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def calls_from(self, qualname: str) -> list[str]:
        return self.callees.get(qualname, [])


def build_call_graph(files: list[SourceFile]) -> CallGraph:
    return _Resolver(files).build()


class _Resolver:
    def __init__(self, files: list[SourceFile]):
        self.files = files
        self.graph = CallGraph()
        self.types_by_name: dict[str, list[Symbol]] = defaultdict(list)
        self.members: dict[str, dict[str, Symbol]] = defaultdict(dict)  # type qualname -> name -> member
        self.implementations: dict[str, list[Symbol]] = defaultdict(list)  # base name -> subtypes
        self.module_members: dict[str, dict[str, Symbol]] = defaultdict(dict)  # file name -> top-level symbols

        for file in files:
            top_level_scope = file.package if file.language == "java" and file.package else file.name
            for symbol in file.symbols:
                self.graph.symbols[symbol.qualname] = symbol
                self.graph.file_of[symbol.qualname] = file
                if symbol.kind in TYPE_KINDS:
                    self.types_by_name[symbol.name].append(symbol)
                    for base in symbol.bases:
                        self.implementations[base].append(symbol)
                self.members[symbol.parent][symbol.name] = symbol
                if symbol.parent == top_level_scope:
                    self.module_members[file.name][symbol.name] = symbol

    def build(self) -> CallGraph:
        for file in self.files:
            imported = self._imported_names(file)
            for call in file.calls:
                for target in self._resolve(call.caller, call.callee, file, imported):
                    if target.qualname != call.caller and target.qualname not in self.graph.callees[call.caller]:
                        self.graph.callees[call.caller].append(target.qualname)
        return self.graph

    def _resolve(self, caller: str, callee: str, file: SourceFile, imported: dict[str, Symbol]) -> list[Symbol]:
        owner = self._enclosing_type(caller)
        if callee.startswith("new "):
            cls = self._find_type(callee[4:], file, imported)
            return [cls] if cls else []

        parts = callee.split(".")
        if parts[0] in SELF_NAMES and owner is not None:
            parts = parts[1:]
            if len(parts) == 1:
                return self._methods(owner, parts[0])
        if len(parts) == 1:
            name = parts[0]
            if owner is not None and (method := self._methods(owner, name)):
                return method
            target = imported.get(name) or self.module_members[file.name].get(name)
            return [target] if target else []
        if len(parts) == 2:
            receiver, method = parts
            if owner is not None and receiver in self._fields(owner):
                field_type = self._find_type(self._fields(owner)[receiver], file, imported)
                return self._methods(field_type, method) if field_type else []
            receiver_type = self._find_type(receiver, file, imported)
            if receiver_type is not None:  # a static call such as `Factory.create()`
                return self._methods(receiver_type, method)
            module_symbol = imported.get(receiver)
            if module_symbol is None and receiver in self.module_members:
                return [s for s in [self.module_members[receiver].get(method)] if s]
        return []

    def _methods(self, owner: Symbol, name: str) -> list[Symbol]:
        """`name` on `owner`, looking in its bases and, for an interface, its implementations."""
        found = self._own_or_inherited(owner, name, set())
        if owner.kind == "interface":
            implementations = [m for impl in self.implementations.get(owner.name, [])
                               if (m := self._own_or_inherited(impl, name, set())) is not None]
            if implementations:
                return implementations
        return [found] if found else []

    def _own_or_inherited(self, owner: Symbol, name: str, seen: set[str]) -> Symbol | None:
        if owner.qualname in seen:
            return None
        seen.add(owner.qualname)
        if name in self.members[owner.qualname]:
            return self.members[owner.qualname][name]
        for base in owner.bases:
            for candidate in self.types_by_name.get(base, []):
                if (found := self._own_or_inherited(candidate, name, seen)) is not None:
                    return found
        return None

    def _fields(self, owner: Symbol) -> dict[str, str]:
        fields = dict(owner.fields)
        for base in owner.bases:
            for candidate in self.types_by_name.get(base, []):
                fields = {**candidate.fields, **fields}
        return fields

    def _enclosing_type(self, qualname: str) -> Symbol | None:
        symbol = self.graph.symbols.get(qualname)
        while symbol is not None and symbol.kind not in TYPE_KINDS:
            symbol = self.graph.symbols.get(symbol.parent)
        return symbol

    def _find_type(self, name: str, file: SourceFile, imported: dict[str, Symbol]) -> Symbol | None:
        """The type called `name` that `file` can see: imported, same file, same package, or unique."""
        if name in imported and imported[name].kind in TYPE_KINDS:
            return imported[name]
        candidates = self.types_by_name.get(name, [])
        for rule in (
            lambda s: self.graph.file_of[s.qualname] is file,
            lambda s: self.graph.file_of[s.qualname].package == file.package,
            lambda s: self.graph.file_of[s.qualname].language == file.language,
        ):
            matching = [s for s in candidates if rule(s)]
            if len(matching) == 1:
                return matching[0]
        return candidates[0] if len(candidates) == 1 else None

    def _imported_names(self, file: SourceFile) -> dict[str, Symbol]:
        names = {}
        for imported in file.imports:
            if not imported.name or imported.name in ("*", "default"):
                continue
            local = imported.alias or imported.name
            if file.language == "java":
                matches = [s for s in self.types_by_name.get(imported.name, [])
                           if self.graph.file_of[s.qualname].package == imported.module]
            else:
                members = self.module_members.get(imported.module) or self.module_members.get(imported.module + "/index", {})
                matches = [members[imported.name]] if imported.name in members else []
            if matches:
                names[local] = matches[0]
        return names
