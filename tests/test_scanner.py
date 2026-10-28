from dataclasses import replace
from pathlib import Path

import pytest

from repo_xray.config import Config
from repo_xray.scanner import scan


def make_files(root: Path, *relative_paths: str, content: str = "x = 1\n") -> None:
    for relative in relative_paths:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def as_posix(paths):
    return [p.as_posix() for p in paths]


def test_finds_python_files_sorted_and_relative(tmp_path):
    make_files(tmp_path, "main.py", "pkg/b.py", "pkg/a.py", "README.md", "pkg/data.json")

    result = scan(tmp_path, Config())

    assert as_posix(result.files) == ["main.py", "pkg/a.py", "pkg/b.py"]


def test_skips_default_ignored_and_hidden_dirs(tmp_path):
    make_files(
        tmp_path,
        "app.py",
        ".git/hooks/x.py",
        ".venv/lib/site.py",
        "__pycache__/app.py",
        "node_modules/pkg/x.py",
        ".hidden/tool.py",
        "mylib.egg-info/x.py",
    )

    result = scan(tmp_path, Config())

    assert as_posix(result.files) == ["app.py"]


def test_skips_virtualenv_with_custom_name(tmp_path):
    make_files(tmp_path, "app.py", "my-env/lib/thing.py")
    (tmp_path / "my-env" / "pyvenv.cfg").write_text("home = /usr\n")

    result = scan(tmp_path, Config())

    assert as_posix(result.files) == ["app.py"]


def test_hidden_dirs_kept_when_configured(tmp_path):
    make_files(tmp_path, ".tools/tool.py")

    result = scan(tmp_path, replace(Config(), ignore_hidden_dirs=False))

    assert as_posix(result.files) == [".tools/tool.py"]


def test_large_files_are_reported_not_analysed(tmp_path):
    make_files(tmp_path, "small.py")
    make_files(tmp_path, "big.py", content="x = 1\n" * 100)

    result = scan(tmp_path, replace(Config(), max_file_bytes=50))

    assert as_posix(result.files) == ["small.py"]
    assert as_posix(result.skipped_large) == ["big.py"]


def test_rejects_a_file_as_root(tmp_path):
    make_files(tmp_path, "main.py")

    with pytest.raises(NotADirectoryError):
        scan(tmp_path / "main.py", Config())


def test_finds_java_and_typescript_but_not_generated_files(tmp_path):
    make_files(
        tmp_path,
        "backend/src/main/java/App.java",
        "frontend/src/app/api.ts",
        "frontend/src/app/view.tsx",
        "frontend/src/types.d.ts",
        "frontend/public/vendor.min.js",
        "frontend/src/main.js",
    )

    result = scan(tmp_path, Config())

    assert as_posix(result.files) == [
        "backend/src/main/java/App.java",
        "frontend/src/app/api.ts",
        "frontend/src/app/view.tsx",
        "frontend/src/main.js",
    ]


def test_skips_build_output_and_reports(tmp_path):
    make_files(
        tmp_path,
        "backend/src/App.java",
        "backend/target/classes/Gen.java",
        "frontend/coverage/app/api.ts",
        "frontend/.angular/cache/x.js",
        "frontend/test-results/x.ts",
    )

    result = scan(tmp_path, Config())

    assert as_posix(result.files) == ["backend/src/App.java"]
