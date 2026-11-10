"""How many HTTP requests go from each frontend to each backend.

The overview writes that number on a connector and the feature map on the
bridge between its zones, so both ask here and always say the same thing.
"""

from repo_xray.analysis.linking import HttpLink
from repo_xray.analysis.paths import is_inside, is_test_path
from repo_xray.analysis.stack import App, Stack
from repo_xray.model import SourceFile

CLIENT_KINDS = ("web", "mobile", "desktop")


def count_in_app(files: list[SourceFile], app: App, attribute: str) -> int:
    """How many `endpoints` or `http_calls` the app's own files hold, tests aside."""
    return sum(
        len(getattr(f, attribute)) for f in files
        if is_inside(f.path, app.path) and not is_test_path(f.path)
    )


def between_apps(stack: Stack, links: list[HttpLink]) -> dict[tuple[str, str], int]:
    """How many linked HTTP requests go from each app to each other app."""
    apps = sorted(stack.apps, key=lambda a: -len(a.path) if a.path != "." else 0)  # the deepest app owns a file

    def owner(path: str) -> str | None:
        return next((a.name for a in apps if is_inside(path, a.path)), None)

    counts: dict[tuple[str, str], int] = {}
    for link in links:
        pair = (owner(link.call_path), owner(link.endpoint_path))
        if None not in pair and pair[0] != pair[1]:
            counts[pair] = counts.get(pair, 0) + 1
    return counts


def frontend_requests(stack: Stack, files: list[SourceFile],
                      links: list[HttpLink] | None = None) -> dict[tuple[str, str], int | None]:
    """What the connector from each frontend to each backend can say: {(frontend, backend): requests}.

    A number is a count repo-xray stands behind: requests matched to that backend's endpoints or,
    for the only backend of a project, every request its frontend makes (its endpoints may belong
    to a framework repo-xray cannot read). None means the two talk but a number would be a guess.
    A pair that is missing has no connector.
    """
    clients = [a for a in stack.apps if a.kind in CLIENT_KINDS]
    apis = [a for a in stack.apps if a.kind == "api"]
    matched = between_apps(stack, links) if links is not None else {}
    requests: dict[tuple[str, str], int | None] = {}
    for client in clients:
        made = count_in_app(files, client, "http_calls")
        for api in apis:
            pair = (client.name, api.name)
            if matched.get(pair):
                requests[pair] = matched[pair]
            elif len(apis) == 1:
                requests[pair] = made or None
            elif links is None and made:
                requests[pair] = None
    return requests
