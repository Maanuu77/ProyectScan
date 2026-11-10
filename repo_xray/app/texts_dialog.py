"""Let the user put names and descriptions in their own words (ADR-0011).

Every field shows what repo-xray found as a grey hint. Typing replaces
it; leaving a field empty goes back to the found text. The result is
saved in the project's xray.toml, so the next analysis keeps it.

One card per feature, grouped by app. A filter narrows a long list, a
field that holds the user's own words is marked, and each card can be put
back to what was found.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLineEdit, QPlainTextEdit, QScrollArea, QVBoxLayout,
                               QWidget)

from repo_xray.analysis.features import Feature
from repo_xray.app.theme import Themes
from repo_xray.app.widgets.common import Button, IconButton, Segmented, caps, hairline, label, set_property, tag
from repo_xray.config import FeatureText
from repo_xray.pipeline import Analysis

KINDS = {"web": "Web app", "api": "API", "mobile": "Mobile app", "desktop": "Desktop app", "library": "Application"}
SOURCES = {"generated": ("Written by repo-xray", "warning"), "code": ("From the code", None), "user": ("Yours", "accent")}
ALL, EDITED = "all", "edited"


class FeatureRow(QFrame):
    """A feature's name and description, each with what was found as its hint."""

    def __init__(self, feature: Feature, saved: FeatureText, themes: Themes):
        super().__init__()
        self.feature = feature
        self.key = feature.key
        self.setProperty("role", "card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 10, 12)
        layout.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(label(feature.key.partition("/")[2] or feature.key, "mono"))
        source = "user" if saved.description else feature.description_source
        text, tone = SOURCES.get(source, SOURCES["code"])
        self.source = tag(text, tone)
        self.source.setToolTip("Where the description shown in the documents comes from")
        head.addWidget(self.source)
        head.addStretch()
        self.reset = IconButton("refresh", themes, "Go back to what repo-xray found", size=14)
        self.reset.clicked.connect(self.clear)
        head.addWidget(self.reset)
        layout.addLayout(head)

        fields = QHBoxLayout()
        fields.setSpacing(8)
        self.name = QLineEdit(saved.name or "")
        self.name.setPlaceholderText(feature.found_name)
        self.name.setToolTip("Name shown in the diagrams and pages")
        self.name.setFixedWidth(210)
        self.description = QLineEdit(saved.description or "")
        self.description.setPlaceholderText(feature.found_description or "What is this feature for?")
        self.description.setToolTip("One sentence shown on the feature's card and at the top of its page")
        fields.addWidget(self.name)
        fields.addWidget(self.description, 1)
        layout.addLayout(fields)
        for field in (self.name, self.description):
            field.textChanged.connect(self._mark)
        self._mark()

    def text(self) -> FeatureText | None:
        """The user's words for this feature, or None when both fields are empty."""
        name = self.name.text().strip() or None
        description = self.description.text().strip() or None
        return FeatureText(name=name, description=description) if name or description else None

    def is_edited(self) -> bool:
        return self.text() is not None

    def clear(self) -> None:
        self.name.clear()
        self.description.clear()

    def matches(self, words: list[str]) -> bool:
        feature = self.feature
        haystack = " ".join([feature.key, feature.found_name, feature.found_description or "",
                             self.name.text(), self.description.text()]).casefold()
        return all(word in haystack for word in words)

    def _mark(self, *_) -> None:
        for field in (self.name, self.description):
            set_property(field, "edited", bool(field.text().strip()))
        self.reset.setEnabled(self.is_edited())


class TextsDialog(QDialog):
    def __init__(self, analysis: Analysis, themes: Themes, parent=None):
        super().__init__(parent)
        self.analysis = analysis
        self.setWindowTitle("Edit texts")
        self.resize(1000, 700)
        self.setMinimumSize(720, 480)
        config = analysis.config
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QVBoxLayout()
        top.setContentsMargins(24, 20, 24, 14)
        top.setSpacing(4)
        top.addWidget(label("Edit texts", "title"))
        top.addWidget(label("Say it in your own words. Grey text is what repo-xray found in the code; leave a field "
                            "empty to keep it.", "muted", wrap=True))
        top.addSpacing(12)
        top.addWidget(caps("Project description"))
        top.addSpacing(2)
        self.description = QPlainTextEdit(config.description or "")
        self.description.setPlaceholderText(analysis.stack.found_description or "What is this project for?")
        self.description.setFixedHeight(64)
        self.description.setTabChangesFocus(True)
        self.description.textChanged.connect(self._changed)
        top.addWidget(self.description)
        top.addSpacing(14)

        tools = QHBoxLayout()
        tools.setSpacing(10)
        tools.addWidget(caps("Features"))
        tools.addStretch()
        self.counter = label("", "subtle")
        tools.addWidget(self.counter)
        self.scope = Segmented([(ALL, "All", "Every feature"), (EDITED, "In your words", "Only the features you changed")])
        self.scope.select(ALL)
        self.scope.selected.connect(self._apply_filter)
        tools.addWidget(self.scope)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter features")
        self.filter.setClearButtonEnabled(True)
        self.filter.setFixedWidth(220)
        self.filter.textChanged.connect(self._apply_filter)
        tools.addWidget(self.filter)
        top.addLayout(tools)
        outer.addLayout(top)
        outer.addWidget(hairline())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        self._list = QVBoxLayout(body)
        self._list.setContentsMargins(24, 14, 18, 18)
        self._list.setSpacing(8)
        self.rows: dict[str, FeatureRow] = {}
        self._groups: list[tuple[QWidget, list[FeatureRow]]] = []
        for app in analysis.stack.apps:
            features = analysis.features.of_app(app.name)
            if not features:
                continue
            heading = label(f"{app.name}  ·  {KINDS.get(app.kind, 'Application')}", "heading")
            heading.setContentsMargins(2, 8, 0, 0)
            self._list.addWidget(heading)
            rows = []
            for feature in features:
                row = FeatureRow(feature, config.features.get(feature.key, FeatureText()), themes)
                row.name.textChanged.connect(self._changed)
                row.description.textChanged.connect(self._changed)
                row.reset.clicked.connect(self._apply_filter)  # a feature put back leaves "in your words"
                self.rows[feature.key] = row
                rows.append(row)
                self._list.addWidget(row)
            self._groups.append((heading, rows))
        self.nothing = label("No feature matches.", "muted")
        self.nothing.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nothing.setContentsMargins(0, 40, 0, 40)
        self.nothing.hide()
        self._list.addWidget(self.nothing)
        self._list.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        outer.addWidget(hairline())

        footer = QHBoxLayout()
        footer.setContentsMargins(24, 12, 24, 14)
        footer.setSpacing(8)
        footer.addWidget(label("Saved in xray.toml in your project, so the next analysis keeps your words.", "subtle"), 1)
        self.cancel = Button("Cancel", themes)
        self.cancel.clicked.connect(self.reject)
        self.save = Button("Save", themes, "check", "primary", "Save and update the documents  (Ctrl+Enter)")
        self.save.setDefault(False)
        self.save.clicked.connect(self.accept)
        footer.addWidget(self.cancel)
        footer.addWidget(self.save)
        outer.addLayout(footer)
        for keys in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(keys), self).activated.connect(self.accept)
        self._changed()

    # What the user wrote

    def project_description(self) -> str | None:
        return " ".join(self.description.toPlainText().split()) or None

    def feature_texts(self) -> dict[str, FeatureText]:
        texts = {key: row.text() for key, row in self.rows.items()}
        return {key: text for key, text in texts.items() if text is not None}

    # Filter and counter

    def visible_keys(self) -> list[str]:
        return [key for key, row in self.rows.items() if not row.isHidden()]

    def _apply_filter(self, *_) -> None:
        words = self.filter.text().casefold().split()
        only_edited = self.scope.current() == EDITED
        shown = 0
        for heading, rows in self._groups:
            visible = [row for row in rows if row.matches(words) and (row.is_edited() or not only_edited)]
            for row in rows:
                row.setVisible(row in visible)
            heading.setVisible(bool(visible))
            shown += len(visible)
        self.nothing.setVisible(shown == 0)

    def _changed(self, *_) -> None:
        edited = sum(row.is_edited() for row in self.rows.values())
        set_property(self.description, "edited", bool(self.description.toPlainText().strip()))
        self.counter.setText(f"{edited} of {len(self.rows)} in your words")
