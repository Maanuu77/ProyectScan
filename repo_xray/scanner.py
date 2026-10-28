"""Find the source files of a project, skipping VCS folders, virtualenvs, caches and build output."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from repo_xray.config import Config

SOURCE_EXTENSIONS = frozenset({".py", ".java", ".ts", ".tsx", ".js", ".jsx", ".mjs"})
# Generated or bundled files that would only add noise.
SKIPPED_SUFFIXES = (".d.ts", ".min.js")

# Build, dependency, container, cloud and CI files that reveal the tech stack.
MANIFEST_NAMES = frozenset({
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
    "package.json", "angular.json", "pyproject.toml", "requirements.txt", "setup.py", "pipfile",
    "firebase.json", "vercel.json", "netlify.toml", "fly.toml", "render.yaml", "procfile",
    "app.yaml", "capacitor.config.json", "capacitor.config.ts", ".gitlab-ci.yml",
})
MANIFEST_SUFFIXES = (".yml", ".yaml", ".sh")
# Hidden folders that hold useful configuration, such as CI workflows.
ALLOWED_HIDDEN_DIRS = frozenset({".github"})


@dataclass
class ScanResult:
    root: Path
    files: list[Path] = field(default_factory=list)
    skipped_large: list[Path] = field(default_factory=list)
    manifests: list[Path] = field(default_factory=list)


def scan(root: Path, config: Config) -> ScanResult:
    """Return the source files under `root`, as sorted paths relative to it."""
    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    result = ScanResult(root=root)
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        # Pruning dirnames in place stops os.walk from descending into them.
        dirnames[:] = [d for d in dirnames if not _is_ignored_dir(current / d, config)]

        for name in filenames:
            path = current / name
            relative = path.relative_to(root)
            if _is_manifest(name):
                result.manifests.append(relative)
            if not _is_source_file(name):
                continue
            if path.stat().st_size > config.max_file_bytes:
                result.skipped_large.append(relative)
            else:
                result.files.append(relative)

    result.files.sort(key=Path.as_posix)
    result.skipped_large.sort(key=Path.as_posix)
    result.manifests.sort(key=Path.as_posix)
    return result


def _is_source_file(name: str) -> bool:
    lowered = name.lower()
    return Path(lowered).suffix in SOURCE_EXTENSIONS and not lowered.endswith(SKIPPED_SUFFIXES)


def _is_manifest(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered in MANIFEST_NAMES
        or lowered.startswith("dockerfile")
        or lowered.endswith(MANIFEST_SUFFIXES)
        or (lowered.startswith("application") and lowered.endswith(".properties"))
    )


def _is_ignored_dir(path: Path, config: Config) -> bool:
    name = path.name
    if name in config.ignored_dirs or name.endswith(".egg-info"):
        return True
    if config.ignore_hidden_dirs and name.startswith(".") and name not in ALLOWED_HIDDEN_DIRS:
        return True
    # A virtualenv can have any name, but it always contains pyvenv.cfg.
    return (path / "pyvenv.cfg").is_file()
