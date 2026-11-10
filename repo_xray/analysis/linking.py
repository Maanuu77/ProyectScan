"""Pair each HTTP call made by a frontend with the backend endpoint that serves it.

Routes are compared segment by segment from the end, because the frontend
usually prefixes a base URL the code cannot see (`{this.url}/bancos/{id}`)
while the backend spells the whole path (`/api/v1/bancos/{bancoId}`).
"""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from repo_xray.analysis.paths import is_test_path
from repo_xray.model import Endpoint, HttpCall, SourceFile

_PLACEHOLDER = re.compile(r"\{[^}]*\}|:\w+|\$\{[^}]*\}")


@dataclass
class HttpLink:
    call: HttpCall
    call_path: str  # file that makes the call
    endpoint: Endpoint
    endpoint_path: str  # file that serves it


def link_http_calls(files: list[SourceFile]) -> list[HttpLink]:
    endpoints = _EndpointIndex([(e, f.path) for f in files if not is_test_path(f.path) for e in f.endpoints])
    links = []
    for file in files:
        if is_test_path(file.path):
            continue
        for call in file.http_calls:
            best = _best_endpoint(call, endpoints)
            if best is not None:
                links.append(HttpLink(call, file.path, best[0], best[1]))
    return links


class _EndpointIndex:
    """Endpoints by method and last segment, so a call is compared only with routes it could match.

    Comparing every call with every endpoint is quadratic: a project with a thousand of each
    spent most of its analysis here. A call's last segment must equal the route's, unless one
    of the two is a parameter, so that is what the index is keyed by.
    """

    def __init__(self, endpoints: list[tuple[Endpoint, str]]):
        self._routes: dict[str, dict[str | None, list[tuple[int, Endpoint, str, list[str | None]]]]] = {}
        for order, (endpoint, path) in enumerate(endpoints):
            segments = _segments(endpoint.path)
            if segments:  # the root route has nothing a call could be matched on
                by_last = self._routes.setdefault(endpoint.method, {})
                by_last.setdefault(segments[-1], []).append((order, endpoint, path, segments))

    def candidates(self, method: str, last: str | None):
        """Routes of `method` whose last segment could match `last` (None: the call ends in a parameter)."""
        for served in (method, "ANY"):
            by_last = self._routes.get(served, {})
            if last is None:
                for routes in by_last.values():
                    yield from routes
            else:
                yield from by_last.get(last, ())
                yield from by_last.get(None, ())


def _best_endpoint(call: HttpCall, endpoints: _EndpointIndex) -> tuple[Endpoint, str] | None:
    call_segments, anchored = _call_segments(call.url)
    if call_segments is None:
        return None
    best, best_key = None, (0, 0)
    for order, endpoint, path, segments in endpoints.candidates(call.method, call_segments[-1]):
        score = _score(call_segments, segments, anchored)
        key = (score, -order)  # between equal scores, the endpoint declared first, as before the index
        if score > 0 and key > best_key:
            best, best_key = (endpoint, path), key
    return best


def _call_segments(url: str) -> tuple[list[str | None], bool] | tuple[None, bool]:
    """Segments of the path a call requests; None marks a dynamic segment.

    `anchored` is True when the URL starts with a literal path, so it must
    match the whole route instead of only its end.
    """
    url = url.split("?")[0].split("#")[0]
    anchored = True
    if re.match(r"^\{[^}]*\}", url):
        url = re.sub(r"^\{[^}]*\}", "", url)  # unknown base URL
        anchored = False
    elif "://" in url:
        url = urlsplit(url).path
        anchored = False
    segments = _segments(url)
    if not any(s is not None for s in segments):
        return None, anchored
    return segments, anchored


def _segments(path: str) -> list[str | None]:
    return [None if _PLACEHOLDER.fullmatch(part) else part for part in path.strip("/").split("/") if part]


def _score(call: list[str | None], route: list[str | None], anchored: bool) -> int:
    """How well a call matches a route: literal segments that agree, 0 when they cannot match."""
    if len(call) > len(route) or (anchored and len(call) != len(route)):
        return 0
    score = 0
    for wanted, offered in zip(call, route[len(route) - len(call):]):
        if wanted is not None and offered is not None:
            if wanted != offered:
                return 0
            score += 2
        elif wanted is None and offered is not None:
            score -= 1  # a dynamic value could be `me`, but a literal match is more likely elsewhere
        else:
            score += 1
    # Prefer routes the call covers entirely over longer routes it only ends like.
    return max(score * 10 - (len(route) - len(call)), 0)
