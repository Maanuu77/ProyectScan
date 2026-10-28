import json
from dataclasses import replace
from pathlib import Path

from repo_xray.config import Config
from repo_xray.parsers import parse_file
from repo_xray.project import analysis_to_dict, analyze_project
from repo_xray.scanner import scan


def write(root: Path, relative: str, content: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return Path(relative)


def test_syntax_error_is_reported_not_raised(tmp_path):
    relative = write(tmp_path, "broken.py", b"def oops(:\n    pass\n")

    info = parse_file(tmp_path, relative)

    assert info.name == "broken"
    assert info.error.startswith("SyntaxError")
    assert "line 1" in info.error
    assert info.symbols == []


def test_invalid_bytes_are_reported_not_raised(tmp_path):
    relative = write(tmp_path, "binary.py", b"x = 1\x00\xff\xfe\n")

    info = parse_file(tmp_path, relative)

    assert info.error is not None


def test_encoding_declaration_is_respected(tmp_path):
    source = '# -*- coding: latin-1 -*-\ndef café():\n    """Olé."""\n'.encode("latin-1")
    relative = write(tmp_path, "legacy.py", source)

    info = parse_file(tmp_path, relative)

    assert info.error is None
    assert info.symbols[0].docstring == "Olé."


def test_project_analysis_continues_after_a_broken_file(tmp_path):
    write(tmp_path, "a_broken.py", b"class :\n")
    write(tmp_path, "b_ok.py", b"def fine():\n    pass\n")

    files = analyze_project(scan(tmp_path, Config()))

    assert [f.path for f in files] == ["a_broken.py", "b_ok.py"]
    assert files[0].error and not files[1].error
    assert files[1].symbols[0].name == "fine"


def test_analysis_round_trips_through_json(tmp_path):
    write(tmp_path, "app.py", b"import os\n\ndef run():\n    os.getcwd()\n")
    write(tmp_path, "big.py", b"x = 1\n" * 50)
    scan_result = scan(tmp_path, replace(Config(), max_file_bytes=100))

    data = json.loads(json.dumps(analysis_to_dict(scan_result, analyze_project(scan_result))))

    assert data["schema_version"] == 2
    assert data["skipped_large"] == ["big.py"]
    (module,) = data["files"]
    assert module["name"] == "app"
    assert module["language"] == "python"
    assert module["symbols"][0]["qualname"] == "app.run"
    assert module["imports"][0]["module"] == "os"
    assert module["calls"][0] == {"caller": "app.run", "callee": "os.getcwd", "lineno": 4}
