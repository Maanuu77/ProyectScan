import pytest
from PySide6.QtGui import QImage

from repo_xray.export import png
from repo_xray.export.png import add_png_copies, for_qt, svg_to_png
from repo_xray.render.svg import FONT_FAMILY, MONO_FAMILY, Svg

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def small_svg() -> str:
    svg = Svg(120, 40, "#ffffff", "test", "test")
    svg.rect(10, 10, 100, 20, 4, fill="#0969da")
    svg.text(14, 25, "Hello", 12, "#ffffff")
    return svg.to_string()


def test_svg_becomes_a_png_at_double_size():
    data = svg_to_png(small_svg(), "#ffffff")

    assert data.startswith(PNG_SIGNATURE)
    image = QImage.fromData(data, "PNG")
    assert (image.width(), image.height()) == (240, 80)
    assert image.pixelColor(200, 30).name() == "#0969da"  # inside the blue rectangle, right of the text


def test_invalid_svg_is_rejected():
    with pytest.raises(ValueError):
        svg_to_png("<not svg", "#ffffff")


@pytest.fixture
def fonts(monkeypatch):
    """Pretend which fonts this computer has."""

    def install(*families: str) -> None:
        monkeypatch.setattr(png, "_installed_families", lambda: set(families))
        monkeypatch.setattr(png, "_fixed_family", lambda: "Fixed")
        png.installed_family.cache_clear()

    yield install
    png.installed_family.cache_clear()


def code_svg() -> str:
    svg = Svg(120, 40, "#ffffff", "test", "test")
    svg.text(14, 25, "GET /api", 12, "#000000", mono=True)
    return svg.to_string()


def test_qt_is_given_the_first_installed_font_of_each_list(fonts):
    fonts("Arial", "Segoe UI", "Consolas", "Menlo")

    converted = for_qt(code_svg())

    assert 'font-family="Segoe UI"' in converted  # before Arial in the list, as a browser would choose
    assert 'font-family="Menlo"' in converted
    assert "sans-serif" not in converted and "monospace" not in converted


def test_qt_falls_back_to_the_system_fixed_font_and_leaves_unknown_lists(fonts):
    fonts("Some Other Font")

    converted = for_qt(code_svg())

    assert 'font-family="Fixed"' in converted
    assert converted.count("Helvetica") == 1  # the text font list is untouched: Qt picks its default


def test_the_exported_svg_keeps_its_font_lists():
    assert FONT_FAMILY.split(",")[0] in code_svg() and MONO_FAMILY.split(",")[0] in code_svg()


def test_png_copies_are_added_for_diagrams_only():
    bundle = {
        "architecture/images/overview-light.svg": small_svg(),
        "architecture/images/overview-dark.svg": small_svg(),
        "architecture/README.md": "# x",
    }

    add_png_copies(bundle)

    assert sorted(bundle) == [
        "architecture/README.md",
        "architecture/images/overview-dark.svg",
        "architecture/images/overview-light.svg",
        "architecture/png/overview-dark.png",
        "architecture/png/overview-light.png",
    ]
    assert bundle["architecture/png/overview-dark.png"].startswith(PNG_SIGNATURE)
