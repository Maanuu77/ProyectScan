"""Large and unusual projects: nothing here should crash, and what cannot be read is reported."""

import xml.etree.ElementTree as ElementTree

import pytest
from PySide6.QtCore import QSettings

from repo_xray.analysis.linking import link_http_calls
from repo_xray.app.theme import LIGHT, SYSTEM, Themes
from repo_xray.app.window import MainWindow
from repo_xray.export.markdown import build_documents
from repo_xray.export.png import renderer_for
from repo_xray.model import Endpoint, HttpCall, SourceFile
from repo_xray.pipeline import analyse
from tests.conftest import POM, write
from tests.svgcheck import overflowing

JAVA = "backend/src/main/java/com/acme"
LONG = "AnExtremelyLongNameThatNobodyWouldChooseButThatSomeGeneratorMight"  # kept under Windows' path limit


def make_project(root, features: int = 12) -> None:
    """A full-stack project with `features` features on each side, plus files that should not be there."""
    files = {
        "README.md": "# Acme\n\nA project made to see how repo-xray copes with odd and numerous files.\n",
        "backend/pom.xml": POM,
        "frontend/package.json": '{"name": "acme-web", "dependencies": {"@angular/core": "^19.0.0"}}',
        "backend/tools/broken.py": "def broken(:\n    pass\n",
        "backend/tools/empty.py": "",
        "frontend/src/app/unclosed.ts": "export class Unclosed { method( { \n",
        "frontend/src/app/long-line.ts": "export const data = [" + ", ".join(str(n) for n in range(20000)) + "];\n",
        "frontend/src/app/features/ñandú/ñandú.page.ts": "@Component({})\nexport class ÑandúPage {}\n",
        f"{JAVA}/weird/web/{LONG}Controller.java":
            f"package com.acme.weird.web;\n@RestController\nclass {LONG}Controller {{ @GetMapping(\"/api/"
            + "/".join(f"segment{n}" for n in range(25)) + "\") Object all() { return null; } }\n",
    }
    for index in range(features):
        name, kind = f"feature{index:03}", f"Feature{index:03}"
        files[f"{JAVA}/{name}/web/{kind}Controller.java"] = f"""\
            package com.acme.{name}.web;
            import com.acme.{name}.application.{kind}Service;
            @RestController
            class {kind}Controller {{
                private final {kind}Service service;
                @GetMapping("/api/{name}") Object list() {{ return service.list(); }}
                @PostMapping("/api/{name}") Object create() {{ return service.list(); }}
            }}
        """
        files[f"{JAVA}/{name}/application/{kind}Service.java"] = f"""\
            package com.acme.{name}.application;
            class {kind}Service {{ public Object list() {{ return null; }} }}
        """
        files[f"frontend/src/app/features/{name}/{name}.api.ts"] = f"""\
            export class {kind}Api {{
              constructor(private http: HttpClient) {{}}
              list() {{ return this.http.get('/api/{name}'); }}
            }}
        """
    write(root, files)
    (root / "backend/tools/binary.py").write_bytes(b"\x00\x01\x02\xff\xfe" * 100)
    (root / "backend/tools/latin1.py").write_bytes("# caf\xe9\nx = 1\n".encode("latin-1"))


@pytest.fixture
def odd_project(tmp_path):
    make_project(tmp_path)
    return tmp_path


def test_odd_files_are_reported_and_the_rest_is_analysed(odd_project):
    analysis = analyse(odd_project)

    broken = {f.path: f.error for f in analysis.files if f.error}
    assert {"backend/tools/broken.py", "backend/tools/binary.py"} <= set(broken)
    assert all("None" not in error for error in broken.values())  # no "(line None)" in what the user reads
    assert len(analysis.features.features) >= 24 and len(analysis.flows) == 25
    assert len(analysis.links) == 12  # every frontend request found its endpoint
    assert "parse-errors" in [d.code for d in analysis.diagnostics]


def test_every_diagram_of_an_odd_project_is_valid_and_keeps_its_text_inside(odd_project):
    bundle = build_documents(analyse(odd_project))

    diagrams = [path for path in bundle if path.endswith("-light.svg")]
    assert len(diagrams) > 20
    for path in diagrams:
        svg = str(bundle[path])
        ElementTree.fromstring(svg)  # well-formed
        assert renderer_for(svg).isValid(), path  # and Qt can draw it
        assert overflowing(svg) == [], path


