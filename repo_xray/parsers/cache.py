"""Remember parsed files, so analysing a project again only reads what changed.

Changing the language or a description in the app runs the whole analysis
again; with the cache that costs a `stat` per file instead of reading and
parsing every one. Parsed files are never modified after parsing, so the
same objects can serve several analyses.
"""

from pathlib import Path

from repo_xray.fs import extended
from repo_xray.model import SourceFile

Stamp = tuple[int, int]  # (size in bytes, modification time in nanoseconds)


class ParseCache:
    def __init__(self):
        self._entries: dict[tuple[str, str], tuple[Stamp, SourceFile]] = {}
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._entries)

    @staticmethod
    def stamp(root: Path, relative_path: Path) -> Stamp | None:
        """What identifies this version of the file, or None when it cannot be read."""
        try:
            status = extended(root / relative_path).stat()
        except OSError:
            return None
        return status.st_size, status.st_mtime_ns

    def lookup(self, root: Path, relative_path: Path, stamp: Stamp | None) -> SourceFile | None:
        entry = self._entries.get((str(root), relative_path.as_posix()))
        if entry is not None and stamp is not None and entry[0] == stamp:
            self.hits += 1
            return entry[1]
        self.misses += 1
        return None

    def store(self, root: Path, relative_path: Path, stamp: Stamp | None, file: SourceFile) -> None:
        if stamp is not None and file.error is None:  # a failure may be passing: try again next time
            self._entries[(str(root), relative_path.as_posix())] = (stamp, file)

    def forget(self, root: Path) -> None:
        """Drop everything remembered about one project."""
        prefix = str(root)
        self._entries = {key: value for key, value in self._entries.items() if key[0] != prefix}
