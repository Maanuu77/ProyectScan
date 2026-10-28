import zipfile

from repo_xray.export.archive import build_bundle, write_zip
from repo_xray.pipeline import analyse
from tests.conftest import hexagonal_backend


def test_zip_contains_guides_documents_and_png_copies(tmp_path):
    project = tmp_path / "project"
    hexagonal_backend(project)
    bundle = build_bundle(analyse(project))

    path = write_zip(bundle, tmp_path / "docs.zip")

    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        snippet = archive.read("README-snippet.md").decode("utf-8")
        guide = archive.read("HOW-TO-USE.md").decode("utf-8")
    assert {"HOW-TO-USE.md", "README-snippet.md", "architecture/README.md", "architecture/analysis.json",
            "architecture/images/overview-light.svg", "architecture/png/overview-dark.png"} <= names
    assert snippet.startswith("## Architecture\n\nproject is made of an API (`api`)")
    assert 'srcset="docs/architecture/images/overview-dark.svg"' in snippet
    assert "Copy the `architecture` folder" in guide
