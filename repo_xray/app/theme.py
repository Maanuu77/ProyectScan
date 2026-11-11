"""The app's design system: colours, type and the style sheet built from them.

One `Palette` per mode. Everything the app draws takes its colours from the
current palette, so switching between light and dark changes the whole
window at once: chrome, dialogs, menus, pages and the diagram on show.
The canvas colour is the diagrams' own background, so a diagram sits in
the window without a visible edge.
"""

import re
from dataclasses import dataclass, fields

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from repo_xray.render import theme as diagrams

SYSTEM, LIGHT, DARK = "system", "light", "dark"
MODES = (SYSTEM, LIGHT, DARK)
SETTING = "theme"

UI_FONTS = ("Segoe UI Variable Text", "Segoe UI", "Inter", "SF Pro Text", "Helvetica Neue", "Noto Sans")
MONO_FONTS = ("Cascadia Mono", "Cascadia Code", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono")

# Type scale in px.
XS, SM, BASE, MD, LG, XL, XXL = 11, 12, 13, 14, 16, 20, 28
# Corner radii in px.
RADIUS_SM, RADIUS, RADIUS_LG = 6, 8, 12


@dataclass(frozen=True)
class Palette:
    name: str  # "light" or "dark"
    canvas: str  # where diagrams and pages are shown
    sidebar: str  # navigation and other chrome beside the canvas
    surface: str  # cards, inputs, menus, buttons
    hover: str  # a row or button under the pointer
    active: str  # a pressed button, the selected row
    border: str  # hairlines between regions
    border_strong: str  # outlines of controls
    text: str
    text_muted: str
    text_subtle: str
    accent: str  # primary buttons and marks: the one colour that means "act here"
    accent_hover: str
    accent_on: str  # text on the accent colour
    accent_soft: str  # tinted background of what is selected
    accent_text: str  # accent-coloured text and icons on ordinary surfaces
    success: str
    success_soft: str
    warning: str
    warning_soft: str
    danger: str
    danger_soft: str
    scrollbar: str
    scrollbar_hover: str
    overlay: str  # behind dialogs and toasts: rgba

    @property
    def diagram(self) -> diagrams.Theme:
        """The diagram theme shown with this palette."""
        return diagrams.THEMES[self.name]


PALETTES = {
    LIGHT: Palette(
        name=LIGHT,
        canvas=diagrams.LIGHT.background,
        sidebar="#f6f8fa",
        surface="#ffffff",
        hover="#eaeef2",
        active="#dfe4ea",
        border="#e1e6eb",
        border_strong="#c8d0d8",
        text="#1f2328",
        text_muted="#59636e",
        text_subtle="#8a939e",
        accent="#5b4bd6",
        accent_hover="#4c3dc0",
        accent_on="#ffffff",
        accent_soft="#eceafd",
        accent_text="#5140c8",
        success="#1a7f37",
        success_soft="#dafbe1",
        warning="#9a6700",
        warning_soft="#fff8c5",
        danger="#cf222e",
        danger_soft="#ffebe9",
        scrollbar="#c8d0d8",
        scrollbar_hover="#a7b0ba",
        overlay="rgba(31, 35, 40, 0.28)",
    ),
    DARK: Palette(
        name=DARK,
        canvas=diagrams.DARK.background,
        sidebar="#090c11",
        surface="#151b23",
        hover="#1a212b",
        active="#232b37",
        border="#222932",
        border_strong="#363e48",
        text="#e9eef4",
        text_muted="#9198a1",
        text_subtle="#6a727d",
        accent="#6c5ce7",
        accent_hover="#7d6ff0",
        accent_on="#ffffff",
        accent_soft="#211e3f",
        accent_text="#a99dff",
        success="#3fb950",
        success_soft="#14261b",
        warning="#d29922",
        warning_soft="#2a2210",
        danger="#f85149",
        danger_soft="#2d1215",
        scrollbar="#363e48",
        scrollbar_hover="#4a535e",
        overlay="rgba(1, 4, 9, 0.6)",
    ),
}

STYLESHEET = """
* { font-family: "@font"; font-size: 13px; color: @text; outline: none; }
QMainWindow, QDialog { background: @canvas; }
QWidget#canvas { background: @canvas; }
QWidget#sidebar, QWidget#statusbar { background: @sidebar; }
QWidget#topbar { background: @canvas; }
QFrame#hairline { background: @border; border: none; }

QToolTip {
    background: @surface; color: @text; border: 1px solid @border_strong; border-radius: 6px; padding: 5px 8px;
}

QLabel { background: transparent; }
QLabel[role="display"] { font-size: 28px; font-weight: 700; }
QLabel[role="title"] { font-size: 20px; font-weight: 700; }
QLabel[role="heading"] { font-size: 14px; font-weight: 600; }
QLabel[role="muted"] { color: @text_muted; }
QLabel[role="subtle"] { color: @text_subtle; font-size: 12px; }
QLabel[role="caps"] { color: @text_subtle; font-size: 11px; font-weight: 700; }
QLabel[role="mono"] { font-family: "@mono"; font-size: 12px; color: @text_muted; }
QLabel[role="key"] {
    font-family: "@mono"; font-size: 11px; color: @text_muted; background: @hover; border: 1px solid @border;
    border-radius: 4px; padding: 1px 5px;
}
QLabel[role="tag"] {
    font-size: 11px; font-weight: 600; color: @text_muted; background: @hover; border-radius: 9px; padding: 2px 8px;
}
QLabel[tone="accent"] { color: @accent_text; background: @accent_soft; }
QLabel[tone="warning"] { color: @warning; background: @warning_soft; }
QLabel[tone="danger"] { color: @danger; background: @danger_soft; }
QLabel[tone="success"] { color: @success; background: @success_soft; }

QPushButton, QToolButton {
    background: @surface; border: 1px solid @border_strong; border-radius: 6px; padding: 5px 12px;
    font-weight: 600; min-height: 18px;
}
QPushButton:hover, QToolButton:hover { background: @hover; }
QPushButton:pressed, QToolButton:pressed, QToolButton:checked { background: @active; }
QPushButton:focus, QToolButton:focus { border-color: @accent; }
QPushButton:disabled, QToolButton:disabled { color: @text_subtle; background: transparent; border-color: @border; }
QPushButton::menu-indicator, QToolButton::menu-indicator { image: none; width: 0; }

QPushButton[variant="primary"], QToolButton[variant="primary"] {
    background: @accent; border-color: @accent; color: @accent_on;
}
QPushButton[variant="primary"]:hover, QToolButton[variant="primary"]:hover {
    background: @accent_hover; border-color: @accent_hover;
}
QPushButton[variant="primary"]:focus { border-color: @text; }
QPushButton[variant="primary"]:disabled, QToolButton[variant="primary"]:disabled {
    background: @active; border-color: @active; color: @text_subtle;
}
QPushButton[variant="ghost"], QToolButton[variant="ghost"] { background: transparent; border-color: transparent; }
QPushButton[variant="ghost"]:hover, QToolButton[variant="ghost"]:hover { background: @hover; }
QPushButton[variant="ghost"]:pressed, QToolButton[variant="ghost"]:pressed,
QToolButton[variant="ghost"]:checked { background: @active; }
QPushButton[variant="ghost"]:focus, QToolButton[variant="ghost"]:focus { border-color: @accent; }
QPushButton[variant="ghost"]:disabled, QToolButton[variant="ghost"]:disabled { border-color: transparent; }
QToolButton[shape="icon"] { padding: 5px; min-width: 18px; }
QPushButton[variant="link"] {
    background: transparent; border: none; color: @accent_text; padding: 2px 0; text-align: left; font-weight: 600;
}
QPushButton[variant="link"]:hover { color: @text; }

QToolButton[variant="segment"] {
    background: transparent; border: 1px solid transparent; border-radius: 5px; padding: 4px 12px;
    color: @text_muted; font-weight: 600;
}
QToolButton[variant="segment"]:hover { color: @text; background: transparent; }
QToolButton[variant="segment"]:checked { background: @surface; border-color: @border_strong; color: @text; }
QWidget#segmented { background: @hover; border-radius: 7px; }

QLineEdit, QPlainTextEdit {
    background: @surface; border: 1px solid @border_strong; border-radius: 6px; padding: 5px 9px;
    selection-background-color: @accent; selection-color: @accent_on;
}
QLineEdit:hover, QPlainTextEdit:hover { border-color: @text_subtle; }
QLineEdit:focus, QPlainTextEdit:focus { border-color: @accent; }
QLineEdit[variant="quiet"] { background: transparent; border-color: @border; }
QLineEdit[variant="quiet"]:focus { background: @surface; border-color: @accent; }
QLineEdit[edited="true"], QPlainTextEdit[edited="true"] { border-color: @accent; background: @accent_soft; }

QMenu { background: @surface; border: 1px solid @border_strong; border-radius: 8px; padding: 5px; }
QMenu::item { padding: 6px 26px 6px 10px; border-radius: 5px; background: transparent; }
QMenu::item:selected { background: @hover; }
QMenu::item:disabled { color: @text_subtle; }
QMenu::separator { height: 1px; background: @border; margin: 5px 6px; }
QMenu::icon { padding-left: 8px; }
QMenu::indicator { width: 14px; height: 14px; padding-left: 6px; }

QScrollArea, QTextBrowser, QListView { background: transparent; border: none; }
QTextBrowser { selection-background-color: @accent; selection-color: @accent_on; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle { background: @scrollbar; border-radius: 4px; }
QScrollBar::handle:vertical { min-height: 36px; }
QScrollBar::handle:horizontal { min-width: 36px; }
QScrollBar::handle:hover { background: @scrollbar_hover; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QProgressBar { background: @active; border: none; border-radius: 2px; min-height: 4px; max-height: 4px; }
QProgressBar::chunk { background: @accent; border-radius: 2px; }

QSplitter::handle { background: @border; }
QSplitter::handle:horizontal { width: 1px; }

QFrame[role="card"] { background: @surface; border: 1px solid @border; border-radius: 10px; }
QFrame[role="card"][interactive="true"]:hover { border-color: @border_strong; background: @hover; }
QFrame[role="panel"] { background: @sidebar; border: 1px solid @border; border-radius: 12px; }
QFrame[role="dropzone"] { background: @sidebar; border: 1.5px dashed @border_strong; border-radius: 14px; }
QFrame[role="dropzone"][active="true"] { background: @accent_soft; border-color: @accent; }
QFrame[role="toast"] { background: @surface; border: 1px solid @border_strong; border-radius: 10px; }
QFrame[role="banner"] { background: @warning_soft; border: none; border-radius: 8px; }
QFrame[role="findbar"] { background: @surface; border: 1px solid @border_strong; border-radius: 9px; }
"""


def stylesheet(palette: Palette, font: str = UI_FONTS[1], mono: str = MONO_FONTS[2]) -> str:
    """The app's style sheet with every `@token` replaced by the palette's colour."""
    tokens = {field.name: getattr(palette, field.name) for field in fields(Palette)}
    tokens.update(font=font, mono=mono)
    # Longest names first, so `@border_strong` is not read as `@border` followed by `_strong`.
    pattern = "|".join(sorted((re.escape(name) for name in tokens), key=len, reverse=True))
    return re.sub(f"@({pattern})", lambda match: tokens[match.group(1)], STYLESHEET)


def first_installed(candidates: tuple[str, ...], fallback: str) -> str:
    installed = set(QFontDatabase.families())
    return next((name for name in candidates if name in installed), fallback)


class Themes(QObject):
    """Which palette is in use, and the one place that changes it.

    The mode is "system" (follow the computer), "light" or "dark", remembered
    between sessions. Widgets that paint by hand read `palette` and repaint
    on `changed`; everything else is restyled through the style sheet.
    """

    changed = Signal(object)  # the new Palette

    def __init__(self, settings: QSettings | None = None, app: QApplication | None = None):
        super().__init__()
        self._settings = settings
        self._app = app
        saved = settings.value(SETTING, SYSTEM, str) if settings is not None else SYSTEM
        self.mode = saved if saved in MODES else SYSTEM
        self.font = self.mono = ""
        self._sync_title_bar()
        self.palette = PALETTES[self._resolve()]
        if app is not None:
            self.font = first_installed(UI_FONTS, app.font().family())
            self.mono = first_installed(MONO_FONTS, QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family())
            app.setStyle("Fusion")
            font = QFont(self.font)
            font.setPixelSize(BASE)
            font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
            app.setFont(font)
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_changed)
            self._apply()

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"Unknown theme mode: {mode}")
        self.mode = mode
        if self._settings is not None:
            self._settings.setValue(SETTING, mode)
        self._refresh()

    def toggle(self) -> None:
        """Switch to the other of light and dark, whatever the mode was."""
        self.set_mode(LIGHT if self.palette.name == DARK else DARK)

    @property
    def is_dark(self) -> bool:
        return self.palette.name == DARK

    def colour(self, name: str) -> QColor:
        """A palette colour as a QColor, e.g. `themes.colour("text_muted")`."""
        return QColor(getattr(self.palette, name))

    def _resolve(self) -> str:
        if self.mode != SYSTEM:
            return self.mode
        return DARK if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else LIGHT

    def _system_changed(self, *_) -> None:
        if self.mode == SYSTEM:
            self._refresh()

    def _sync_title_bar(self) -> None:
        """Make the platform's own parts (title bar, native dialogs) follow the app's mode, where it can.

        Done before resolving "system": while a mode is forced, Qt reports the forced scheme.
        """
        hints = QGuiApplication.styleHints()
        if not hasattr(hints, "setColorScheme"):  # Qt older than 6.8
            return
        if self.mode == SYSTEM:
            hints.unsetColorScheme()
        else:
            hints.setColorScheme(Qt.ColorScheme.Dark if self.mode == DARK else Qt.ColorScheme.Light)

    def _refresh(self) -> None:
        self._sync_title_bar()
        palette = PALETTES[self._resolve()]
        if palette is self.palette:
            return
        self.palette = palette
        self._apply()
        self.changed.emit(palette)

    def _apply(self) -> None:
        if self._app is None:
            return
        p = self.palette
        colours = QPalette()
        for role, colour in (
            (QPalette.ColorRole.Window, p.canvas), (QPalette.ColorRole.Base, p.surface),
            (QPalette.ColorRole.AlternateBase, p.sidebar), (QPalette.ColorRole.Text, p.text),
            (QPalette.ColorRole.WindowText, p.text), (QPalette.ColorRole.Button, p.surface),
            (QPalette.ColorRole.ButtonText, p.text), (QPalette.ColorRole.Highlight, p.accent),
            (QPalette.ColorRole.HighlightedText, p.accent_on), (QPalette.ColorRole.PlaceholderText, p.text_subtle),
            (QPalette.ColorRole.ToolTipBase, p.surface), (QPalette.ColorRole.ToolTipText, p.text),
            (QPalette.ColorRole.Link, p.accent_text),
        ):
            colours.setColor(role, QColor(colour))
        self._app.setPalette(colours)
        self._app.setStyleSheet(stylesheet(p, self.font, self.mono))
