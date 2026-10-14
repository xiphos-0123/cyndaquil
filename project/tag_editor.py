"""Reusable tag entry with suggestions from existing session records."""

from PySide6.QtCore import QStringListModel, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .history_filters import normalize_tags


class TagCompleter(QCompleter):
    """Complete the current comma-separated tag without replacing earlier tags."""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.tags_model = QStringListModel(self)
        self.setModel(self.tags_model)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

    def splitPath(self, path):
        return [path.rsplit(",", 1)[-1].strip()]

    def pathFromIndex(self, index):
        # Read from the supplied index, which may belong to Qt's filtered model.
        tag = index.data(self.completionRole()) or ""
        current = self.editor.text()
        return f"{current.rsplit(',', 1)[0]}, {tag}" if "," in current else tag


class TagEditor(QWidget):
    changed = Signal()

    def __init__(self, tags=(), available=(), parent=None, *, compact=False):
        super().__init__(parent)
        layout = QVBoxLayout(self) if compact else QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.text = QLineEdit(", ".join(normalize_tags(tags)))
        self.text.setPlaceholderText("Tags, separated by commas")
        self.text.setCursorPosition(0)
        self.completer = TagCompleter(self.text)
        self.text.setCompleter(self.completer)
        self.text.setAccessibleName("Session tags")
        self.text.setToolTip("For example: Waking Up Arc, Reading. A comma separates tags.")
        self.suggestions = QComboBox()
        self.suggestions.setAccessibleName("Existing tags")
        self.suggestions.setMinimumContentsLength(12)
        self.suggestions.setMaximumWidth(220)
        self.add = QPushButton("Add")
        self.add.setAutoDefault(False)
        layout.addWidget(self.text, 1)
        controls = QHBoxLayout() if compact else layout
        controls.addWidget(self.suggestions)
        controls.addWidget(self.add)
        if compact:
            layout.addLayout(controls)
        self.set_available(available)
        self.text.textChanged.connect(self.changed)
        self.add.clicked.connect(self._add_selected)
        self.suggestions.currentIndexChanged.connect(lambda index: self.add.setEnabled(index > 0))

    def set_available(self, tags):
        self.completer.tags_model.setStringList(sorted(normalize_tags(tags), key=str.casefold))
        current = self.suggestions.currentText()
        self.suggestions.clear()
        self.suggestions.addItem("Existing tags…", None)
        for tag in sorted(normalize_tags(tags), key=str.casefold):
            self.suggestions.addItem(tag, tag)
        index = self.suggestions.findText(current)
        if index >= 0:
            self.suggestions.setCurrentIndex(index)
        self.add.setEnabled(self.suggestions.currentIndex() > 0)

    def _add_selected(self):
        tag = self.suggestions.currentData()
        if tag:
            self.text.setText(", ".join(normalize_tags([*self.tags(), tag])))

    def tags(self):
        return normalize_tags(self.text.text())


def available_tags(sessions):
    return normalize_tags(
        [tag for session in sessions for tag in normalize_tags(session.get("tags", []))]
    )


class BulkTagDialog(QDialog):
    def __init__(self, count, available, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tag Selected Sessions")
        self.resize(640, 180)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(f"Update tags on {count} selected sessions. Notes and times are preserved.")
        )
        self.mode = QComboBox()
        self.mode.addItem("Add tags", False)
        self.mode.addItem("Remove tags", True)
        self.editor = TagEditor(available=available)
        layout.addWidget(self.mode)
        layout.addWidget(self.editor)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setEnabled(False)
        self.editor.changed.connect(lambda: self.save_button.setEnabled(bool(self.editor.tags())))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
