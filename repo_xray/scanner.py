"""Find the Python files of a project, skipping VCS folders, virtualenvs and caches."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from repo_xray.config import Config


@dataclass
class ScanResult:
    root: Path
    files: list[Path] = field(default_factory=list)
    skipped_large: list[Path] = field(default_factory=list)


def scan(root: Path, config: Config) -> ScanResult:
    """Return the `.py` files under `root`, as sorted paths relative to it."""
    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    result = ScanResult(root=root)
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        # Pruning dirnames in place stops os.walk from descending into them.
        dirnames[:] = [d for d in dirnames if not _is_ignored_dir(current / d, config)]

        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = current / name
            relative = path.relative_to(root)
            if path.stat().st_size > config.max_file_bytes:
                result.skipped_large.append(relative)
            else:
                result.files.append(relative)

    result.files.sort(key=Path.as_posix)
    result.skipped_large.sort(key=Path.as_posix)
    return result


def _is_ignored_dir(path: Path, config: Config) -> bool:
    name = path.name
    if name in config.ignored_dirs or name.endswith(".egg-info"):
        return True
    if config.ignore_hidden_dirs and name.startswith("."):
        return True
    # A virtualenv can have any name, but it always contains pyvenv.cfg.
    return (path / "pyvenv.cfg").is_file()
