from repo_xray.analysis.linking import link_http_calls
from repo_xray.export.markdown import FOLDER, build_documents
from repo_xray.pipeline import analyse as run_pipeline
from repo_xray.render.requests import count_in_app, frontend_requests
from tests.conftest import analyse, hexagonal_backend, write
from tests.svgcheck import texts

WEB = {
    "web/package.json": '{"dependencies": {"@angular/core": "^19.0.0"}}',
    "web/src/app/orders.api.ts": """\
        export class OrdersApi {
          constructor(private http: HttpClient) {}
          create() { return this.http.post('/api/orders', {}); }
          list() { return this.http.get('/api/products'); }
          stats() { return this.http.get('/api/statistics'); }
        }
    """,
    "web/src/app/orders.api.spec.ts": "it('x', () => fetch('/api/ignored'));\n",
}


def test_counts_leave_tests_out(tmp_path):
    hexagonal_backend(tmp_path)
    write(tmp_path, WEB)
    stack, files = analyse(tmp_path)
    web = next(a for a in stack.apps if a.name == "web")

    assert count_in_app(files, web, "http_calls") == 3


def test_requests_matched_to_endpoints_are_the_number_to_trust(tmp_path):
    hexagonal_backend(tmp_path)
    write(tmp_path, WEB)
    stack, files = analyse(tmp_path)

    assert frontend_requests(stack, files, link_http_calls(files)) == {("web", "api"): 2}  # /api/statistics has no endpoint
    assert frontend_requests(stack, files) == {("web", "api"): 3}  # links unknown: all go to the only backend


def test_the_only_backend_gets_every_request_when_its_endpoints_cannot_be_read(tmp_path):
    write(tmp_path, {
        "web/package.json": '{"dependencies": {"react": "^18.0.0"}}',
        "web/src/api.ts": "export const load = () => fetch('/api/items');\n",
        "api/pyproject.toml": '[project]\nname = "api"\ndependencies = ["fastapi"]\n',
        "api/main.py": "x = 1\n",
    })
    stack, files = analyse(tmp_path)

    assert frontend_requests(stack, files, link_http_calls(files)) == {("web", "api"): 1}


def test_a_frontend_that_requests_nothing_still_talks_to_the_only_backend(shop):
    stack, files = analyse(shop)

    assert frontend_requests(stack, files, []) == {("web", "api"): None}  # drawn, without a number


def test_overview_and_feature_map_say_the_same_number(tmp_path):
    hexagonal_backend(tmp_path)
    write(tmp_path, WEB)

    bundle = build_documents(run_pipeline(tmp_path))

    overview = texts(str(bundle[f"{FOLDER}/images/overview-light.svg"]))
    features = texts(str(bundle[f"{FOLDER}/images/features-light.svg"]))
    assert "REST · 2 calls" in overview and "REST · 2 calls" in features
