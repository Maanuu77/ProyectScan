"""Level 3: what happens when someone uses a feature.

A flow follows one request from the screen that starts it, through the
frontend's API client, over HTTP to the endpoint, down the backend's
layers and into the database or service where it ends. Only the main
path is kept: at each step the call that goes deepest (entry ->
application -> data) wins, preferring code of the same feature, so a
flow stays short enough to read.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from repo_xray.analysis import catalog
from repo_xray.analysis.calls import CallGraph
from repo_xray.analysis.features import FeatureMap
from repo_xray.analysis.layers import classify
from repo_xray.analysis.linking import HttpLink
from repo_xray.analysis.paths import is_inside, is_test_path
from repo_xray.analysis.stack import Stack
from repo_xray.model import Endpoint, SourceFile

LAYER_DEPTH = {"entry": 0, "application": 1, "integration": 2, "data": 3}
MAX_BACKEND_STEPS = 5
MAX_UI_SEARCH = 4
WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")
_NOISE = re.compile(r"(Mapper|Converter|Assembler|Dto|Request|Response)$")


@dataclass
class Step:
    qualname: str
    name: str  # what the reader sees: `ResenaService.publicar`
    app: str
    layer: str  # a layer key, or "service" for the database or service where the flow ends
    feature: str | None = None  # feature key


@dataclass
class Flow:
    key: str
    title: str
    method: str
    route: str
    feature: str | None  # backend feature key
    steps: list[Step] = field(default_factory=list)
    http_index: int | None = None  # the request crosses from steps[i - 1] to steps[i]
    score: float = 0


def build_flows(stack: Stack, files: list[SourceFile], graph: CallGraph, links: list[HttpLink],
                feature_map: FeatureMap) -> list[Flow]:
    return _FlowBuilder(stack, files, graph, links, feature_map).build()


def pick_flows(flows: list[Flow], limit: int = 3) -> list[Flow]:
    """The most telling flows, at most one per backend feature."""
    chosen, seen = [], set()
    for flow in sorted(flows, key=lambda f: -f.score):
        if flow.feature in seen:
            continue
        chosen.append(flow)
        seen.add(flow.feature)
        if len(chosen) == limit:
            break
    return chosen


class _FlowBuilder:
    def __init__(self, stack: Stack, files: list[SourceFile], graph: CallGraph, links: list[HttpLink],
                 feature_map: FeatureMap):
        self.stack = stack
        self.graph = graph
        self.links_by_endpoint = defaultdict(list)
        for link in links:
            self.links_by_endpoint[(link.endpoint_path, link.endpoint.handler, link.endpoint.method)].append(link)
        self.callers = defaultdict(list)
        for caller, callees in graph.callees.items():
            for callee in callees:
                self.callers[callee].append(caller)
        self.feature_of_file = {path: f for f in feature_map.features for path in f.files}
        apps = sorted(stack.apps, key=lambda a: -len(a.path) if a.path != "." else 0)
        self.app_of_file = {f.path: a.name for f in files for a in [next((a for a in apps if is_inside(f.path, a.path)), None)] if a}
        kinds = {a.name: a.kind for a in stack.apps}
        self.layer_of_file = {f.path: classify(f, kinds.get(self.app_of_file.get(f.path, ""), "api")) for f in files}
        self.files = files
        self.services_of_file = {
            f.path: [t.name for i in f.imports for t in [catalog.match_import(i.module)] if t] for f in files
        }

    def build(self) -> list[Flow]:
        flows = []
        for file in self.files:
            if is_test_path(file.path):
                continue
            for endpoint in file.endpoints:
                flows.append(self._flow(file, endpoint))
        return flows

    def _flow(self, file: SourceFile, endpoint: Endpoint) -> Flow:
        feature = self.feature_of_file.get(file.path)
        flow = Flow(
            key=f"{endpoint.method.lower()}-{_slug(endpoint.path)}",
            title=endpoint.summary or _title_from(endpoint),
            method=endpoint.method,
            route=endpoint.path,
            feature=feature.key if feature else None,
        )
        links = self.links_by_endpoint.get((file.path, endpoint.handler, endpoint.method), [])
        if links:
            front = self._frontend_steps(links[0])
            flow.steps.extend(front)
            flow.http_index = len(front)
        flow.steps.extend(self._backend_steps(endpoint.handler, feature.key if feature else None))
        flow.steps.extend(self._final_service(flow.steps))
        flow.score = self._score(flow)
        return flow

    def _frontend_steps(self, link: HttpLink) -> list[Step]:
        """The screen that starts the request, then the API client that sends it."""
        client = self._step(link.call.caller)
        if client is None:
            return []
        ui = self._nearest_entry_caller(link.call.caller)
        return [s for s in (self._step(ui) if ui else None, client) if s is not None]

    def _nearest_entry_caller(self, qualname: str) -> str | None:
        frontier, seen = [qualname], {qualname}
        for _ in range(MAX_UI_SEARCH):
            next_frontier = []
            for current in frontier:
                for caller in self.callers.get(current, []):
                    if caller in seen:
                        continue
                    seen.add(caller)
                    if self._layer(caller) == "entry" and not is_test_path(self._path(caller) or ""):
                        return self._outermost_in_class(caller)
                    next_frontier.append(caller)
            frontier = next_frontier
        return None

    def _outermost_in_class(self, qualname: str) -> str:
        """`submit()` is called by `buy()` in the same component: the user triggers `buy()`."""
        symbol, seen = self.graph.symbols[qualname], {qualname}
        while True:
            outer = next((c for c in self.callers.get(qualname, []) if c not in seen
                          and self.graph.symbols.get(c) is not None
                          and self.graph.symbols[c].parent == symbol.parent), None)
            if outer is None:
                return qualname
            seen.add(outer)
            qualname = outer

    def _backend_steps(self, handler: str, feature: str | None) -> list[Step]:
        steps, current, seen = [], handler, set()
        while current and len(steps) < MAX_BACKEND_STEPS and current not in seen:
            seen.add(current)
            step = self._step(current)
            if step is None:
                break
            steps.append(step)
            current = self._deepest_callee(current, feature, seen)
        return steps

    def _deepest_callee(self, qualname: str, feature: str | None, seen: set[str]) -> str | None:
        here = LAYER_DEPTH.get(self._layer(qualname), 0)
        current = self.graph.symbols.get(qualname)
        best, best_key = None, None
        for order, callee in enumerate(self.graph.calls_from(qualname)):
            symbol = self.graph.symbols.get(callee)
            if callee in seen or symbol is None or symbol.kind not in ("method", "function"):
                continue
            if current is not None and symbol.kind == "method" and symbol.parent == current.parent:
                continue  # private helpers of the same class are details, not steps
            owner = symbol.parent.rpartition(".")[2]
            if _NOISE.search(owner):
                continue
            depth = LAYER_DEPTH.get(self._layer(callee))
            if depth is None or depth < here:
                continue
            same_feature = self._feature(callee) == feature
            # Deeper layers first, then the same feature, then the last call (writes usually come last).
            key = (depth > here, same_feature, depth, order)
            if best_key is None or key > best_key:
                best, best_key = callee, key
        return best

    def _final_service(self, steps: list[Step]) -> list[Step]:
        if not steps or steps[-1].layer != "data":
            return []
        last = steps[-1]
        services = {s.name: s for s in self.stack.services}
        path = self._path(last.qualname) or ""
        imported = [n for n in self.services_of_file.get(path, []) if n in services]
        for name in imported:
            return [Step(name, name, name, "service")]
        databases = [s for s in self.stack.services if s.category == "database" and last.app in s.used_by]
        if databases:
            return [Step(databases[0].name, databases[0].name, databases[0].name, "service")]
        return []

    def _score(self, flow: Flow) -> float:
        score = len(flow.steps)
        if flow.http_index:
            score += 4
        if flow.method in WRITE_METHODS:
            score += 3 if flow.method in ("POST", "PUT") else 1
        if flow.steps and flow.steps[-1].layer == "service":
            score += 3
        return score

    # Lookups

    def _step(self, qualname: str | None) -> Step | None:
        symbol = self.graph.symbols.get(qualname) if qualname else None
        if symbol is None:
            return None
        path = self._path(qualname)
        owner = symbol.parent.rpartition(".")[2].rpartition("/")[2] if symbol.kind == "method" else ""
        feature = self.feature_of_file.get(path)
        return Step(
            qualname=qualname,
            name=f"{owner}.{symbol.name}" if owner else symbol.name,
            app=self.app_of_file.get(path, ""),
            layer=self.layer_of_file.get(path, "other"),
            feature=feature.key if feature else None,
        )

    def _path(self, qualname: str) -> str | None:
        file = self.graph.file_of.get(qualname)
        return file.path if file else None

    def _layer(self, qualname: str) -> str:
        return self.layer_of_file.get(self._path(qualname) or "", "other")

    def _feature(self, qualname: str) -> str | None:
        feature = self.feature_of_file.get(self._path(qualname) or "")
        return feature.key if feature else None


def _title_from(endpoint: Endpoint) -> str:
    return f"{endpoint.method} {endpoint.path}"


def _slug(route: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", route.lower()).strip("-") or "root"
