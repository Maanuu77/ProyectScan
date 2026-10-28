from repo_xray.analysis.linking import link_http_calls
from repo_xray.model import Endpoint, HttpCall, SourceFile


def backend(*routes: tuple[str, str]) -> SourceFile:
    endpoints = [Endpoint(method, path, f"api.Controller.h{i}", i) for i, (method, path) in enumerate(routes)]
    return SourceFile("api/Controller.java", "java", "api.Controller", "api", 10, endpoints=endpoints)


def frontend(*calls: tuple[str, str], path: str = "web/src/api.ts") -> SourceFile:
    http_calls = [HttpCall(method, url, f"web.api.c{i}", i) for i, (method, url) in enumerate(calls)]
    return SourceFile(path, "typescript", "web/src/api", "web/src", 10, http_calls=http_calls)


def pairs(files):
    return [(link.call.url, link.endpoint.path) for link in link_http_calls(files)]


def test_base_url_placeholder_matches_the_end_of_the_route():
    files = [backend(("GET", "/api/v1/bancos/{bancoId}/resenas"), ("GET", "/api/v1/bancos/{id}")),
             frontend(("GET", "{this.url}/bancos/{id}/resenas"))]

    assert pairs(files) == [("{this.url}/bancos/{id}/resenas", "/api/v1/bancos/{bancoId}/resenas")]


def test_literal_segments_beat_parameters():
    files = [backend(("GET", "/api/usuarios/{id}"), ("GET", "/api/usuarios/me")),
             frontend(("GET", "{base}/usuarios/me"), ("GET", "{base}/usuarios/{userId}"))]

    assert pairs(files) == [("{base}/usuarios/me", "/api/usuarios/me"),
                            ("{base}/usuarios/{userId}", "/api/usuarios/{id}")]


def test_method_must_match_unless_the_route_accepts_any():
    files = [backend(("POST", "/api/orders"), ("ANY", "/api/legacy")),
             frontend(("GET", "/api/orders"), ("DELETE", "/api/legacy"))]

    assert pairs(files) == [("/api/legacy", "/api/legacy")]


def test_literal_paths_must_match_the_whole_route():
    files = [backend(("GET", "/api/v1/orders"), ("GET", "/orders")),
             frontend(("GET", "/orders"), ("GET", "https://shop.example.com/api/v1/orders?page=2"))]

    assert pairs(files) == [("/orders", "/orders"),
                            ("https://shop.example.com/api/v1/orders?page=2", "/api/v1/orders")]


def test_calls_that_cannot_be_matched_are_left_out():
    files = [backend(("GET", "/api/orders")),
             frontend(("GET", "{url}"), ("GET", "{base}/invoices")),
             frontend(("GET", "/api/orders"), path="web/src/api.spec.ts")]

    assert pairs(files) == []
