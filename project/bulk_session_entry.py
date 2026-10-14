"""Explicit, transactional editing of selected history records."""

from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .history_filters import normalize_tags
from .history_records import (
    _datetime_to_editor,
    _parse_datetime,
    _parse_duration,
    _seconds_to_editor,
)
from .mixed_text import MixedText
from .persistence import PersistenceError
from .tag_editor import TagEditor, available_tags
from .theme import COLORS


class MixedMarkerHighlighter(QSyntaxHighlighter):
    def __init__(self, document, mixed):
        super().__init__(document)
        self.mixed = mixed
        self.marker_format = QTextCharFormat()
        self.marker_format.setBackground(QColor(COLORS["bronze"]))
        self.marker_format.setForeground(QColor(COLORS["background"]))
        self.marker_format.setFontWeight(QFont.Weight.Bold)

    def highlightBlock(self, text):
        for match in self.mixed.pattern.finditer(text):
            start = len(text[: match.start()].encode("utf-16-le")) // 2
            length = len(match.group().encode("utf-16-le")) // 2
            self.setFormat(start, length, self.marker_format)


class BulkSessionEntryDialog(QDialog):
    def __init__(self, store, sessions, parent=None):
        super().__init__(parent)
        self.store = store
        self.original = deepcopy(sessions)
        self.setWindowTitle(f"Edit {len(sessions)} Sessions")
        self.resize(1040, 780)
        self.setMinimumSize(800, 600)
        self.text_fields = {}
        self.value_fields = {}
        self.common_values = {}
        self.apply_fields = {}
        self.initial = {}
        self.mixed = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(16)
        title = QLabel(f"Edit {len(sessions)} sessions")
        title.setObjectName("Title")
        help_text = QLabel(
            "Shared text is shown normally. A marker such as ⟦1⟧ keeps each session’s differing text. "
            "Replace or remove a whole marker to change that section for everyone. "
            "Only checked fields are saved."
        )
        help_text.setObjectName("Muted")
        help_text.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(help_text)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        details = QWidget()
        form = QFormLayout(details)
        form.setContentsMargins(4, 4, 16, 4)
        form.setVerticalSpacing(16)
        scroll.setWidget(details)
        splitter.addWidget(scroll)
        for key, label in (("mission", "Session objective"), ("preset_name", "Preset name")):
            mixed = MixedText.from_values([record.get(key, "") or "" for record in self.original])
            editor = QLineEdit(mixed.template)
            self.mixed[key] = mixed
            self.text_fields[key] = editor
            self.initial[key] = editor.text()
            check = self._apply_checkbox(key, label)
            form.addRow(check, editor)
            editor.textChanged.connect(lambda _, box=check: box.setChecked(True))

        common_tags = normalize_tags(self.original[0].get("tags", []))
        for record in self.original[1:]:
            assigned = {tag.casefold() for tag in normalize_tags(record.get("tags", []))}
            common_tags = [tag for tag in common_tags if tag.casefold() in assigned]
        self.tags = TagEditor(common_tags, available_tags(store.sessions), compact=True)
        self.tag_mode = QComboBox()
        for label, value in (
            ("Add tags", "add"),
            ("Remove tags", "remove"),
            ("Replace tags", "replace"),
        ):
            self.tag_mode.addItem(label, value)
        tag_box = QWidget()
        tag_layout = QVBoxLayout(tag_box)
        tag_layout.setContentsMargins(0, 0, 0, 0)
        tag_layout.addWidget(self.tag_mode)
        tag_layout.addWidget(self.tags)
        tag_check = self._apply_checkbox("tags", "Tags")
        form.addRow(tag_check, tag_box)
        self.tags.changed.connect(lambda: tag_check.setChecked(True))
        self.tag_mode.currentIndexChanged.connect(lambda: tag_check.setChecked(True))

        self.mode = QComboBox()
        self.mode.addItem("Keep individual modes", None)
        self.mode.addItem("Stopwatch", "stopwatch")
        self.mode.addItem("Timer", "timer")
        mode_check = self._apply_checkbox("mode", "Session mode")
        form.addRow(mode_check, self.mode)
        self.mode.currentIndexChanged.connect(
            lambda: mode_check.setChecked(self.mode.currentData() is not None)
        )
        for key, label in (
            ("focused_seconds", "Focused time"),
            ("target_seconds", "Target duration"),
            ("started_at", "Started at"),
            ("ended_at", "Finished at"),
        ):
            values = [record.get(key) for record in self.original]
            common = all(value == values[0] for value in values)
            self.common_values[key] = common
            initial = (
                (
                    _seconds_to_editor(values[0])
                    if key.endswith("_seconds")
                    else _datetime_to_editor(values[0])
                )
                if common
                else ""
            )
            editor = QLineEdit(initial)
            editor.setPlaceholderText(
                "Mixed · unchanged"
                if not common
                else ("HH:MM:SS" if key.endswith("_seconds") else "YYYY-MM-DD HH:MM:SS+offset")
            )
            self.value_fields[key] = editor
            self.initial[key] = initial
            check = self._apply_checkbox(key, label)
            form.addRow(check, editor)
            editor.textChanged.connect(lambda _, box=check: box.setChecked(True))
        form.addRow(QLabel("Recorded ambience and other fields stay as saved."))

        notes_card = QFrame()
        notes_card.setObjectName("Card")
        notes_layout = QVBoxLayout(notes_card)
        notes_layout.setContentsMargins(20, 18, 20, 20)
        notes_layout.setSpacing(12)
        note_check = self._apply_checkbox("completion_note", "Apply completion notes")
        notes_layout.addWidget(note_check)
        self.note_mixed = MixedText.from_values(
            [record.get("completion_note", "") or "" for record in self.original]
        )
        self.mixed["completion_note"] = self.note_mixed
        self.notes = QPlainTextEdit(self.note_mixed.template)
        self.notes.setPlaceholderText("Completion notes for the selected sessions")
        self.text_fields["completion_note"] = self.notes
        self.initial["completion_note"] = self.notes.toPlainText()
        self.note_highlighter = MixedMarkerHighlighter(self.notes.document(), self.note_mixed)
        self._last_note_text = self.initial["completion_note"]
        self.notes.textChanged.connect(self._notes_changed)
        notes_layout.addWidget(self.notes, 1)
        differences = QPushButton("View differing sections…")
        differences.setEnabled(any(mixed.sections for mixed in self.mixed.values()))
        differences.clicked.connect(self.show_differences)
        notes_layout.addWidget(differences)
        splitter.addWidget(notes_card)
        splitter.setSizes([440, 600])
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText(f"Save selected sessions ({len(sessions)})")
        self.save_button.setObjectName("Primary")
        self.save_button.setEnabled(False)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _notes_changed(self):
        text = self.notes.toPlainText()
        if text == self._last_note_text:
            return  # Syntax highlighting can emit textChanged without editing text.
        self._last_note_text = text
        self.apply_fields["completion_note"].setChecked(text != self.initial["completion_note"])

    def _apply_checkbox(self, key, label):
        box = QCheckBox(label)
        self.apply_fields[key] = box
        box.toggled.connect(self._update_save)
        return box

    def _update_save(self):
        if hasattr(self, "save_button"):
            self.save_button.setEnabled(any(box.isChecked() for box in self.apply_fields.values()))

    def build_updates(self):
        updates = {record["id"]: {} for record in self.original}
        for key, editor in self.text_fields.items():
            edited = editor.toPlainText() if isinstance(editor, QPlainTextEdit) else editor.text()
            if not self.apply_fields[key].isChecked() or edited == self.initial[key]:
                continue
            for index, record in enumerate(self.original):
                updates[record["id"]][key] = self.mixed[key].expand(edited, index)
        for key, editor in self.value_fields.items():
            if not self.apply_fields[key].isChecked():
                continue
            if self.common_values[key] and editor.text() == self.initial[key]:
                continue
            # Mixed fields start empty; explicit checked empty text can clear them.
            value = (
                _parse_duration(editor.text(), key.replace("_", " "))
                if key.endswith("_seconds")
                else _parse_datetime(editor.text(), key.replace("_", " "))
            )
            for patch in updates.values():
                patch[key] = value
        if self.apply_fields["mode"].isChecked() and self.mode.currentData() is not None:
            for patch in updates.values():
                patch["mode"] = self.mode.currentData()
        if self.apply_fields["tags"].isChecked():
            tags = self.tags.tags()
            removed = {tag.casefold() for tag in tags}
            for record in self.original:
                existing = normalize_tags(record.get("tags", []))
                mode = self.tag_mode.currentData()
                updates[record["id"]]["tags"] = (
                    tags
                    if mode == "replace"
                    else [tag for tag in existing if tag.casefold() not in removed]
                    if mode == "remove"
                    else normalize_tags([*existing, *tags])
                )
        return {sid: patch for sid, patch in updates.items() if patch}

    def save(self):
        try:
            updates = self.build_updates()
            self.store.update_sessions(
                updates, expected={record["id"]: record for record in self.original}
            )
        except (ValueError, PersistenceError) as error:
            QMessageBox.warning(self, "Sessions Were Not Saved", str(error))
            return
        self.accept()

    def show_differences(self):
        lines = []
        for key, mixed in self.mixed.items():
            for token, values in mixed.sections.items():
                lines.append(f"{key.replace('_', ' ').title()} · {token}")
                for index, value in enumerate(values):
                    lines.append(
                        f"Session {index + 1} · {self.original[index].get('mission') or self.original[index]['id']}"
                    )
                    lines.append(value if value else "(empty)")
                    lines.append("")
        dialog = QDialog(self)
        dialog.setWindowTitle("Differing Sections")
        dialog.resize(780, 600)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit("\n".join(lines))
        text.setReadOnly(True)
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
