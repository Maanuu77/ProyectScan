"""Level 1: what a project is made of.

Apps come from build manifests (pom.xml, package.json, pyproject.toml…).
Databases and external services come from dependencies, imports, compose
files and connection strings. Deployment targets come from Dockerfiles,
cloud configuration and CI workflows.
"""

import json
import re
import tomllib
import xml.etree.ElementTree as ElementTree
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import yaml

from repo_xray.analysis import catalog
from repo_xray.analysis.catalog import Tech
from repo_xray.analysis.paths import is_inside
from repo_xray.model import SourceFile
from repo_xray.scanner import ScanResult

PROJECT_MANIFESTS = ("pom.xml", "build.gradle", "build.gradle.kts", "package.json",
                     "pyproject.toml", "requirements.txt", "setup.py", "pipfile")
TEST_SCOPES = {"test", "provided"}
MAX_CONFIG_BYTES = 200_000


@dataclass
class App:
    """Something that runs on its own: a web frontend, an API, a mobile app…"""

    name: str
    path: str  # folder relative to the root, "." for the root itself
    kind: str  # "web", "api", "mobile", "desktop" or "library"
    language: str
    technologies: list[str] = field(default_factory=list)  # e.g. ["Spring Boot 4.1", "Java 21"]
    files: int = 0
    lines: int = 0
    deployments: list[str] = field(default_factory=list)  # e.g. ["Docker", "Cloud Run"]


@dataclass
class Service:
    """A database, auth provider, storage or external API that the apps use."""

    name: str
    category: str
    used_by: list[str] = field(default_factory=list)  # app names
    details: list[str] = field(default_factory=list)  # e.g. ["PostGIS", "Cloud SQL"]
    evidence: list[str] = field(default_factory=list)  # files that revealed it


@dataclass
class Stack:
    name: str
    apps: list[App] = field(default_factory=list)
    services: list[Service] = field(default_factory=list)
    ci: list[str] = field(default_factory=list)


def detect_stack(scan_result: ScanResult, files: list[SourceFile]) -> Stack:
    detector = _Detector(scan_result, files)
    return detector.run()


