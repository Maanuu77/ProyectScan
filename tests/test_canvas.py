import pytest
from PySide6.QtCore import QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QColor

from repo_xray.app.theme import SYSTEM, Themes
from repo_xray.app.widgets.canvas import FIT_ALL, FIT_WIDTH, MAX_FIT, MAX_SCALE, MIN_SCALE, DiagramCanvas
from repo_xray.app.widgets.pageview import MAX_COLUMN, PageView
from repo_xray.render.svg import Svg


@pytest.fixture
def themes(tmp_path):
    manager = Themes(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    yield manager
    manager.set_mode(SYSTEM)


def diagram(width: int = 1000, height: int = 500) -> str:
    svg = Svg(width, height, "#ffffff", "test", "test")
    svg.rect(100, 100, 200, 80, 12, fill="#eeeeee", id="feature-api-orders")
    svg.rect(500, 100, 200, 80, 12, fill="#eeeeee", id="feature-api-catalog")
    svg.rect(520, 110, 40, 40, 8, fill="#dddddd", id="service-postgresql")  # a small part inside the second card
    svg.text(120, 140, "OrderService", 14, "#000000", weight=600)
    svg.text(520, 170, "CatalogService", 14, "#000000")
    svg.text(120, 300, "GET /api/orders", 12, "#000000", mono=True)
    return svg.to_string()


@pytest.fixture
def canvas(qtbot, themes):
    widget = DiagramCanvas(themes)
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    widget.show_svg(diagram(), "#ffffff")
    return widget


def centre_of(canvas, element_id: str) -> QPoint:
    box = next(b for i, b in canvas._regions if i == element_id)
    return canvas._to_widget(box).center().toPoint()


def test_a_diagram_opens_fitted_to_the_width_and_starts_at_the_top(canvas):
    assert canvas.fit_mode == FIT_WIDTH
    assert canvas.scale == pytest.approx(0.6)  # 600 px for a 1000 px diagram
    box = canvas.content_rect()
    assert (box.left(), box.top(), box.width()) == pytest.approx((0, 0, 600))  # shorter than the canvas: not centred down


def test_fitting_never_blows_a_small_diagram_up(qtbot, themes):
    widget = DiagramCanvas(themes)
    qtbot.addWidget(widget)
    widget.resize(900, 600)
    widget.show()

    widget.show_svg(diagram(300, 200), "#ffffff")

    assert widget.scale == MAX_FIT
    assert widget.content_rect().center().x() == pytest.approx(450)  # centred across


def test_fit_all_shows_the_whole_diagram_centred(canvas):
    canvas.show_svg(diagram(500, 2000), "#ffffff")
    assert canvas.content_rect().height() > canvas.height()  # by width: scrolls down

    canvas.fit(FIT_ALL)

    box = canvas.content_rect()
    assert box.height() == pytest.approx(400) and box.center().x() == pytest.approx(300)
    canvas.toggle_fit()
    assert canvas.fit_mode == FIT_WIDTH


def test_zoom_keeps_the_point_under_the_pointer_where_it_is(canvas):
    canvas.zoom_to(1.0)
    anchor = QPointF(200, 150)
    before = (anchor - canvas.content_rect().topLeft()) / canvas.scale

    canvas.zoom_to(2.0, anchor)

    after = (anchor - canvas.content_rect().topLeft()) / canvas.scale
    assert (after.x(), after.y()) == pytest.approx((before.x(), before.y()))
    assert canvas.fit_mode is None  # the user chose a zoom: resizing no longer re-fits


def test_zoom_has_limits_and_steps(canvas, qtbot):
    seen = []
    canvas.zoom_changed.connect(seen.append)

    canvas.zoom_to(100)
    assert canvas.scale == MAX_SCALE
    canvas.zoom_to(0.0001)
    assert canvas.scale == MIN_SCALE
    canvas.zoom_to(0.6)
    canvas.zoom_in()
    assert canvas.scale == 0.67  # the next step up, not a fixed factor
    canvas.zoom_out()
    assert canvas.scale == 0.5
    canvas.zoom_out()
    assert canvas.scale == 0.33
    canvas.actual_size()
    assert canvas.scale == 1.0 and seen[-1] == 1.0


def test_panning_stops_at_the_edges(canvas):
    canvas.zoom_to(2.0)  # 2000 x 1000 in a 600 x 400 canvas

    canvas.pan(10_000, 10_000)
    assert canvas.content_rect().topLeft() == QPointF(0, 0)
    canvas.pan(-10_000, -10_000)
    box = canvas.content_rect()
    assert (box.right(), box.bottom()) == pytest.approx((600, 400))


def test_resizing_refits_until_the_user_zooms(canvas):
    canvas.resize(800, 400)
    assert canvas.scale == pytest.approx(0.8)

    canvas.zoom_to(1.5)
    canvas.resize(500, 400)

    assert canvas.scale == 1.5


def test_the_same_diagram_drawn_again_keeps_the_view(canvas):
    canvas.zoom_to(2.0, QPointF(300, 200))
    origin = canvas.content_rect().topLeft()

    canvas.show_svg(diagram(), "#000000", keep_view=True)

    assert canvas.scale == 2.0 and canvas.content_rect().topLeft() == origin
    canvas.show_svg(diagram(), "#000000")
    assert canvas.fit_mode == FIT_WIDTH and canvas.scale == pytest.approx(0.6)


def test_find_marks_every_label_that_contains_the_text(canvas):
    seen = []
    canvas.matches_changed.connect(lambda current, total: seen.append((current, total)))

    assert canvas.find("service") == 2  # OrderService and CatalogService, whatever the case
    assert seen[-1] == (1, 2)
    canvas.find_next()
    assert seen[-1] == (2, 2)
    canvas.find_next()
    assert seen[-1] == (1, 2)  # round again
    canvas.find_next(-1)
    assert seen[-1] == (2, 2)
    assert canvas.find("/api") == 1  # code labels are searched too
    assert canvas.find("nothing") == 0 and seen[-1] == (0, 0)
    canvas.clear_find()
    assert canvas.match_count() == 0


def test_the_current_match_is_scrolled_into_view(canvas):
    canvas.zoom_to(3.0)
    canvas.pan(10_000, 10_000)  # top-left corner: "CatalogService" at x=520 is far to the right

    canvas.find("CatalogService")

    box = canvas._to_widget(canvas._matches[0])
    assert 0 <= box.left() and box.right() <= canvas.width() and 0 <= box.top() and box.bottom() <= canvas.height()


def test_a_search_survives_a_new_drawing_of_the_diagram(canvas):
    canvas.find("order")

    canvas.show_svg(diagram(), "#0d1117", keep_view=True)  # e.g. the theme changed

    assert canvas.match_count() == 2  # OrderService and /api/orders


def test_clicking_a_card_announces_it_and_dragging_does_not(canvas, qtbot):
    canvas.zoom_to(1.0)
    canvas.pan(10_000, 10_000)
    clicked = []
    canvas.element_clicked.connect(clicked.append)

    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=centre_of(canvas, "feature-api-orders"))
    assert clicked == ["feature-api-orders"]

    start = centre_of(canvas, "feature-api-orders")
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(canvas, start + QPoint(-60, -30))
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=start + QPoint(-60, -30))
    assert clicked == ["feature-api-orders"]  # that was a drag: the diagram moved instead
    assert canvas.content_rect().left() == pytest.approx(-60)


