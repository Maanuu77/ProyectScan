import pytest

from repo_xray.render import components as c
from repo_xray.render import ids
from repo_xray.render import theme as t
from repo_xray.render.svg import Svg, text_width
from repo_xray.render.theme import DARK, LIGHT
from tests.svgcheck import SVG, box, by_id, overflowing, parse, texts


def canvas(width: float = 600, height: float = 300) -> Svg:
    return Svg(width, height, LIGHT.background, "t", "d")


def test_header_marks_the_level_and_returns_where_the_content_starts():
    svg = canvas()

    bottom = c.header(svg, LIGHT, 2, "WHAT DOES IT DO?", c.title_lines("shop", 600))

    rects = [r for r in parse(svg.to_string()).iter(f"{SVG}rect")][1:4]  # after the background
    assert [r.attrib["fill"] for r in rects] == [LIGHT.border, LIGHT.text, LIGHT.border]  # the second of three
    assert texts(svg.to_string()) == ["WHAT DOES IT DO?", "shop"]
    assert bottom == c.header_bottom(1) > c.TITLE_Y


def test_a_long_title_wraps_to_the_lines_it_is_given():
    title = "A title that says a great deal more than one line of a narrow diagram could ever hold"

    assert len(c.title_lines(title, 600, max_lines=1)) == 1
    two = c.title_lines(title, 600, max_lines=2)
    assert len(two) == 2 and all(text_width(line, t.TITLE, 700) <= 600 - c.PAD * 2 for line in two)
    assert c.header_bottom(2) == c.header_bottom(1) + c.TITLE_LINE


def test_footer_shows_a_note_or_a_legend_and_always_the_credit():
    note, legend = canvas(), canvas()

    c.footer(note, LIGHT, 600, 300, "CI  ·  GitHub Actions", "Generated with repo-xray")
    c.footer(legend, LIGHT, 600, 300, None, "Generated with repo-xray", [("#ff0000", "Entry points"), ("#00ff00", "Data")])

    assert texts(note.to_string()) == ["Generated with repo-xray", "CI  ·  GitHub Actions"]
    assert texts(legend.to_string()) == ["Generated with repo-xray", "Entry points", "Data"]
    assert overflowing(note.to_string(), margin=c.PAD) == []


def test_a_legend_that_does_not_fit_is_cut_at_a_whole_entry():
    svg = canvas(width=360)

    c.footer(svg, LIGHT, 360, 300, None, "Generated with repo-xray", [("#f00", "Entry points"), ("#0f0", "Application logic")])

    assert "Application logic" not in texts(svg.to_string())
    assert overflowing(svg.to_string(), margin=c.PAD) == []


def test_chip_and_pill_report_the_width_they_draw():
    svg = canvas()

    assert c.chip(svg, LIGHT, 10, 10, "Spring Boot 3.4") == c.chip_width("Spring Boot 3.4")
    assert c.chip(svg, LIGHT, 10, 50, "Orders", dot="#0969da") == c.chip_width("Orders", dot=True)
    assert c.pill(svg, LIGHT, 300, 100, "reads & writes") == c.pill_width("reads & writes")
    assert c.chip_width("Orders", dot=True) > c.chip_width("Orders")


@pytest.mark.parametrize("method, accent", [("GET", "api"), ("POST", "desktop"), ("PUT", "mobile"),
                                             ("DELETE", "cache"), ("ANY", "neutral")])
def test_method_badge_is_coloured_by_what_the_request_does(method, accent):
    for theme in (LIGHT, DARK):
        svg = Svg(200, 60, theme.background, "t", "d")

        c.method_badge(svg, theme, 10, 10, method)

        badge = list(parse(svg.to_string()).iter(f"{SVG}rect"))[1]
        label = parse(svg.to_string()).find(f"{SVG}text")
        assert badge.attrib["fill"] == theme.accent(accent).soft
        assert label.text == method and label.attrib["fill"] == theme.accent(accent).strong


def test_route_pill_keeps_both_ends_of_a_route_that_is_too_long():
    svg = canvas()
    route = "/api/v1/admin/moderation/reviews/{reviewId}/reports/{reportId}/resolution"

    width = c.route_pill(svg, LIGHT, 20, 50, "DELETE", route, max_width=260)

    assert width == 260 == c.route_width("DELETE", route, 260)
    shown = texts(svg.to_string())[-1]
    assert shown.startswith("/api/v1") and shown.endswith("resolution") and "…" in shown
    pill = list(parse(svg.to_string()).iter(f"{SVG}rect"))[1]
    assert box(pill)[2] == 260


def test_polyline_rounds_its_corners_and_ends_in_an_arrow():
    svg = canvas()

    c.polyline(svg, [(10, 10), (100, 10), (100, 80)], "#000")

    root = parse(svg.to_string())
    path = root.find(f"{SVG}path").attrib["d"]
    assert path.startswith("M 10.0 10.0 L 90.0 10.0 Q 100.0 10.0 100.0 20.0")
    assert path.endswith("L 100.0 75.0")  # the line stops inside the arrow head
    tip = root.find(f"{SVG}polygon").attrib["points"].split()[0]
    assert tip == "100,80"


def test_curve_point_follows_the_curve_from_end_to_end():
    assert c.curve_point(0, 0, 100, 50, 0) == (0, 0)
    assert c.curve_point(0, 0, 100, 50, 1) == (100, 50)
    assert c.curve_point(0, 0, 100, 50, 0.5) == pytest.approx((50, 25))


def test_card_carries_its_id():
    svg = canvas()

    c.card(svg, LIGHT, 10, 10, 200, 80, ids.feature_id("backend/Reseñas"))

    assert box(by_id(svg.to_string(), "feature-backend-resenas")) == (10, 10, 200, 80)


@pytest.mark.parametrize("element_id, expected", [
    (ids.app_id("Shop Web"), ("app", "shop-web")),
    (ids.service_id("Firebase Auth"), ("service", "firebase-auth")),
    (ids.feature_id("backend/Reseñas"), ("feature", "backend-resenas")),
    (ids.step_id(3, "backend/resena"), ("feature", "backend-resena")),  # a step leads to its feature
    (ids.step_id(2, None), None),  # code outside any feature leads nowhere
    ("something-else", None),
])
def test_ids_say_what_they_stand_for(element_id, expected):
    assert ids.parse(element_id) == expected


def test_slug_is_safe_for_ids_and_file_names():
    assert ids.slug("backend/Reseñas & más") == "backend-resenas-mas"
    assert ids.slug("***") == "x"