class _Detector:
    def __init__(self, scan_result: ScanResult, files: list[SourceFile]):
        self.root = scan_result.root
        self.manifests = [p.as_posix() for p in scan_result.manifests]
        self.files = files
        self.stack = Stack(name=self.root.name)
        self.services: dict[str, Service] = {}
        self.app_techs: dict[str, list[Tech]] = {}

    def run(self) -> Stack:
        self._find_apps()
        self._services_from_imports()
        self._services_from_compose()
        self._services_from_connection_strings()
        self._firebase_config()
        self._deployments()
        self._ci()
        self._drop_superseded_services()
        self.stack.services = sorted(self.services.values(), key=lambda s: (s.category, s.name))
        return self.stack

    # Apps

    def _find_apps(self) -> None:
        candidates: dict[str, list[str]] = {}
        for manifest in self.manifests:
            path = PurePosixPath(manifest)
            if path.name.lower() in PROJECT_MANIFESTS:
                candidates.setdefault(str(path.parent), []).append(manifest)

        for folder in sorted(candidates, key=lambda f: (f.count("/"), f)):
            techs, versions = [], {}
            for manifest in candidates[folder]:
                found, found_versions = self._read_dependencies(manifest)
                techs.extend(found)
                versions.update(found_versions)
            app = self._make_app(folder, techs, versions)
            if app is None:
                continue
            nested_in = next((a for a in self.stack.apps if is_inside(folder, a.path)), None)
            if nested_in is not None and app.kind == "library":
                continue  # e.g. an e2e test package inside the frontend
            if folder == "." and self.stack.apps and app.kind == "library":
                continue
            self.stack.apps.append(app)
            self.app_techs[app.name] = techs
            for tech in techs:
                if tech.category not in ("framework", "language", "tool"):
                    self._add_service(tech, app.name, candidates[folder][0])

        self._count_files()

    def _make_app(self, folder: str, techs: list[Tech], versions: dict[str, str]) -> App | None:
        sources = [f for f in self.files if is_inside(f.path, folder)]
        if not sources and not techs:
            return None
        roles = [t.role for t in techs if t.category == "framework"]
        kind = next((r for r in ("mobile", "desktop", "web", "api") if r in roles), "library")
        language = _main_language(sources)
        technologies = []
        order = {"framework": 0, "language": 1, "tool": 2}
        for tech in sorted(techs, key=lambda t: order.get(t.category, 3)):
            if tech.category in order and tech.name not in technologies:
                technologies.append(tech.name)
        technologies = [f"{t} {versions[t]}" if t in versions else t for t in technologies]
        language_label = language.capitalize() if language != "typescript" else "TypeScript"
        if versions.get("Java") and language == "java":
            language_label = f"Java {versions['Java']}"
        if language and not any(t.startswith(language_label.split()[0]) for t in technologies):
            technologies.insert(1 if technologies else 0, language_label)
        name = PurePosixPath(folder).name if folder != "." else self.stack.name
        return App(name=name, path=folder, kind=kind, language=language, technologies=technologies)

    def _count_files(self) -> None:
        # The deepest app that contains a file owns it.
        apps = sorted(self.stack.apps, key=lambda a: -a.path.count("/") - (a.path != "."))
        for source in self.files:
            owner = next((a for a in apps if is_inside(source.path, a.path)), None)
            if owner is not None:
                owner.files += 1
                owner.lines += source.line_count

    def _read_dependencies(self, manifest: str) -> tuple[list[Tech], dict[str, str]]:
        name = PurePosixPath(manifest).name.lower()
        text = self._read(manifest)
        if text is None:
            return [], {}
        if name == "pom.xml":
            return _maven_dependencies(text)
        if name == "package.json":
            return _npm_dependencies(text)
        if name in ("build.gradle", "build.gradle.kts"):
            return _gradle_dependencies(text)
        return _python_dependencies(name, text)

    # Services

    def _services_from_imports(self) -> None:
        for source in self.files:
            app = self._app_of(source.path)
            for imported in source.imports:
                tech = catalog.match_import(imported.module)
                if tech is not None:
                    self._add_service(tech, app, source.path)

    def _services_from_compose(self) -> None:
        for manifest in self.manifests:
            if not re.fullmatch(r"(docker-)?compose(\..+)?\.ya?ml", PurePosixPath(manifest).name.lower()):
                continue
            data = self._read_yaml(manifest)
            for definition in (data.get("services") or {}).values() if isinstance(data, dict) else []:
                image = definition.get("image") if isinstance(definition, dict) else None
                tech = catalog.match_image(image) if image else None
                if tech is not None:
                    self._add_service(tech, None, manifest)

    def _services_from_connection_strings(self) -> None:
        for manifest in self.manifests:
            name = PurePosixPath(manifest).name.lower()
            if not (name.startswith("application") or name.startswith(".env")):
                continue
            text = self._read(manifest) or ""
            for marker, tech in catalog.CONNECTION_STRINGS:
                if marker in text:
                    self._add_service(tech, self._app_of(manifest), manifest)

    def _firebase_config(self) -> None:
        if "firebase.json" not in self.manifests:
            return
        try:
            data = json.loads(self._read("firebase.json") or "{}")
        except json.JSONDecodeError:
            return
        if "storage" in data:
            self._add_service(catalog.FIREBASE_STORAGE, None, "firebase.json")
        if "firestore" in data:
            self._add_service(catalog.FIRESTORE, None, "firebase.json")
        if "auth" in data.get("emulators", {}):
            self._add_service(catalog.FIREBASE_AUTH, None, "firebase.json")
        hosting = data.get("hosting")
        for site in hosting if isinstance(hosting, list) else [hosting] if hosting else []:
            public = site.get("public", "")
            app = next((a for a in self.stack.apps if a.path != "." and is_inside(public, a.path)), None)
            app = app or next((a for a in self.stack.apps if a.kind == "web"), None)
            if app is not None:
                _add_once(app.deployments, "Firebase Hosting")

    def _add_service(self, tech: Tech, app: str | None, evidence: str) -> None:
        name, details = tech.name, []
        if tech.name == "PostGIS":
            name, details = "PostgreSQL", ["PostGIS"]
        service = self.services.setdefault(name, Service(name=name, category=tech.category))
        for detail in details:
            _add_once(service.details, detail)
        if app is not None:
            _add_once(service.used_by, app)
        _add_once(service.evidence, evidence)

    def _drop_superseded_services(self) -> None:
        for specific, generic_names in catalog.SUPERSEDES.items():
            if specific not in self.services:
                continue
            for generic in generic_names & self.services.keys():
                for app in self.services.pop(generic).used_by:
                    _add_once(self.services[specific].used_by, app)
        # Services seen only in infrastructure files belong to the apps that use that kind of service.
        for service in self.services.values():
            if not service.used_by and service.category in ("database", "cache", "messaging", "search"):
                service.used_by = [a.name for a in self.stack.apps if a.kind == "api"]

    # Deployment and CI

    def _deployments(self) -> None:
        for manifest in self.manifests:
            path = PurePosixPath(manifest)
            name = path.name.lower()
            folder = str(path.parent)
            if name.startswith("dockerfile"):
                app = self._app_object(folder)
                if app is not None:
                    _add_once(app.deployments, "Docker")
            elif name in ("vercel.json", "netlify.toml", "fly.toml", "render.yaml", "procfile", "app.yaml"):
                target = {"vercel.json": "Vercel", "netlify.toml": "Netlify", "fly.toml": "Fly.io",
                          "render.yaml": "Render", "procfile": "Heroku", "app.yaml": "App Engine"}[name]
                app = self._app_object(folder) or self._first_app("web")
                if app is not None:
                    _add_once(app.deployments, target)

        if any(self._mentions(m, "serving.knative.dev", "gcloud run deploy") for m in self.manifests):
            app = next((a for a in self.stack.apps if "Docker" in a.deployments and a.kind == "api"), None)
            app = app or self._first_app("api")
            if app is not None:
                _add_once(app.deployments, "Cloud Run")
        if any(self._mentions(m, "socket-factory", "cloudsql") for m in self.manifests):
            for service in self.services.values():
                if service.name in ("PostgreSQL", "MySQL"):
                    _add_once(service.details, "Cloud SQL")

    def _ci(self) -> None:
        if any(m.startswith(".github/workflows/") for m in self.manifests):
            self.stack.ci.append("GitHub Actions")
        if ".gitlab-ci.yml" in self.manifests:
            self.stack.ci.append("GitLab CI")

    # Helpers

    def _app_object(self, path: str) -> App | None:
        candidates = [a for a in self.stack.apps if is_inside(path, a.path)]
        return max(candidates, key=lambda a: len(a.path) if a.path != "." else 0, default=None)

    def _app_of(self, path: str) -> str | None:
        app = self._app_object(path)
        return app.name if app else None

    def _first_app(self, kind: str) -> App | None:
        return next((a for a in self.stack.apps if a.kind == kind), None)

    def _mentions(self, manifest: str, *needles: str) -> bool:
        text = self._read(manifest) or ""
        return any(needle in text for needle in needles)

    def _read(self, relative: str) -> str | None:
        path = self.root / relative
        try:
            if path.stat().st_size > MAX_CONFIG_BYTES:
                return None
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def _read_yaml(self, relative: str):
        try:
            return yaml.safe_load(self._read(relative) or "") or {}
        except yaml.YAMLError:
            return {}


