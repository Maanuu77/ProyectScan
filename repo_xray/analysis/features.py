"""Level 2: what a project does, as business features per app.

A feature is found in one of three ways, in this order:

1. an explicit container folder (`features/`, `modules/`, `domains/`);
2. vertical slices: folders that hold several layers on their own
   (`banco/` with `web/`, `application/`, `domain/` and `persistence/`);
3. in layer-first projects, files grouped by their base name
   (`OrderController`, `OrderService` and `OrderRepository` make "Order").

Folders such as `shared/` or `core/` are reported as shared foundations,
not as features. Frontend features are then linked to the backend
features they call, following the call graph down to the HTTP calls.
"""

import posixpath
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from repo_xray.analysis import catalog
from repo_xray.analysis.calls import CallGraph
from repo_xray.analysis.layers import classify
from repo_xray.analysis.linking import HttpLink
from repo_xray.analysis.paths import is_inside, is_test_path
from repo_xray.analysis.stack import App, Stack
from repo_xray.model import Endpoint, SourceFile

CONTAINERS = ("features", "modules", "domains", "feature", "module", "domain-modules")
SHARED_NAMES = {"shared", "common", "core", "util", "utils", "lib", "libs", "helpers", "config",
                "infrastructure", "infra", "support", "base", "commons", "environments", "styles",
                "assets", "types", "app"}
SLICE_LAYERS = {"entry", "application", "domain", "data"}
NAME_SUFFIXES = {"controller", "service", "services", "repository", "repo", "dao", "entity", "dto", "request",
                 "response", "mapper", "impl", "usecase", "use", "case", "adapter", "api", "page", "component",
                 "store", "model", "models", "resource", "handler", "router", "routes", "view", "schema",
                 "serializer", "form", "client", "jpa", "persistence", "web", "command", "query", "test"}
MAX_CALL_DEPTH = 5


@dataclass
class Feature:
    key: str  # unique across apps, e.g. "backend/resena"
    name: str
    app: str
    path: str  # main folder, or "" for features grouped by name
    files: list[str] = field(default_factory=list)
    layers: dict[str, int] = field(default_factory=dict)  # layer -> number of files
    endpoints: list[Endpoint] = field(default_factory=list)
    http_calls: int = 0
    description: str | None = None
    calls: dict[str, int] = field(default_factory=dict)  # backend feature key -> HTTP calls made to it
    services: list[str] = field(default_factory=list)  # external services it reaches, e.g. "Firebase Auth"
    depends_on: dict[str, int] = field(default_factory=dict)  # same-app feature key -> calls into it


@dataclass
class SharedPart:
    """Code every feature leans on: `shared/`, `core/`, configuration…"""

    app: str
    name: str
    files: int
    layers: dict[str, int] = field(default_factory=dict)


@dataclass
class FeatureMap:
    features: list[Feature] = field(default_factory=list)
    shared: list[SharedPart] = field(default_factory=list)

    def of_app(self, app: str) -> list[Feature]:
        return [f for f in self.features if f.app == app]


def detect_features(stack: Stack, files: list[SourceFile], graph: CallGraph, links: list[HttpLink]) -> FeatureMap:
    result = FeatureMap()
    owner = _owners(stack, files)
    feature_of_file: dict[str, Feature] = {}
    for app in stack.apps:
        app_files = [f for f in files if owner.get(f.path) is app and not is_test_path(f.path)]
        layers = {f.path: classify(f, app.kind) for f in app_files}
        groups, shared = _group(app, app_files, layers)
        for name, (folder, members) in groups.items():
            feature = _make_feature(app, name, folder, members, layers)
            result.features.append(feature)
            for member in members:
                feature_of_file[member.path] = feature
        for name, members in sorted(shared.items()):
            counts = Counter(layers[m.path] for m in members)
            result.shared.append(SharedPart(app.name, name, len(members), dict(counts)))
    _connect(result, files, feature_of_file, graph, links)
    for feature in result.features:
        feature.services = _canonical_services(feature.services, stack)
    return result


def _canonical_services(names: list[str], stack: Stack) -> list[str]:
    """Use the names of level 1: "Cloud Storage" is shown as "Firebase Storage" when that is the service."""
    known = {s.name for s in stack.services}
    result = []
    for name in names:
        specific = next((k for k, generic in catalog.SUPERSEDES.items() if name in generic and k in known), None)
        name = specific or name
        if name in known and name not in result:
            result.append(name)
    return result


