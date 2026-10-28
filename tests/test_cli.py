import json
import zipfile

from repo_xray.cli import main


def make_project(root):
    (root / "pkg").mkdir()
    (root / "pkg" / "__init__.py").write_text("")
    (root / "pkg" / "service.py").write_text(
        "from .repo import Repo\n"
        "\n"
        "class Service:\n"
        "    def run(self):\n"
        "        return Repo().load()\n"
    )
    (root / "pkg" / "repo.py").write_text("class Repo:\n    def load(self):\n        return 1\n")
    (root / "broken.py").write_text("def nope(:\n")


def test_prints_summary(tmp_path, capsys):
    make_project(tmp_path)

    exit_code = main([str(tmp_path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Files            4" in out
    assert "Classes          2" in out
    assert "Methods          2" in out
    assert "Could not parse 1 file(s):" in out
    assert "broken.py: SyntaxError" in out


def test_writes_json(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    make_project(project)
    output = tmp_path / "analysis.json"

    exit_code = main([str(project), "--json", str(output)])

    assert exit_code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert [f["name"] for f in data["files"]] == ["broken", "pkg", "pkg.repo", "pkg.service"]


def test_missing_folder_fails_cleanly(tmp_path, capsys):
    exit_code = main([str(tmp_path / "missing")])

    assert exit_code == 2
    assert "is not a folder" in capsys.readouterr().err


def test_invalid_config_fails_cleanly(tmp_path, capsys):
    (tmp_path / "xray.toml").write_text("this is = = not toml")

    exit_code = main([str(tmp_path)])

    assert exit_code == 2
    assert "invalid configuration" in capsys.readouterr().err


def test_summary_lists_apps_services_features_and_flows(tmp_path, capsys):
    make_project(tmp_path)

    main([str(tmp_path)])

    out = capsys.readouterr().out
    assert "Apps" in out and "Features" in out and "Flows" in out


def test_exports_a_zip_with_the_documentation(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    make_project(project)
    destination = tmp_path / "out" / "docs.zip"

    exit_code = main([str(project), "--export", str(destination), "--no-png"])

    assert exit_code == 0
    with zipfile.ZipFile(destination) as archive:
        names = archive.namelist()
    assert "HOW-TO-USE.md" in names and "README-snippet.md" in names
    assert "architecture/README.md" in names
    assert not any(name.startswith("architecture/png/") for name in names)
    assert "Documentation written to" in capsys.readouterr().out
