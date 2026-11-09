"""What the analysis could not do, said plainly.

Static analysis has gaps: a file that does not parse, a request whose
endpoint is not in the project, a flow that stops at the controller.
Hiding them makes the documents look more certain than they are, so every
gap becomes a `Diagnostic` the app and the command line can show.
"""

from dataclasses import dataclass, field

from repo_xray.analysis.features import FeatureMap
from repo_xray.analysis.flows import Flow
from repo_xray.analysis.linking import HttpLink
from repo_xray.analysis.paths import is_test_path
from repo_xray.analysis.stack import Stack
from repo_xray.model import SourceFile
from repo_xray.scanner import ScanResult

ERROR, WARNING, INFO = "error", "warning", "info"
SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}


@dataclass
class Diagnostic:
    severity: str  # ERROR: nothing useful can be shown; WARNING: something is missing; INFO: worth knowing
    code: str  # stable identifier, e.g. "parse-errors"
    title: str  # one line, with the count
    detail: str  # what it means and what the user can do about it
    items: list[str] = field(default_factory=list)  # the files, requests or names concerned


def diagnose(scan: ScanResult, files: list[SourceFile], stack: Stack, links: list[HttpLink],
             features: FeatureMap, flows: list[Flow]) -> list[Diagnostic]:
    found = [d for check in (_sources, _parsing, _stack, _requests, _flows, _features)
             for d in check(scan, files, stack, links, features, flows)]
    return sorted(found, key=lambda d: SEVERITY_ORDER[d.severity])


def _sources(scan, files, stack, links, features, flows):
    if not files:
        yield Diagnostic(ERROR, "no-sources", "No source files found",
                         "repo-xray reads Python, Java, TypeScript and JavaScript. This folder has none of them "
                         "outside ignored folders such as node_modules, build or .venv. "
                         "Choose the folder that holds the project's code.")
    if scan.skipped_large:
        yield Diagnostic(INFO, "skipped-large", f"{_n(len(scan.skipped_large), 'file')} skipped for being too large",
                         "Files over the size limit are usually generated or bundled code. "
                         "Raise max_file_bytes in xray.toml to include them.",
                         [path.as_posix() for path in scan.skipped_large])


def _parsing(scan, files, stack, links, features, flows):
    broken = [f for f in files if f.error]
    if broken:
        yield Diagnostic(WARNING, "parse-errors", f"{_n(len(broken), 'file')} could not be read",
                         "These files have syntax or encoding errors, so their classes, calls and endpoints "
                         "are missing from the diagrams. The rest of the project was analysed.",
                         [f"{f.path}: {f.error}" for f in broken])


def _stack(scan, files, stack, links, features, flows):
    if files and not stack.apps:
        yield Diagnostic(WARNING, "no-apps", "No application was recognised",
                         "repo-xray finds applications through their build files: pom.xml, build.gradle, "
                         "package.json, pyproject.toml or requirements.txt. None was found next to the code.")
    unused = [s.name for s in stack.services if not s.used_by]
    if unused:
        yield Diagnostic(INFO, "unattached-services", f"{_n(len(unused), 'service')} found only in configuration",
                         "They appear in compose or cloud files, but no application imports them, "
                         "so the overview shows them without a connection.", unused)


def _requests(scan, files, stack, links, features, flows):
    linked = {id(link.call) for link in links}
    served = {(link.endpoint_path, link.endpoint.handler, link.endpoint.method) for link in links}
    sources = [f for f in files if not is_test_path(f.path)]
    endpoints = [(f, e) for f in sources for e in f.endpoints]
    unmatched = [f"{f.path}:{c.lineno}  {c.method} {c.url}" for f in sources for c in f.http_calls
                 if id(c) not in linked]
    if unmatched and endpoints:
        yield Diagnostic(WARNING, "unlinked-requests",
                         f"{_n(len(unmatched), 'HTTP request')} could not be linked to an endpoint",
                         "The frontend makes these requests, but no endpoint in the project has a matching "
                         "method and route. They may go to another service, or their URL is built at runtime.",
                         unmatched)
    elif unmatched:
        yield Diagnostic(INFO, "external-requests", f"{_n(len(unmatched), 'HTTP request')} to APIs outside the project",
                         "The project makes HTTP requests but serves no endpoints that repo-xray recognises, "
                         "so they are treated as calls to external APIs.", unmatched)
    if links:
        unused = [f"{e.method} {e.path}  ({f.path})" for f, e in endpoints
                  if (f.path, e.handler, e.method) not in served]
        if unused:
            yield Diagnostic(INFO, "uncalled-endpoints", f"{_n(len(unused), 'endpoint')} not called by the frontend",
                             "No request in the project's frontends reaches these endpoints. They may serve "
                             "other clients, webhooks or admin tools.", unused)


def _flows(scan, files, stack, links, features, flows):
    if files and not flows:
        yield Diagnostic(INFO, "no-flows", "No request flows (level 3)",
                         "Flows start at HTTP endpoints, and repo-xray recognises Spring's (@GetMapping, "
                         "@PostMapping…). None was found, so the documents have levels 1 and 2 only.")
    backend = [(flow, [s for s in flow.steps[flow.http_index or 0:] if s.layer != "service"]) for flow in flows]
    shallow = [f"{flow.method} {flow.route}" for flow, steps in backend if len(steps) <= 1]
    if shallow:
        verb = "stops" if len(shallow) == 1 else "stop"
        yield Diagnostic(INFO, "shallow-flows", f"{_n(len(shallow), 'flow')} {verb} at the entry point",
                         "The handler's calls could not be followed further: calls on local variables or on "
                         "values returned by other calls are not resolved (see the Limitations in the README).",
                         shallow)


def _features(scan, files, stack, links, features, flows):
    whole = [app.name for app in stack.apps
             if [f.key for f in features.of_app(app.name)] == [f"{app.name}/{app.name}"]]
    if whole:
        yield Diagnostic(INFO, "unsplit-apps", f"{_n(len(whole), 'application')} shown as a single feature",
                         "No feature folders (features/, modules/), vertical slices or shared file names were "
                         "found, so the whole application counts as one feature.", whole)
    generated = [f"{f.name}  ({f.app})" for f in features.features if f.description_source == "generated"]
    if generated:
        yield Diagnostic(INFO, "generated-descriptions",
                         f"{_n(len(generated), 'feature')} described with a generated sentence",
                         "The code has no description for them (OpenAPI tag, Javadoc, docstring), so repo-xray "
                         "wrote one from what it found. Use Edit texts to say it in your own words.", generated)


def _n(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
