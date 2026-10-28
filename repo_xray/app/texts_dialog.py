"""Let the user put names and descriptions in their own words (ADR-0011).

Every field shows what repo-xray found as a grey hint. Typing replaces
it; leaving a field empty goes back to the found text. The result is
saved in the project's xray.toml, so the next analysis keeps it.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHeaderView, QLabel, QLineEdit, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from repo_xray.config import FeatureText
from repo_xray.pipeline import Analysis

NAME, DESCRIPTION = 1, 2


class TextsDialog(QDialog):
    def __init__(self, analysis: Analysis, parent=None):
        super().__init__(parent)
        self.analysis = analysis
        self.setWindowTitle("Edit texts")
        self.resize(980, 620)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        intro = QLabel("Write names and descriptions in your own words. Grey text is what repo-xray found; "
                       "leave a field empty to keep it. Saved in xray.toml in your project.")
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(self._section("PROJECT DESCRIPTION"))
        config = analysis.config
        self.description = QLineEdit(config.description or "")
        self.description.setPlaceholderText(analysis.stack.found_description or "What is this project for?")
        layout.addWidget(self.description)

        layout.addWidget(self._section("FEATURES"))
        features = analysis.features.features
        self.table = QTableWidget(len(features), 3)
        self.table.setHorizontalHeaderLabels(["Feature", "Name", "Description"])
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(NAME, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(DESCRIPTION, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(NAME, 180)
        for row, feature in enumerate(features):
            key = QTableWidgetItem(f"{feature.app} · {feature.key.partition('/')[2]}")
            key.setFlags(Qt.ItemFlag.ItemIsEnabled)
            key.setData(Qt.ItemDataRole.UserRole, feature.key)
            self.table.setItem(row, 0, key)
            saved = config.features.get(feature.key, FeatureText())
            self.table.setCellWidget(row, NAME, self._field(saved.name, feature.found_name))
            self.table.setCellWidget(row, DESCRIPTION, self._field(saved.description, feature.found_description))
            self.table.setRowHeight(row, 38)
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def project_description(self) -> str | None:
        return self.description.text().strip() or None

    def feature_texts(self) -> dict[str, FeatureText]:
        texts = {}
        for row in range(self.table.rowCount()):
            key = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            name = self.table.cellWidget(row, NAME).text().strip() or None
            description = self.table.cellWidget(row, DESCRIPTION).text().strip() or None
            if name or description:
                texts[key] = FeatureText(name=name, description=description)
        return texts

    @staticmethod
    def _field(value: str | None, hint: str | None) -> QLineEdit:
        field = QLineEdit(value or "")
        field.setPlaceholderText(hint or "")
        field.setFrame(False)
        return field

    @staticmethod
    def _section(title: str) -> QLabel:
        label = QLabel(title)
        label.setObjectName("section")
        return label
