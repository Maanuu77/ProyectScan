"""Which architectural layer each file belongs to.

The vocabulary is the same for every language and framework, so a Spring
hexagonal backend and an Angular frontend can be drawn side by side:

- entry: where requests or users come in (controllers, routes, pages, components)
- application: what the app does (use cases, services, stores, hooks)
- domain: the business concepts (entities, value objects, models)
- data: where data is stored or fetched (repositories, persistence, API clients)
- integration: wiring and third parties (configuration, security, adapters)
"""

import re
from pathlib import PurePosixPath

from repo_xray.analysis.paths import is_test_path
from repo_xray.model import SourceFile

LAYERS = {
    "entry": "Entry points",
    "application": "Application logic",
    "domain": "Domain model",
    "data": "Data access",
    "integration": "Integrations & config",
    "test": "Tests",
    "other": "Other",
}

ANNOTATIONS = {
    "RestController": "entry", "Controller": "entry", "Path": "entry", "Repository": "data", "Entity": "data",
    "Configuration": "integration", "SpringBootApplication": "integration",
    "ConfigurationProperties": "integration",
}
# Angular decorators; Spring also has a @Component, which says nothing about the layer.
TS_DECORATORS = {"Component": "entry", "Directive": "entry", "Pipe": "entry"}

# Names that say what a file is more reliably than the folder it sits in.
DECISIVE_SUFFIXES = {
    "config": "integration", "configuration": "integration", "interceptor": "integration",
    "guard": "integration", "guards": "integration", "filter": "integration", "seeder": "integration",
    "properties": "integration", "application": "integration", "module": "integration",
    "model": "domain", "models": "domain", "types": "domain", "dto": "entry",
}

FOLDERS = {
    "entry": {"web", "controller", "controllers", "rest", "routes", "router", "routers", "handlers",
              "endpoints", "views", "pages", "components", "ui", "screens", "layout", "presentation",
              "dto", "dtos", "graphql", "cli", "commands"},
    "application": {"application", "usecase", "usecases", "use-cases", "use_cases", "services", "service",
                    "port", "ports", "in", "store", "stores", "state", "hooks"},
    "domain": {"domain", "model", "models", "entities", "entity", "valueobjects"},
    "data": {"persistence", "repository", "repositories", "dao", "db", "database", "data", "storage",
             "migrations", "migration", "queries"},
    "integration": {"infrastructure", "infra", "config", "configuration", "security", "adapters", "adapter",
                    "integration", "integrations", "external", "clients", "firebase", "messaging",
                    "auth", "interceptors", "guards", "middleware", "bootstrap"},
}

SUFFIXES = {
    "entry": ("controller", "resource", "handler", "router", "routes", "endpoint", "page", "component",
              "view", "screen", "layout", "dialog", "pipe", "directive"),
    "application": ("service", "usecase", "interactor", "store", "state", "facade"),
    "domain": ("entity", "exception", "policy", "event"),
    "data": ("repository", "dao", "api", "client", "queries", "gateway"),
}

_WORDS = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")


def classify(file: SourceFile, app_kind: str = "api") -> str:
    """The layer of one file; `app_kind` disambiguates folders such as `api/`."""
    if is_test_path(file.path):
        return "test"
    if file.endpoints:
        return "entry"
    if file.http_calls:
        return "data"
    annotations = {d.split("(")[0].rpartition(".")[2] for s in file.symbols for d in s.decorators}
    known = TS_DECORATORS if file.language in ("typescript", "javascript") else ANNOTATIONS
    for annotation, layer in known.items():
        if annotation in annotations:
            return layer

    words = _name_words(file.path)
    if words and words[-1] in DECISIVE_SUFFIXES:
        return DECISIVE_SUFFIXES[words[-1]]
    if words and words[0] == "use" and len(words) > 1 and file.language in ("typescript", "javascript"):
        return "application"  # React hooks: useOrders, use-cart

    for folder in reversed(PurePosixPath(file.path).parts[:-1]):
        layer = _folder_layer(folder.lower(), app_kind)
        if layer:
            return layer

    for layer, suffixes in SUFFIXES.items():
        if words and words[-1] in suffixes:
            return layer
    return "other"


def _folder_layer(folder: str, app_kind: str) -> str | None:
    if folder == "api":
        # In a frontend, `api/` holds the HTTP clients; in a backend, the controllers.
        return "data" if app_kind in ("web", "mobile", "desktop") else "entry"
    return next((layer for layer, names in FOLDERS.items() if folder in names), None)


def _name_words(path: str) -> list[str]:
    """`BancoJpaRepository.java` -> [banco, jpa, repository]; `auth.interceptor.ts` -> [auth, interceptor]."""
    stem = PurePosixPath(path).name.split(".")
    stem = [part for part in stem[:-1]] if len(stem) > 1 else stem
    return [w.lower() for part in stem for chunk in re.split(r"[-_]", part) for w in _WORDS.findall(chunk)]
