"""Settings for repo-xray: defaults that an optional xray.toml can extend."""

import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path

CONFIG_FILE = "xray.toml"

DEFAULT_IGNORED_DIRS = frozenset({
    ".git", ".hg", ".svn",
    ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox",
    "node_modules", "build", "dist", "site-packages",
})


@dataclass(frozen=True)
class Config:
    ignored_dirs: frozenset[str] = DEFAULT_IGNORED_DIRS
    ignore_hidden_dirs: bool = True
    max_file_bytes: int = 1_000_000


def load_config(project_root: Path) -> Config:
    """Read xray.toml from the analysed project, if it exists.

    `extra_ignored_dirs` is added to the default ignore list instead of
    replacing it, so a config file cannot accidentally un-ignore `.git`.
    """
    path = project_root / CONFIG_FILE
    if not path.is_file():
        return Config()

    with path.open("rb") as file:
        data = tomllib.load(file)

    config = Config()
    extra_dirs = data.pop("extra_ignored_dirs", [])
    if extra_dirs:
        config = replace(config, ignored_dirs=config.ignored_dirs | frozenset(extra_dirs))

    allowed = {f.name for f in fields(Config)} - {"ignored_dirs"}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Unknown keys in {path}: {', '.join(sorted(unknown))}")
    return replace(config, **data)
