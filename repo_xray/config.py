"""Settings for repo-xray: defaults that an optional xray.toml can extend.

Besides analysis settings, xray.toml holds the user's own words (ADR-0011):
the documents' language, the project description and a name and
description per feature. They always win over what repo-xray finds.
"""

import json
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

CONFIG_FILE = "xray.toml"
LANGUAGES = ("en", "es")

DEFAULT_IGNORED_DIRS = frozenset({
    ".git", ".hg", ".svn",
    ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox",
    "node_modules", "build", "dist", "site-packages",
    # Build output and generated reports of Java and JavaScript tooling.
    "target", "coverage", "test-results", "playwright-report",
    ".angular", ".next", ".nuxt", ".gradle", ".mvn",
})

HEADER = """\
# repo-xray settings for this project.
# Texts written here replace the ones repo-xray finds in the code; the app keeps this file up to date.
"""


@dataclass(frozen=True)
class FeatureText:
    name: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class Config:
    ignored_dirs: frozenset[str] = DEFAULT_IGNORED_DIRS
    ignore_hidden_dirs: bool = True
    max_file_bytes: int = 1_000_000
    language: str | None = None  # None: detected from the code
    description: str | None = None  # replaces the project description
    features: Mapping[str, FeatureText] = field(default_factory=dict)  # by feature key, e.g. "web/auth"


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
    config = replace(config, features=_feature_texts(data.pop("features", {}), path))

    allowed = {f.name for f in fields(Config)} - {"ignored_dirs", "features"}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Unknown keys in {path}: {', '.join(sorted(unknown))}")
    if data.get("language") not in (None, *LANGUAGES):
        raise ValueError(f"language in {path} must be one of {', '.join(LANGUAGES)}")
    return replace(config, **data)


def save_texts(project_root: Path, language: str | None, description: str | None,
               features: Mapping[str, FeatureText]) -> Path:
    """Write the user's texts to xray.toml, keeping any other setting already in it."""
    path = project_root / CONFIG_FILE
    data = {}
    if path.is_file():
        with path.open("rb") as file:
            data = tomllib.load(file)
    for key, value in (("language", language), ("description", description)):
        if value:
            data[key] = value
        else:
            data.pop(key, None)
    tables = {}
    for key, text in sorted(features.items()):
        entry = {k: v for k, v in (("name", text.name), ("description", text.description)) if v}
        if entry:
            tables[key] = entry
    if tables:
        data["features"] = tables
    else:
        data.pop("features", None)
    path.write_text(HEADER + _to_toml(data), encoding="utf-8")
    return path


def _feature_texts(tables: object, path: Path) -> dict[str, FeatureText]:
    if not isinstance(tables, dict):
        raise ValueError(f"features in {path} must be a table")
    texts = {}
    for key, entry in tables.items():
        unknown = set(entry) - {"name", "description"} if isinstance(entry, dict) else {"(not a table)"}
        if unknown:
            raise ValueError(f"Unknown keys for feature {key!r} in {path}: {', '.join(sorted(unknown))}")
        texts[key] = FeatureText(name=entry.get("name"), description=entry.get("description"))
    return texts


def _to_toml(data: dict) -> str:
    """Enough TOML for this file: strings, numbers, booleans, string lists and the features tables."""
    lines, tables = [], []
    for key, value in data.items():
        if isinstance(value, dict):
            tables.append((key, value))
        else:
            lines.append(f"{key} = {_value(value)}")
    for name, table in tables:
        for key, entry in table.items():
            lines += ["", f"[{name}.{_value(key)}]"]
            lines += [f"{k} = {_value(v)}" for k, v in entry.items()]
    return "\n".join(lines) + "\n"


def _value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list | tuple | set | frozenset):
        return "[" + ", ".join(_value(v) for v in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)  # a JSON string is a valid TOML basic string