def _owners(stack: Stack, files: list[SourceFile]) -> dict[str, App]:
    apps = sorted(stack.apps, key=lambda a: -len(a.path) if a.path != "." else 0)
    return {f.path: a for f in files for a in [next((a for a in apps if is_inside(f.path, a.path)), None)] if a}


def _group(app: App, files: list[SourceFile], layers: dict[str, str]):
    """Split an app's files into features and shared parts: ({name: (folder, files)}, {name: files})."""
    if not files:
        return {}, {}
    root = _common_folder([f.path for f in files])
    for strategy in (_by_container, _by_slices):
        grouped = strategy(root, files, layers)
        if grouped is not None:
            return grouped
    return _by_name(root, files, layers)


def _by_container(root: str, files: list[SourceFile], layers: dict[str, str]):
    containers = Counter()
    for file in files:
        parts = _relative(file.path, root).split("/")[:-1]
        for index, part in enumerate(parts[:-1]):
            if part.lower() in CONTAINERS:
                containers["/".join(parts[: index + 1])] += 1
    for container, _ in containers.most_common():
        children = defaultdict(list)
        for file in files:
            relative = _relative(file.path, root)
            if relative.startswith(container + "/") and relative.count("/") > container.count("/") + 1:
                children[relative[len(container) + 1:].split("/")[0]].append(file)
        if len(children) >= 2:
            features = {name: (_join(root, container, name), members) for name, members in children.items()}
            claimed = {m.path for _, members in features.values() for m in members}
            # Shared code usually sits next to the container: src/app/{features,core,shared}.
            beside = _join(root, posixpath.dirname(container))
            rest = [f for f in files if f.path not in claimed]
            shared = _shared_by_top_folder(beside, [f for f in rest if is_inside(f.path, beside)])
            for name, members in _shared_by_top_folder(root, [f for f in rest if not is_inside(f.path, beside)]).items():
                shared.setdefault(name, []).extend(members)
            return features, shared
    return None


def _by_slices(root: str, files: list[SourceFile], layers: dict[str, str]):
    children = defaultdict(list)
    for file in files:
        relative = _relative(file.path, root)
        children[relative.split("/")[0] if "/" in relative else ""].append(file)
    slices = {
        name: members for name, members in children.items()
        if name and name.lower() not in SHARED_NAMES
        and len({layers[m.path] for m in members} & SLICE_LAYERS) >= 2
    }
    if len(slices) < 2:
        return None
    features = {name: (_join(root, name), members) for name, members in slices.items()}
    rest = [f for name, members in children.items() if name not in slices for f in members]
    return features, _shared_by_top_folder(root, rest)


def _by_name(root: str, files: list[SourceFile], layers: dict[str, str]):
    stems = defaultdict(list)
    for file in files:
        stems[_stem(file)].append(file)
    features, rest = {}, []
    for stem, members in stems.items():
        if stem and len({layers[m.path] for m in members} & SLICE_LAYERS) >= 2:
            features[stem] = ("", members)
        else:
            rest.extend(members)
    if len(features) < 2:
        return {"": (root, files)}, {}
    return features, _shared_by_top_folder(root, rest)


def _shared_by_top_folder(root: str, files: list[SourceFile]) -> dict[str, list[SourceFile]]:
    shared = defaultdict(list)
    for file in files:
        relative = _relative(file.path, root)
        shared[relative.split("/")[0] if "/" in relative else "(root)"].append(file)
    return dict(shared)


def _make_feature(app: App, name: str, folder: str, members: list[SourceFile], layers: dict[str, str]) -> Feature:
    tags = _tags(members)
    feature = Feature(
        key=f"{app.name}/{name or app.name}",
        name=_display_name(name or app.name, [tag for tag, _ in tags]),
        app=app.name,
        path=folder,
        files=sorted(m.path for m in members),
        layers=dict(Counter(layers[m.path] for m in members)),
        endpoints=[e for m in members for e in m.endpoints],
        http_calls=sum(len(m.http_calls) for m in members),
    )
    feature.description = _description(feature, members, layers, tags)
    return feature


