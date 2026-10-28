import xml.etree.ElementTree as ElementTree

import pytest

from repo_xray.render.svg import Svg, fit_text, text_width, wrap_text
from repo_xray.render.theme import DARK, LIGHT, icon

SVG_NS = "{http://www.w3.org/2000/svg}"


def test_text_width_grows_with_length_size_and_weight():
    assert text_width("iiii", 14) < text_width("WWWW", 14)
    assert text_width("Benchify", 14) < text_width("Benchify", 20)
    assert text_width("Benchify", 14) < text_width("Benchify", 14, weight=600)
    assert text_width("ñandú", 14) > 0


def test_fit_text_adds_an_ellipsis_only_when_needed():
    assert fit_text("short", 200, 14) == "short"
    shortened = fit_text("A much longer label than the box allows", 120, 14)
    assert shortened.endswith("…")
    assert text_width(shortened, 14) <= 120


def test_wrap_text_respects_width_and_line_limit():
    lines = wrap_text("Finds benches near you and lets people rate them and save favourites", 160, 13, max_lines=2)

    assert len(lines) == 2
    assert all(text_width(line, 13) <= 160 for line in lines)
    assert lines[-1].endswith("…")


def test_svg_is_well_formed_and_escapes_text():
    svg = Svg(200, 100, "#fff", title="A & B", description="<desc>")
    svg.rect(10, 10, 50, 20, radius=4, fill="#eee", stroke="#000", stroke_width=1.5)
    svg.text(10, 50, "Fish & <chips>", 14, "#000", weight=600, anchor="middle")
    svg.path("M 0 0 L 10 10", fill="none", stroke="#000")
    svg.group_start(opacity=0.5)
    svg.circle(5, 5, 2, fill="#000")
    svg.group_end()

    root = ElementTree.fromstring(svg.to_string())

    assert root.attrib["viewBox"] == "0 0 200 100"
    assert root.find(f"{SVG_NS}title").text == "A & B"
    text = root.find(f"{SVG_NS}text")
    assert text.text == "Fish & <chips>"
    assert text.attrib["text-anchor"] == "middle"
    assert text.attrib["font-weight"] == "600"
    assert root.findall(f"{SVG_NS}rect")[1].attrib["stroke-width"] == "1.5"


@pytest.mark.parametrize("kind", ["users", "web", "api", "mobile", "desktop", "database", "auth",
                                  "storage", "cache", "messaging", "search", "deploy", "library"])
def test_every_icon_draws_valid_svg(kind):
    svg = Svg(24, 24, "#fff", "icon", "icon")
    icon(svg, kind, 0, 0, 24, "#000")

    root = ElementTree.fromstring(svg.to_string())

    assert len(root) > 3  # title, desc, background and at least one shape


def test_themes_define_the_same_accents():
    assert LIGHT.accents.keys() == DARK.accents.keys()
    assert LIGHT.accent("unknown") == LIGHT.accents["neutral"]