def test_the_smallest_part_under_the_pointer_wins_and_only_clickable_parts_react(canvas):
    canvas.zoom_to(1.0)
    canvas.pan(10_000, 10_000)
    inner = QPointF(centre_of(canvas, "service-postgresql"))

    assert canvas.element_at(inner) == "service-postgresql"
    canvas.set_clickable({"feature-api-catalog"})
    assert canvas.element_at(inner) == "feature-api-catalog"
    assert canvas.element_at(QPointF(centre_of(canvas, "feature-api-orders"))) is None
    assert canvas.element_at(QPointF(5, 5)) is None


def test_keys_zoom_and_move(canvas, qtbot):
    canvas.zoom_to(2.0)
    canvas.pan(10_000, 10_000)

    qtbot.keyClick(canvas, Qt.Key.Key_Down)
    assert canvas.content_rect().top() == -80
    qtbot.keyClick(canvas, Qt.Key.Key_End)
    assert canvas.content_rect().bottom() == pytest.approx(400)
    qtbot.keyClick(canvas, Qt.Key.Key_Minus)
    assert canvas.scale == 1.75
    qtbot.keyClick(canvas, Qt.Key.Key_0)
    assert canvas.fit_mode == FIT_WIDTH


def test_the_canvas_paints_the_diagram_on_its_background(canvas):
    canvas.show_svg(diagram(), "#123456")

    image = canvas.grab().toImage()

    assert image.pixelColor(5, 395).name() == "#123456"  # below the diagram: the canvas colour
    assert image.pixelColor(120, 90) == QColor("#eeeeee")  # inside the first card


