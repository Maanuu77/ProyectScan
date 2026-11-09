from repo_xray.analysis.diagnostics import ERROR, INFO, WARNING
from repo_xray.cli import summarize_analysis
from repo_xray.pipeline import analyse
from tests.conftest import hexagonal_backend, write


def codes(analysis) -> dict[str, str]:
    return {d.code: d.severity for d in analysis.diagnostics}


def by_code(analysis, code):
    return next(d for d in analysis.diagnostics if d.code == code)


def test_an_empty_folder_is_an_error_with_advice(tmp_path):
    analysis = analyse(tmp_path)

    assert codes(analysis) == {"no-sources": ERROR}
    assert "Choose the folder" in by_code(analysis, "no-sources").detail


def test_broken_files_are_listed_with_their_error(tmp_path):
    hexagonal_backend(tmp_path)
    write(tmp_path, {"api/tools/bad.py": "def broken(:\n"})

    diagnostic = by_code(analyse(tmp_path), "parse-errors")

    assert diagnostic.severity == WARNING and diagnostic.title == "1 file could not be read"
    assert diagnostic.items[0].startswith("api/tools/bad.py: SyntaxError")


def test_requests_without_an_endpoint_and_endpoints_without_a_request(tmp_path):
    hexagonal_backend(tmp_path)
    write(tmp_path, {
        "web/package.json": '{"dependencies": {"@angular/core": "^19.0.0"}}',
        "web/src/app/orders.api.ts": """\
            export class OrdersApi {
              constructor(private http: HttpClient) {}
              create() { return this.http.post('/api/orders', {}); }
              stats() { return this.http.get('/api/statistics'); }
            }
        """,
    })

    analysis = analyse(tmp_path)

    unlinked = by_code(analysis, "unlinked-requests")
    assert unlinked.severity == WARNING
    assert unlinked.items == ["web/src/app/orders.api.ts:4  GET /api/statistics"]
    uncalled = by_code(analysis, "uncalled-endpoints")
    assert uncalled.severity == INFO and len(uncalled.items) == 1 and uncalled.items[0].startswith("GET /api/products")


def test_requests_of_a_project_without_endpoints_are_external(tmp_path):
    write(tmp_path, {
        "package.json": '{"dependencies": {"react": "^19.0.0"}}',
        "src/api.ts": "export function load() { return fetch('https://api.example.com/items'); }\n",
    })

    analysis = analyse(tmp_path)

    assert codes(analysis)["external-requests"] == INFO
    assert "unlinked-requests" not in codes(analysis)
    assert codes(analysis)["no-flows"] == INFO


def test_flows_that_stop_at_the_entry_point_are_a_note(tmp_path):
    hexagonal_backend(tmp_path)

    analysis = analyse(tmp_path)

    assert by_code(analysis, "shallow-flows").items == ["GET /api/products"]  # ProductController calls nothing
    assert all(d.severity == INFO for d in analysis.diagnostics)


def test_diagnostics_are_sorted_by_severity_and_printed_by_the_cli(tmp_path):
    hexagonal_backend(tmp_path)
    write(tmp_path, {"api/tools/bad.py": "def broken(:\n"})

    analysis = analyse(tmp_path)
    summary = summarize_analysis(analysis)

    assert analysis.diagnostics[0].severity == WARNING
    assert "Notes:\n  ! 1 file could not be read\n      api/tools/bad.py: SyntaxError" in summary
    assert "\n  - 1 flow stops at the entry point" in summary
