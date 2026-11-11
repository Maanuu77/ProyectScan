"""The projects opened lately, remembered between sessions.

Each one keeps what the last analysis found (apps, features, flows), so
the start page can say what a project is before it is opened again. The
list of paths stays in the "recent" setting, as in 1.0; the details live
beside it and a path without details is still shown.
"""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from PySide6.QtCore import QSettings

MAX_RECENT = 8
PATHS, DETAILS = "recent", "recent_details"


@dataclass(frozen=True)
class RecentProject:
    path: str
    name: str = ""  # the project's own name, which may differ from its folder's
    apps: int = 0
    features: int = 0
    flows: int = 0
    opened: float = 0.0  # seconds since the epoch; 0 when unknown

    @property
    def title(self) -> str:
        return self.name or Path(self.path).name

    @property
    def exists(self) -> bool:
        return Path(self.path).is_dir()

    def summary(self) -> str:
        """`2 apps · 15 features · 28 flows`, with only what there is."""
        parts = [(self.apps, "app"), (self.features, "feature"), (self.flows, "flow")]
        return "  ·  ".join(f"{count} {noun}{'' if count == 1 else 's'}" for count, noun in parts if count)


class RecentProjects:
    def __init__(self, settings: QSettings):
        self._settings = settings

    def all(self) -> list[RecentProject]:
        """Most recent first, without folders that no longer exist."""
        details = self._details()
        projects = [details.get(path) or RecentProject(path=path) for path in self._paths()]
        return [project for project in projects if project.exists]

    def remember(self, folder: Path, name: str = "", apps: int = 0, features: int = 0, flows: int = 0) -> None:
        path = str(folder)
        paths = [path, *[p for p in self._paths() if p != path]][:MAX_RECENT]
        details = {p: d for p, d in self._details().items() if p in paths}
        details[path] = RecentProject(path, name, apps, features, flows, time.time())
        self._save(paths, details)

    def forget(self, folder: Path | str) -> None:
        path = str(folder)
        paths = [p for p in self._paths() if p != path]
        self._save(paths, {p: d for p, d in self._details().items() if p in paths})

    def clear(self) -> None:
        self._save([], {})

    def _paths(self) -> list[str]:
        value = self._settings.value(PATHS, [], list)
        return [p for p in value if isinstance(p, str)] if isinstance(value, list) else []

    def _details(self) -> dict[str, RecentProject]:
        try:
            raw = json.loads(self._settings.value(DETAILS, "{}", str) or "{}")
            return {path: RecentProject(**{**fields, "path": path}) for path, fields in raw.items()}
        except (ValueError, TypeError, AttributeError):
            return {}  # a damaged setting only loses the details, never the list

    def _save(self, paths: list[str], details: dict[str, RecentProject]) -> None:
        self._settings.setValue(PATHS, paths)
        self._settings.setValue(DETAILS, json.dumps({path: asdict(d) for path, d in details.items()}))


def ago(moment: float, now: float | None = None) -> str:
    """`just now`, `5 minutes ago`, `yesterday`, `3 weeks ago`: how long since `moment`."""
    if not moment:
        return ""
    seconds = max((now if now is not None else time.time()) - moment, 0)
    if seconds < 90:
        return "just now"
    for limit, unit, length in ((3600, "minute", 60), (86400, "hour", 3600), (7 * 86400, "day", 86400),
                                (35 * 86400, "week", 7 * 86400), (365 * 86400, "month", 30 * 86400)):
        if seconds < limit:
            count = max(round(seconds / length), 1)
            if unit == "day" and count == 1:
                return "yesterday"
            return f"{count} {unit}{'' if count == 1 else 's'} ago"
    count = max(round(seconds / (365 * 86400)), 1)
    return f"{count} year{'' if count == 1 else 's'} ago"