def _maven_dependencies(text: str) -> tuple[list[Tech], dict[str, str]]:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return [], {}
    namespace = root.tag.partition("}")[0] + "}" if root.tag.startswith("{") else ""

    def find(element, path):
        return element.find("/".join(namespace + part for part in path.split("/")))

    techs, versions = [], {}
    for dependency in root.iter(namespace + "dependency"):
        artifact = dependency.findtext(namespace + "artifactId", "")
        if dependency.findtext(namespace + "scope", "") in TEST_SCOPES:
            continue
        tech = catalog.match_dependency(artifact)
        if tech is not None:
            techs.append(tech)
    parent = find(root, "parent")
    if parent is not None and parent.findtext(namespace + "artifactId", "") == "spring-boot-starter-parent":
        versions["Spring Boot"] = _major_minor(parent.findtext(namespace + "version", ""))
    java = find(root, "properties/java.version")
    if java is not None and java.text:
        versions["Java"] = java.text.strip()
    return techs, versions


def _npm_dependencies(text: str) -> tuple[list[Tech], dict[str, str]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [], {}
    techs, versions = [], {}
    runtime = data.get("dependencies") or {}
    development = data.get("devDependencies") or {}
    for name, version in [*runtime.items(), *development.items()]:
        tech = catalog.match_dependency(name)
        if tech is None or (name in development and tech.category not in ("language", "tool")):
            continue
        techs.append(tech)
        if tech.category in ("framework", "language") and isinstance(version, str):
            versions.setdefault(tech.name, _major(version))
    return techs, versions


def _gradle_dependencies(text: str) -> tuple[list[Tech], dict[str, str]]:
    techs = []
    for artifact in re.findall(r"['\"][\w.\-]+:([\w.\-]+)(?::[\w.\-]+)?['\"]", text):
        tech = catalog.match_dependency(artifact)
        if tech is not None:
            techs.append(tech)
    return techs, {}


def _python_dependencies(name: str, text: str) -> tuple[list[Tech], dict[str, str]]:
    names: list[str] = []
    if name == "pyproject.toml":
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return [], {}
        names = data.get("project", {}).get("dependencies", [])
        names += list(data.get("tool", {}).get("poetry", {}).get("dependencies", {}))
    elif name in ("requirements.txt", "pipfile", "setup.py"):
        names = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith(("#", "-"))]
    techs = []
    for requirement in names:
        package = re.split(r"[\s<>=!~\[;]", requirement.strip().strip("'\","), maxsplit=1)[0]
        tech = catalog.match_dependency(package)
        if tech is not None:
            techs.append(tech)
    return techs, {}


def _main_language(sources: list[SourceFile]) -> str:
    counts = Counter()
    for source in sources:
        counts[source.language] += source.line_count
    if counts.get("javascript") and counts.get("typescript"):
        counts["typescript"] += counts.pop("javascript")
    return counts.most_common(1)[0][0] if counts else ""


def _add_once(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def _major(version: str) -> str:
    match = re.search(r"\d+", version)
    return match.group(0) if match else ""


def _major_minor(version: str) -> str:
    match = re.match(r"(\d+)(?:\.(\d+))?", version.strip())
    if not match:
        return ""
    return ".".join(part for part in match.groups() if part)
