import pytest
from PySide6.QtGui import QImage

from repo_xray.export.png import add_png_copies, svg_to_png
from repo_xray.render.svg import Svg

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