def test_an_empty_canvas_does_nothing(qtbot, themes):
    widget = DiagramCanvas(themes)
    qtbot.addWidget(widget)
    widget.resize(300, 200)

    widget.zoom_in()
    widget.fit()
    assert widget.find("x") == 0 and not widget.has_diagram()
    widget.grab()


# The page view


PAGE = """\
# Orders

> Checkout and order history

Part of **api** · [back to the overview](../README.md)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../images/flow-post-api-orders-dark.svg">
  <img alt="Place an order" src="../images/flow-post-api-orders-light.svg">
</picture>
"""


@pytest.fixture
def page(qtbot, themes):
    widget = PageView(themes)
    qtbot.addWidget(widget)
    widget.resize(700, 500)
    widget.show()
    return widget


def test_a_page_shows_its_text_and_draws_its_diagrams(page):
    asked = []

    def source(name: str) -> str:
        asked.append(name)
        return diagram(1000, 500)

    page.show_markdown(PAGE, source)

    assert "Orders" in page.toPlainText() and "Checkout and order history" in page.toPlainText()
    assert "<picture" not in page.toPlainText() and "**" not in page.toPlainText()
    assert asked == ["flow-post-api-orders"]
    image = page._diagram_image("flow-post-api-orders")
    assert 0 < image.width() / image.devicePixelRatio() <= min(MAX_COLUMN, 700)
    assert image.width() / image.height() == pytest.approx(2, abs=0.01)


def test_a_small_diagram_is_not_stretched_to_the_column(page):
    page.show_markdown(PAGE, lambda name: diagram(300, 150))

    image = page._diagram_image("flow-post-api-orders")

    assert image.width() / image.devicePixelRatio() == 300


def test_links_are_announced_as_written(page, qtbot):
    page.show_markdown(PAGE, lambda name: diagram())
    seen = []
    page.link_clicked.connect(seen.append)

    position = next(point for point in (QPoint(x, y) for y in range(60, 400, 4) for x in range(40, 660, 6))
                    if page.anchorAt(point) == "../README.md")
    qtbot.mouseClick(page.viewport(), Qt.MouseButton.LeftButton, pos=position)

    assert seen == ["../README.md"]


def test_a_page_is_drawn_again_in_the_new_theme(page, themes):
    themes.set_mode("light")
    page.show_markdown(PAGE, lambda name: diagram())
    light = page.toHtml()

    themes.set_mode("dark")

    assert page.toHtml() != light and page.markdown() == PAGE
    assert themes.palette.text.lower() in page.toHtml().lower()


def test_a_missing_diagram_leaves_the_page_readable(page):
    page.show_markdown(PAGE, lambda name: None)

    assert "Orders" in page.toPlainText()
    assert page._diagram_image("flow-post-api-orders").isNull()
