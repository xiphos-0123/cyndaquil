"""Full session record editor; changes are persisted only on explicit save."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSplitter, QVBoxLayout, QWidget,
)
from .store import Store
from .persistence import PersistenceError
from .tag_editor import TagEditor, available_tags
from .utils import format_seconds, parse_iso_datetime
from .history_records import _seconds_to_editor, _parse_duration, _datetime_to_editor, _parse_datetime


class SessionEntryDialog(QDialog):
    def __init__(self, store: Store, session: dict, parent=None):
        super().__init__(parent)
        self.store = store
        self.original = deepcopy(session)
        self.setWindowTitle("Session Entry")
        self.resize(1000, 740)
        self.setMinimumSize(800, 580)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Edit Session Entry")
        title.setObjectName("Title")
        subtitle = QLabel(
            "Edit the complete saved record. Session span and non-focus time are derived from Start, Finish, and Focused Time."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        id_label = QLabel(f"ID: {session.get('id', '')}")
        id_label.setObjectName("Muted")
        id_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header.addWidget(id_label)
        root.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left = QWidget()
        left_scroll.setWidget(left)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 10, 4)
        left_layout.setSpacing(14)

        details = QFrame()
        details.setObjectName("Card")
        form = QFormLayout(details)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(10)

        self.tags = TagEditor(session.get("tags", []), available_tags(store.sessions), compact=True)
        self.mission = QLineEdit(session.get("mission", ""))
        self.preset_name = QLineEdit(session.get("preset_name", ""))
        self.preset_ref = QComboBox()
        self.preset_ref.addItem("No Preset Reference", None)
        current_preset_id = session.get("preset_id")
        for preset in self.store.presets:
            self.preset_ref.addItem(preset.get("name", "Preset"), preset.get("id"))
        preset_index = self.preset_ref.findData(current_preset_id)
        if preset_index >= 0:
            self.preset_ref.setCurrentIndex(preset_index)
        elif current_preset_id:
            self.preset_ref.addItem(f"Missing Preset ({current_preset_id})", current_preset_id)
            self.preset_ref.setCurrentIndex(self.preset_ref.count() - 1)

        self.mode = QComboBox()
        self.mode.addItem("Stopwatch", "stopwatch")
        self.mode.addItem("Timer", "timer")
        mode_index = self.mode.findData(session.get("mode", "stopwatch"))
        self.mode.setCurrentIndex(mode_index if mode_index >= 0 else 0)

        self.started_at = QLineEdit(_datetime_to_editor(session.get("started_at")))
        self.started_at.setPlaceholderText("YYYY-MM-DD HH:MM:SS+offset")
        self.ended_at = QLineEdit(_datetime_to_editor(session.get("ended_at")))
        self.ended_at.setPlaceholderText("YYYY-MM-DD HH:MM:SS+offset")
        self.target = QLineEdit(_seconds_to_editor(session.get("target_seconds", 0)))
        self.focused = QLineEdit(_seconds_to_editor(session.get("focused_seconds", 0)))
        for field in (self.target, self.focused):
            field.setPlaceholderText("HH:MM:SS")

        self.span_value = QLabel("—")
        self.nonfocus_value = QLabel("—")
        self.span_value.setObjectName("Muted")
        self.nonfocus_value.setObjectName("Muted")

        form.addRow("Session Objective", self.mission)
        form.addRow("Tags", self.tags)
        form.addRow("Preset Name", self.preset_name)
        form.addRow("Preset Reference", self.preset_ref)
        form.addRow("Session Mode", self.mode)
        form.addRow("Started At", self.started_at)
        form.addRow("Finished At", self.ended_at)
        form.addRow("Target Duration", self.target)
        form.addRow("Focused Time", self.focused)
        form.addRow("Session Span", self.span_value)
        form.addRow("Non-Focus Time (Derived)", self.nonfocus_value)

        time_note = QLabel(
            "Non-Focus Time is calculated automatically as Session Span minus Focused Time. "
            "Durations accept HH:MM:SS, MM:SS, seconds, 45m, or 1.5h."
        )
        time_note.setObjectName("Muted")
        time_note.setWordWrap(True)
        form.addRow("", time_note)
        left_layout.addWidget(details)

        resources = QFrame()
        resources.setObjectName("Card")
        resources_layout = QVBoxLayout(resources)
        resources_layout.setContentsMargins(16, 16, 16, 16)
        resources_layout.setSpacing(8)
        resource_title = QLabel("Recorded Ambience")
        resource_title.setObjectName("SectionTitle")
        resource_note = QLabel(
            "These references belong to this History entry; editing them does not modify the original preset."
        )
        resource_note.setObjectName("Muted")
        resource_note.setWordWrap(True)

        self.visual = QComboBox()
        self.visual.addItem("No Visual", None)
        current_visual = session.get("visual_id")
        for item in self.store.resources:
            if item.get("kind") in {"image", "gif", "video"}:
                self.visual.addItem(item.get("name", "Visual"), item.get("id"))
        visual_index = self.visual.findData(current_visual)
        if visual_index >= 0:
            self.visual.setCurrentIndex(visual_index)
        elif current_visual:
            self.visual.addItem(f"Missing Resource ({current_visual})", current_visual)
            self.visual.setCurrentIndex(self.visual.count() - 1)

        self.audio_list = QListWidget()
        self.audio_list.setMinimumHeight(150)
        self.audio_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        current_music = set(session.get("music_ids", []))
        known_audio_ids = set()
        for item in self.store.resources:
            if item.get("kind") != "audio":
                continue
            rid = item.get("id")
            known_audio_ids.add(rid)
            list_item = QListWidgetItem(self.audio_list)
            box = QCheckBox(item.get("name", "Audio"))
            box.setProperty("resource_id", rid)
            box.setChecked(rid in current_music)
            self.audio_list.setItemWidget(list_item, box)
            list_item.setSizeHint(box.sizeHint())
        for missing_id in sorted(current_music - known_audio_ids):
            list_item = QListWidgetItem(self.audio_list)
            box = QCheckBox(f"Missing Resource ({missing_id})")
            box.setProperty("resource_id", missing_id)
            box.setChecked(True)
            self.audio_list.setItemWidget(list_item, box)
            list_item.setSizeHint(box.sizeHint())

        visual_form = QFormLayout()
        visual_form.addRow("Visual Resource", self.visual)
        resources_layout.addWidget(resource_title)
        resources_layout.addWidget(resource_note)
        resources_layout.addLayout(visual_form)
        resources_layout.addWidget(QLabel("Audio Resources"))
        resources_layout.addWidget(self.audio_list)
        left_layout.addWidget(resources)
        left_layout.addStretch()
        splitter.addWidget(left_scroll)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 4, 4, 4)
        right_layout.setSpacing(12)

        note_card = QFrame()
        note_card.setObjectName("Card")
        note_layout = QVBoxLayout(note_card)
        note_layout.setContentsMargins(16, 16, 16, 16)
        note_title = QLabel("Completion Notes")
        note_title.setObjectName("SectionTitle")
        self.completion_note = QPlainTextEdit(session.get("completion_note", "") or "")
        self.completion_note.setPlaceholderText("Completion notes")
        self.completion_note.setMinimumHeight(240)
        note_layout.addWidget(note_title)
        note_layout.addWidget(self.completion_note, 1)

        distraction_card = QFrame()
        distraction_card.setObjectName("Card")
        distraction_layout = QVBoxLayout(distraction_card)
        distraction_layout.setContentsMargins(16, 16, 16, 16)
        distraction_title = QLabel("Distraction Log")
        distraction_title.setObjectName("SectionTitle")
        distraction_note = QLabel("One entry per line.")
        distraction_note.setObjectName("Muted")
        self.distractions = QPlainTextEdit("\n".join(session.get("distractions", []) or []))
        self.distractions.setMinimumHeight(180)
        distraction_layout.addWidget(distraction_title)
        distraction_layout.addWidget(distraction_note)
        distraction_layout.addWidget(self.distractions, 1)

        right_layout.addWidget(note_card, 3)
        self.distraction_toggle = QPushButton("Show Distraction Dump")
        self.distraction_toggle.setCheckable(True)
        self.distraction_toggle.toggled.connect(distraction_card.setVisible)
        self.distraction_toggle.toggled.connect(
            lambda shown: self.distraction_toggle.setText("Hide Distraction Dump" if shown else "Show Distraction Dump")
        )
        distraction_card.hide()
        right_layout.addWidget(self.distraction_toggle)
        right_layout.addWidget(distraction_card, 2)
        splitter.addWidget(right)
        splitter.setSizes([500, 500])

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setText("Save Session Entry")
        save_button.setObjectName("Primary")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.started_at.textChanged.connect(self._refresh_derived_times)
        self.ended_at.textChanged.connect(self._refresh_derived_times)
        self.focused.textChanged.connect(self._refresh_derived_times)
        self._refresh_derived_times()

    def _refresh_derived_times(self) -> None:
        try:
            start = parse_iso_datetime(_parse_datetime(self.started_at.text(), "Started At")) if self.started_at.text().strip() else None
            end = parse_iso_datetime(_parse_datetime(self.ended_at.text(), "Finished At")) if self.ended_at.text().strip() else None
            focused = _parse_duration(self.focused.text(), "Focused Time")
        except ValueError:
            self.span_value.setText("—")
            self.nonfocus_value.setText("—")
            return
        if not start or not end or end < start:
            self.span_value.setText("—")
            self.nonfocus_value.setText("—")
            return
        span = max(0, int((end - start).total_seconds()))
        self.span_value.setText(format_seconds(span))
        self.nonfocus_value.setText(format_seconds(max(0, span - focused)))

    def _selected_audio_ids(self) -> list[str]:
        result = []
        for row in range(self.audio_list.count()):
            item = self.audio_list.item(row)
            box = self.audio_list.itemWidget(item)
            if box and box.isChecked():
                rid = box.property("resource_id")
                if rid:
                    result.append(str(rid))
        return result

    def save(self) -> None:
        try:
            started_at = _parse_datetime(self.started_at.text(), "Started At")
            ended_at = _parse_datetime(self.ended_at.text(), "Finished At")
            target_seconds = _parse_duration(self.target.text(), "Target Duration")
            focused_seconds = _parse_duration(self.focused.text(), "Focused Time")
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Session Entry", str(exc))
            return

        if started_at and ended_at:
            if datetime.fromisoformat(ended_at) < datetime.fromisoformat(started_at):
                QMessageBox.warning(self, "Invalid Session Entry", "Finished At cannot be earlier than Started At.")
                return

        # Keep original timestamp precision and note/distraction formatting when
        # the user has not edited those fields (for example, when adding tags).
        if self.started_at.text() == _datetime_to_editor(self.original.get("started_at")):
            started_at = self.original.get("started_at", "")
        if self.ended_at.text() == _datetime_to_editor(self.original.get("ended_at")):
            ended_at = self.original.get("ended_at", "")
        note = self.completion_note.toPlainText()
        if note != (self.original.get("completion_note", "") or ""):
            note = note.strip()
        distraction_text = self.distractions.toPlainText()
        original_distractions = self.original.get("distractions", []) or []
        distractions = (original_distractions if distraction_text == "\n".join(original_distractions)
                        else [line.strip() for line in distraction_text.splitlines() if line.strip()])
        updated = dict(self.original)
        updated.pop("break_seconds", None)
        updated.update({
            "mission": self.mission.text().strip(),
            "tags": self.tags.tags(),
            "preset_name": self.preset_name.text().strip(),
            "preset_id": self.preset_ref.currentData(),
            "mode": self.mode.currentData(),
            "started_at": started_at,
            "ended_at": ended_at,
            "target_seconds": target_seconds,
            "focused_seconds": focused_seconds,
            "completion_note": note,
            "distractions": distractions,
            "music_ids": self._selected_audio_ids(),
            "visual_id": self.visual.currentData(),
        })
        try:
            saved = self.store.update_session(self.original.get("id"), updated)
        except PersistenceError as error:
            QMessageBox.critical(self, "Session Was Not Saved", str(error))
            return
        if not saved:
            QMessageBox.warning(self, "Session Not Found", "This session no longer exists. Your edits have not been saved.")
            return
        self.accept()


