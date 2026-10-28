"""Pick the parser for each file and keep one broken file from stopping the rest."""

from collections.abc import Callable
from pathlib import Path

from repo_xray.model import SourceFile
from repo_xray.parsers import java, python

Parser = Callable[[bytes, Path], SourceFile]

PARSERS: dict[str, tuple[str, Parser]] = {
    ".py": ("python", python.parse),
    ".java": ("java", java.parse),
}

SUPPORTED_EXTENSIONS = frozenset(PARSERS)


def language_of(path: Path) -> str | None:
    entry = PARSERS.get(path.suffix.lower())
    return entry[0] if entry else None


def parse_file(root: Path, relative_path: Path) -> SourceFile:
    """Parse one file. A broken file is reported in `error` instead of raising."""
    language, parser = PARSERS[relative_path.suffix.lower()]
    try:
        return parser((root / relative_path).read_bytes(), relative_path)
    except SyntaxError as exc:
        error = f"SyntaxError: {exc.msg} (line {exc.lineno})"
    except (ValueError, RecursionError, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    return SourceFile(
        path=relative_path.as_posix(),
        language=language,
        name=relative_path.with_suffix("").as_posix(),
        package=relative_path.parent.as_posix(),
        line_count=0,
        error=error,
    )
