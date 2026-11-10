"""Pick the parser for each file and keep one broken file from stopping the rest."""

from collections.abc import Callable
from pathlib import Path

from repo_xray.fs import extended
from repo_xray.model import SourceFile
from repo_xray.parsers import java, python, typescript

Parser = Callable[[bytes, Path], SourceFile]

PARSERS: dict[str, tuple[str, Parser]] = {
    ".py": ("python", python.parse),
    ".java": ("java", java.parse),
    ".ts": ("typescript", typescript.parse),
    ".tsx": ("typescript", typescript.parse),
    ".js": ("javascript", typescript.parse),
    ".jsx": ("javascript", typescript.parse),
    ".mjs": ("javascript", typescript.parse),
}

SUPPORTED_EXTENSIONS = frozenset(PARSERS)


def language_of(path: Path) -> str | None:
    entry = PARSERS.get(path.suffix.lower())
    return entry[0] if entry else None


def read_source(root: Path, relative_path: Path) -> bytes | OSError:
    """The file's bytes, or the error that kept it from being read. Safe to call from several threads."""
    try:
        return extended(root / relative_path).read_bytes()
    except OSError as exc:
        return exc


def parse_source(data: bytes | OSError, relative_path: Path) -> SourceFile:
    """Parse what `read_source` returned. A broken file is reported in `error` instead of raising."""
    language, parser = PARSERS[relative_path.suffix.lower()]
    try:
        if isinstance(data, OSError):
            raise data
        return parser(data, relative_path)
    except SyntaxError as exc:
        error = f"SyntaxError: {exc.msg}" + (f" (line {exc.lineno})" if exc.lineno else "")
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


def parse_file(root: Path, relative_path: Path) -> SourceFile:
    """Read and parse one file. A broken file is reported in `error` instead of raising."""
    return parse_source(read_source(root, relative_path), relative_path)
