import os
import sys
from pathlib import Path

import pytest

from repo_xray.config import Config
from repo_xray.fs import extended
from repo_xray.pipeline import analyse
from repo_xray.scanner import scan

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="the 260-character limit is a Windows rule")


@windows_only
@pytest.mark.parametrize(("path", "expected"), [
    (r"C:\code\shop", r"\\?\C:\code\shop"),
    (r"\\?\C:\code\shop", r"\\?\C:\code\shop"),
    (r"\\server\share\shop", r"\\?\UNC\server\share\shop"),
])
def test_extended_paths_on_windows(path, expected):
    assert str(extended(Path(path))) == expected


@pytest.mark.skipif(os.name == "nt", reason="other systems have no such limit")
def test_paths_are_unchanged_elsewhere():
    assert extended(Path("/code/shop")) == Path("/code/shop")


@windows_only
def test_projects_deeper_than_260_characters_are_analysed(tmp_path):
    deep = Path(*["a-rather-long-folder-name"] * 12)  # about 310 characters below tmp_path
    source = extended(tmp_path / deep / "Order.java")
    source.parent.mkdir(parents=True)
    source.write_text("package shop;\nclass Order { void pay() {} }\n", encoding="utf-8")
    assert len(str(tmp_path / deep / "Order.java")) > 260

    analysis = analyse(tmp_path)

    assert [f.path for f in analysis.files] == [(deep / "Order.java").as_posix()]
    assert analysis.files[0].error is None


def test_unreadable_files_are_skipped(tmp_path, monkeypatch):
    (tmp_path / "ok.py").write_text("x = 1\n")
    (tmp_path / "locked.py").write_text("x = 1\n")
    real_stat = Path.stat

    def stat(self, *args, **kwargs):
        if self.name == "locked.py":
            raise PermissionError("locked")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)

    assert [p.as_posix() for p in scan(tmp_path, Config()).files] == ["ok.py"]
