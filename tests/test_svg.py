import xml.etree.ElementTree as ElementTree

import pytest

from repo_xray.render.svg import MONO_FAMILY, Svg, fit_middle, fit_text, text_width, wrap_text
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


def test_accented_letters_measure_like_their_base_letter():
    assert text_width("Reseñas públicas", 13) == text_width("Resenas publicas", 13)
    assert text_width("Moderación", 13) < text_width("Moderacion", 13) * 1.01  # it used to count 600 per accent


def test_wide_scripts_and_emoji_fill_the_em_square():
    assert text_width("日本語", 10) > text_width("abc", 10) * 1.7
    assert text_width("e\u0301", 14) == text_width("e", 14)  # a combining accent takes no room


def test_monospace_is_measured_per_character():
    assert text_width("iiii", 12, mono=True) == text_width("WWWW", 12, mono=True)
    assert text_width("GET /api", 12, mono=True) == pytest.approx(8 * 0.61 * 12)


def test_fit_middle_keeps_both_ends_of_a_route():
    route = "/api/v1/admin/moderacion/resenas/{resenaId}/revision"

    shortened = fit_middle(route, 220, 12, mono=True)

    assert shortened.startswith("/api/v1") and shortened.endswith("revision") and "…" in shortened
    assert text_width(shortened, 12, mono=True) <= 220
    assert fit_middle("short", 220, 12) == "short"


def test_wrap_text_breaks_long_identifiers_where_they_read_best():
    lines = wrap_text("ResenaPersistenceAdapterImplementation.borrarReportesPendientes", 150, 13, max_lines=4)

    assert len(lines) > 1 and "".join(lines) == "ResenaPersistenceAdapterImplementation.borrarReportesPendientes"
    assert all(text_width(line, 13) <= 150 for line in lines)
    assert all(line[0].isupper() or line[0] == "b" for line in lines)  # cut between words, never inside one


def test_wrap_text_splits_a_word_without_any_break_point():
    lines = wrap_text("x" * 80, 100, 13, max_lines=10)

    assert "".join(lines) == "x" * 80
    assert all(text_width(line, 13) <= 100 for line in lines)


def test_fit_text_is_exact_for_long_strings():
    text = "word " * 400

    shortened = fit_text(text, 300, 13)

    assert text_width(shortened, 13) <= 300 < text_width(shortened[:-1] + "wo…", 13)


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


def test_elements_can_be_named_and_code_is_monospaced():
    svg = Svg(200, 100, "#fff", title="t", description="d")
    svg.rect(10, 10, 50, 20, radius=4, fill="#eee", id="feature-api-orders")
    svg.text(10, 50, "GET /api/orders", 12, "#000", mono=True)

    root = ElementTree.fromstring(svg.to_string())

    assert root.findall(f"{SVG_NS}rect")[1].attrib["id"] == "feature-api-orders"
    assert root.find(f"{SVG_NS}text").attrib["font-family"] == MONO_FAMILY


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
