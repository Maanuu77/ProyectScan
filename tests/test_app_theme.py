import re
from dataclasses import fields

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from repo_xray.app import icons
from repo_xray.app.theme import DARK, LIGHT, PALETTES, STYLESHEET, SYSTEM, Palette, Themes, stylesheet
from repo_xray.app.widgets.common import Button, ElidedLabel, IconButton, Segmented
from repo_xray.render import theme as diagrams


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def luminance(colour: str) -> float:
    def channel(value: int) -> float:
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    c = QColor(colour)
    return 0.2126 * channel(c.red()) + 0.7152 * channel(c.green()) + 0.0722 * channel(c.blue())


def contrast(first: str, second: str) -> float:
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("mode", [LIGHT, DARK])
def test_the_canvas_is_the_diagrams_own_background(mode):
    palette = PALETTES[mode]

    assert palette.canvas == diagrams.THEMES[mode].background  # a diagram sits in the window without an edge
    assert palette.diagram is diagrams.THEMES[mode]


@pytest.mark.parametrize("mode", [LIGHT, DARK])
def test_text_is_readable_on_every_surface(mode):
    p = PALETTES[mode]

    for background in (p.canvas, p.sidebar, p.surface, p.hover, p.active):
        assert contrast(p.text, background) >= 7, background
        assert contrast(p.text_muted, background) >= 4.5, background
    assert contrast(p.accent_on, p.accent) >= 4.5  # the label of a primary button
    assert contrast(p.accent_text, p.accent_soft) >= 4.5  # the selected row
    for tone, soft in ((p.danger, p.danger_soft), (p.warning, p.warning_soft), (p.success, p.success_soft)):
        assert contrast(tone, soft) >= 4.5


def test_the_style_sheet_uses_only_colours_the_palette_has():
    known = {field.name for field in fields(Palette)} | {"font", "mono"}

    used = set(re.findall(r"@([a-z_]+)", STYLESHEET))

    assert used <= known
    for mode in (LIGHT, DARK):
        built = stylesheet(PALETTES[mode])
        assert "@" not in built
        assert PALETTES[mode].border_strong in built and PALETTES[mode].accent in built


def test_longer_token_names_win_over_their_prefixes():
    built = stylesheet(PALETTES[LIGHT])

    assert "_strong" not in built and "_soft" not in built and "_hover" not in built


def test_mode_is_remembered_and_announced(qtbot, settings):
    themes = Themes(settings)
    seen = []
    themes.changed.connect(seen.append)
    assert themes.mode == SYSTEM

    themes.set_mode(DARK)
    themes.set_mode(DARK)  # nothing changes: nothing is announced
    themes.set_mode(LIGHT)

    assert [palette.name for palette in seen] == [DARK, LIGHT][-len(seen):]
    assert seen[-1] is PALETTES[LIGHT] and not themes.is_dark
    assert Themes(settings).mode == LIGHT  # a new session starts where this one ended
    themes.set_mode(SYSTEM)  # leave the application as it was found


def test_toggle_switches_between_light_and_dark(qtbot, settings):
    themes = Themes(settings)
    themes.set_mode(LIGHT)

    themes.toggle()
    assert themes.mode == DARK and themes.is_dark
    themes.toggle()
    assert themes.mode == LIGHT
    themes.set_mode(SYSTEM)


def test_an_unknown_mode_is_refused(settings):
    with pytest.raises(ValueError):
        Themes(settings).set_mode("sepia")
    settings.setValue("theme", "sepia")
    assert Themes(settings).mode == SYSTEM  # a damaged setting falls back instead of failing


def test_the_whole_application_is_restyled(qtbot, settings):
    app = QApplication.instance()
    before = app.styleSheet()
    themes = Themes(settings, app)
    try:
        themes.set_mode(DARK)
        assert PALETTES[DARK].canvas in app.styleSheet()
        assert app.palette().window().color().name() == PALETTES[DARK].canvas
        themes.set_mode(LIGHT)
        assert PALETTES[LIGHT].canvas in app.styleSheet() and PALETTES[DARK].sidebar not in app.styleSheet()
        assert themes.font and themes.mono
    finally:
        themes.set_mode(SYSTEM)
        app.setStyleSheet(before)


@pytest.mark.parametrize("name", sorted(icons.ICONS))
def test_every_icon_draws_something_in_the_colour_asked(qtbot, name):
    image = icons.pixmap(name, "#ff0000", 24, 2.0).toImage()

    assert (image.width(), image.height()) == (48, 48)
    painted = [image.pixelColor(x, y) for x in range(48) for y in range(48) if image.pixelColor(x, y).alpha() > 200]
    assert painted, name
    assert all(c.red() > 200 and c.green() < 60 and c.blue() < 60 for c in painted)


def test_icons_are_remembered(qtbot):
    assert icons.pixmap("search", "#123456", 16, 1.0) is icons.pixmap("search", "#123456", 16, 1.0)
    assert not icons.icon("search", "#123456").isNull()


def test_buttons_change_their_icon_with_the_theme(qtbot, settings):
    themes = Themes(settings)
    themes.set_mode(LIGHT)
    button, primary = IconButton("search", themes, "Find"), Button("Export", themes, "export", "primary")
    qtbot.addWidget(button)
    qtbot.addWidget(primary)
    light = button.icon().pixmap(16, 16).toImage()

    themes.set_mode(DARK)

    assert button.icon().pixmap(16, 16).toImage() != light
    assert button.toolTip() == "Find" and primary.property("variant") == "primary"
    themes.set_mode(SYSTEM)


def test_segmented_announces_clicks_but_not_what_the_code_selects(qtbot):
    control = Segmented([("a", "Overview", ""), ("b", "Features", ""), ("c", "Flows", "")])
    qtbot.addWidget(control)
    seen = []
    control.selected.connect(seen.append)

    control.select("b")
    assert control.current() == "b" and seen == []
    control.button("c").click()
    assert control.current() == "c" and seen == ["c"]
    control.select(None)
    assert control.current() is None


def test_elided_label_shortens_but_keeps_the_whole_text(qtbot):
    text = "C:/Users/someone/projects/a-very-long-folder-name/another-long-folder/project"
    widget = ElidedLabel(text)
    qtbot.addWidget(widget)
    widget.resize(120, 20)
    widget.show()

    assert widget.text() != text and widget.text().endswith("…")
    assert widget.full_text() == text and widget.toolTip() == text