def _connect(result: FeatureMap, files: list[SourceFile], feature_of_file: dict[str, Feature],
             graph: CallGraph, links: list[HttpLink]) -> None:
    """Which backend features each feature calls over HTTP, and which features it depends on."""
    links_by_caller = defaultdict(list)
    for link in links:
        links_by_caller[link.call.caller].append(link)
    for feature in result.features:
        starts = [s.qualname for f in files if f.path in feature.files for s in f.symbols]
        reached = _reachable(graph, starts)
        reached_files = {feature_files.path for q in reached for feature_files in [graph.file_of.get(q)] if feature_files}
        for file in files:
            if file.path in reached_files or file.path in feature.files:
                for imported in file.imports:
                    tech = catalog.match_import(imported.module)
                    if tech is not None and tech.name not in feature.services:
                        feature.services.append(tech.name)
        for qualname in reached:
            for link in links_by_caller.get(qualname, []):
                target = feature_of_file.get(link.endpoint_path)
                if target is not None and target is not feature:
                    feature.calls[target.key] = feature.calls.get(target.key, 0) + 1
        for start in starts:
            for callee in graph.calls_from(start):
                target_file = graph.file_of.get(callee)
                target = feature_of_file.get(target_file.path) if target_file else None
                if target is not None and target is not feature and target.app == feature.app:
                    feature.depends_on[target.key] = feature.depends_on.get(target.key, 0) + 1


def _reachable(graph: CallGraph, starts: list[str]) -> set[str]:
    seen, frontier = set(starts), list(starts)
    for _ in range(MAX_CALL_DEPTH):
        frontier = [c for q in frontier for c in graph.calls_from(q) if c not in seen]
        seen.update(frontier)
    return seen


# Names and descriptions


_TAG = re.compile(r'^Tag\(\s*name\s*=\s*"([^"]+)"(?:\s*,\s*description\s*=\s*"([^"]+)")?')


def _tags(members: list[SourceFile]) -> list[tuple[str, str | None]]:
    """OpenAPI `@Tag(name, description)` on controllers: the authors' own name for the feature."""
    tags = []
    for member in members:
        for symbol in member.symbols:
            for decorator in symbol.decorators:
                match = _TAG.match(decorator)
                if match:
                    tags.append((match.group(1), match.group(2)))
    # Plain tags ("Usuarios") describe the feature better than sub-areas ("Administración: usuarios").
    return sorted(tags, key=lambda tag: ":" in tag[0])


def _display_name(name: str, tag_names: list[str]) -> str:
    key = _fold(name)
    for tag in tag_names:
        tag = tag.rpartition(":")[2].strip()  # "Administración: moderación" -> "moderación"
        if _fold(tag).startswith(key[:4]):
            return tag[:1].upper() + tag[1:]
    words = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", re.sub(r"[-_.]", " ", name))
    text = " ".join(words) or name
    return text[:1].upper() + text[1:].lower()


def _description(feature: Feature, members: list[SourceFile], layers: dict[str, str],
                 tags: list[tuple[str, str | None]]) -> str | None:
    name = _fold(feature.name)
    described = [d for t, d in tags if d]
    for tag, text in tags:
        if text and _fold(tag.rpartition(":")[2]).startswith(name[:4]):
            return text
    if described:
        return described[0]
    for wanted in ("entry", "application", "domain"):
        for member in members:
            if layers[member.path] == wanted:
                docs = [member.docstring] + [s.docstring for s in member.symbols if s.kind == "class"]
                for doc in docs:
                    if doc:
                        return _first_sentence(doc)
    return None


def _first_sentence(text: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s", " ".join(text.split()), maxsplit=1)[0]
    return sentence.rstrip(".")


def _stem(file: SourceFile) -> str:
    """`OrderJpaRepository.java` -> `order`; `order-list.component.ts` -> `order-list`."""
    base = posixpath.basename(file.path).split(".")[0]
    words = [w.lower() for w in re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", base.replace("-", " ").replace("_", " "))]
    while len(words) > 1 and words[-1] in NAME_SUFFIXES:
        words.pop()
    if words and words[-1] in NAME_SUFFIXES:
        return ""
    return "-".join(words)


def _fold(text: str) -> str:
    """Lower case without accents or plural `s`, to compare `Reseñas` with `resena`."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", plain)


def _common_folder(paths: list[str]) -> str:
    folders = [posixpath.dirname(p) for p in paths]
    common = posixpath.commonpath(folders) if folders else ""
    return common if common != "." else ""


def _relative(path: str, root: str) -> str:
    return path[len(root) + 1:] if root and path.startswith(root + "/") else path


def _join(*parts: str) -> str:
    return "/".join(p for p in parts if p)
