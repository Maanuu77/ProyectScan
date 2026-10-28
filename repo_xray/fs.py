"""File-system helpers that also work with very deep folders on Windows."""

import os
from pathlib import Path

_EXTENDED = "\\\\?\\"


def extended(path: Path) -> Path:
    """On Windows, the `\\\\?\\` form of an absolute path, which is not limited to 260 characters.

    Deeply nested projects (Maven test packages, monorepos) easily exceed that
    limit, and the classic form then fails with "path not found".
    """
    if os.name != "nt":
        return path
    text = str(path)
    if text.startswith(_EXTENDED):
        return path
    if text.startswith("\\\\"):  # a network share: \\server\share -> \\?\UNC\server\share
        return Path(_EXTENDED + "UNC\\" + text[2:])
    return Path(_EXTENDED + text)
