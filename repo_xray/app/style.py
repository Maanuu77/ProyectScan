"""The app's look: the same palette as the diagrams, following the system's light or dark mode."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from repo_xray.render.theme import DARK, LIGHT, Theme

STYLESHEET = """
QWidget {{ background: {background}; color: {text}; font-size: 14px; }}
QLabel#title {{ font-size: 30px; font-weight: 700; }}
QLabel#heading {{ font-size: 20px; font-weight: 700; }}
QLabel#muted, QLabel#hint {{ color: {text_muted}; }}
QLabel#hint {{ font-size: 13px; }}
QLabel#section {{ color: {text_muted}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QFrame#card {{ background: {surface}; border: 1px solid {border}; border-radius: 12px; }}
QFrame#dropzone {{ background: {surface}; border: 2px dashed {border_strong}; border-radius: 16px; }}
QFrame#dropzone[active="true"] {{ border-color: {accent}; background: {accent_soft}; }}
QPushButton {{
    background: {surface}; border: 1px solid {border}; border-radius: 8px;
    padding: 8px 16px; font-weight: 600;
}}
QPushButton:hover {{ background: {surface_muted}; border-color: {border_strong}; }}
QPushButton:disabled {{ color: {text_subtle}; }}
QPushButton#primary {{ background: {accent}; border-color: {accent}; color: #ffffff; }}
QPushButton#primary:hover {{ background: {accent_hover}; }}
QPushButton#link {{ background: transparent; border: none; color: {accent}; padding: 4px 0; text-align: left; }}
QPushButton:checked {{ background: {accent_soft}; border-color: {accent}; color: {accent}; }}
QListWidget {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; padding: 6px; }}
QListWidget::item {{ padding: 7px 10px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {accent_soft}; color: {text}; }}
QListWidget::item:hover {{ background: {surface_muted}; }}
QProgressBar {{ background: {surface_muted}; border: none; border-radius: 4px; height: 8px; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}
QScrollArea, QTextBrowser {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; }}
QTextBrowser {{ padding: 16px; }}
"""


def current_theme() -> Theme:
    hints = QGuiApplication.styleHints()
    return DARK if hints.colorScheme() == Qt.ColorScheme.Dark else LIGHT


def apply(app: QApplication) -> Theme:
    theme = current_theme()
    accent = theme.accent("desktop")
    app.setStyle("Fusion")
    palette = QPalette()
    for role, colour in ((QPalette.ColorRole.Window, theme.background), (QPalette.ColorRole.Base, theme.surface),
                         (QPalette.ColorRole.Text, theme.text), (QPalette.ColorRole.WindowText, theme.text),
                         (QPalette.ColorRole.Highlight, accent.strong), (QPalette.ColorRole.Button, theme.surface),
                         (QPalette.ColorRole.ButtonText, theme.text)):
        palette.setColor(role, QColor(colour))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET.format(
        background=theme.background, surface=theme.surface, surface_muted=theme.surface_muted,
        border=theme.border, border_strong=theme.border_strong, text=theme.text, text_muted=theme.text_muted,
        text_subtle=theme.text_subtle, accent=accent.strong, accent_soft=accent.soft,
        accent_hover=QColor(accent.strong).darker(115).name(),
    ))
    return theme