def test_a_folder_without_build_files_is_one_application(tmp_path):
    write(tmp_path, {
        "main.py": "from helpers.maths import add\n\ndef run():\n    return add(1, 2)\n",
        "helpers/maths.py": '"""Small sums."""\n\ndef add(a, b):\n    return a + b\n',
    })

    analysis = analyse(tmp_path)

    assert [(app.name, app.kind, app.path, app.files) for app in analysis.stack.apps] == [(tmp_path.name, "library", ".", 2)]
    assert analysis.stack.inferred_app and len(analysis.features.features) == 1
    codes = {d.code: d.severity for d in analysis.diagnostics}
    assert codes["no-build-file"] == "info" and "no-apps" not in codes
    assert str(build_documents(analysis)["architecture/images/overview-light.svg"]).startswith("<svg")


def test_a_project_with_a_build_file_is_not_inferred(tmp_path):
    write(tmp_path, {"pyproject.toml": '[project]\nname = "tool"\n', "tool.py": "x = 1\n"})

    analysis = analyse(tmp_path)

    assert not analysis.stack.inferred_app and "no-build-file" not in [d.code for d in analysis.diagnostics]


# Linking many requests to many endpoints


def source(path: str, endpoints=(), calls=()) -> SourceFile:
    return SourceFile(path=path, language="java", name=path, package="", line_count=1,
                      endpoints=[Endpoint(m, p, f"{path}.h{i}", i) for i, (m, p) in enumerate(endpoints)],
                      http_calls=[HttpCall(m, u, f"{path}.c{i}", i) for i, (m, u) in enumerate(calls)])


def linked(files) -> list[tuple[str, str]]:
    return [(link.call.url, f"{link.endpoint.method} {link.endpoint.path}") for link in link_http_calls(files)]


def test_a_request_is_linked_to_the_endpoint_declared_first_among_equals():
    files = [
        source("a/First.java", endpoints=[("GET", "/api/v1/items")]),
        source("b/Second.java", endpoints=[("GET", "/api/v2/items")]),
        source("web/api.ts", calls=[("GET", "{base}/items")]),
    ]

    assert linked(files) == [("{base}/items", "GET /api/v1/items")]


def test_requests_that_end_in_a_parameter_and_routes_that_do_still_meet():
    files = [
        source("a/Items.java", endpoints=[("GET", "/api/items/{id}"), ("GET", "/api/items/mine"), ("ANY", "/api/ping"),
                                          ("DELETE", "/api/items/{id}"), ("GET", "/")]),
        source("web/api.ts", calls=[("GET", "{base}/items/{itemId}"), ("GET", "{base}/items/mine"),
                                    ("POST", "{base}/ping"), ("DELETE", "/api/items/{id}"),
                                    ("GET", "{base}/no/such/route/anywhere")]),
    ]

    assert linked(files) == [
        ("{base}/items/{itemId}", "GET /api/items/{id}"),
        ("{base}/items/mine", "GET /api/items/mine"),  # the literal route wins over the parameter
        ("{base}/ping", "ANY /api/ping"),
        ("/api/items/{id}", "DELETE /api/items/{id}"),
    ]


def test_linking_a_thousand_requests_does_not_compare_each_with_every_endpoint():
    names = [f"thing{n}" for n in range(1000)]
    files = [source("api/Things.java", endpoints=[("GET", f"/api/{name}") for name in names]),
             source("web/api.ts", calls=[("GET", f"{{base}}/{name}") for name in names])]
    compared = []

    import repo_xray.analysis.linking as linking

    original = linking._score

    def counting(*args):
        compared.append(1)
        return original(*args)

    linking._score = counting
    try:
        links = link_http_calls(files)
    finally:
        linking._score = original

    assert len(links) == 1000
    assert len(compared) == 1000  # one candidate per request, not a million comparisons


# The app on the same project


@pytest.fixture
def window(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    themes = Themes(settings)
    themes.set_mode(LIGHT)
    win = MainWindow(themes, settings)
    qtbot.addWidget(win)
    yield win
    themes.set_mode(SYSTEM)


def test_the_app_opens_every_document_of_an_odd_project(qtbot, window, tmp_path):
    project = tmp_path / "acme"
    make_project(project)
    window.resize(1200, 800)
    window.show()

    window.analyse(project)
    task = window.task
    with qtbot.waitSignal(task.finished, timeout=60_000):
        pass
    workspace = window.workspace

    entries = workspace.navigation.entries()
    assert len(entries) > 50
    for entry in entries:
        assert workspace.open(entry.target), entry.title
        assert workspace.title.full_text() == entry.title
    drawn = [path for path in workspace.bundle if path.endswith("-light.svg") and workspace.bundle.is_written(path)]
    dark = [path for path in workspace.bundle if path.endswith("-dark.svg") and workspace.bundle.is_written(path)]
    assert len(drawn) > 20 and len(dark) == 2  # only the theme on show was drawn, plus the two first diagrams
