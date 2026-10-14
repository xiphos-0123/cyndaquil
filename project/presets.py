from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .store import Store
from .utils import new_id


class PresetsPage(QWidget):
    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self.music_boxes: dict[str, QCheckBox] = {}
        self.current_id: str | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)

        left = QFrame()
        left.setObjectName("Card")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Focus Presets")
        title.setObjectName("SectionTitle")
        description = QLabel(
            "Save reusable combinations of session mode, audio, and visual ambience."
        )
        description.setWordWrap(True)
        description.setObjectName("Muted")

        self.list = QListWidget()

        self.new_btn = QPushButton("New Preset")
        self.duplicate_btn = QPushButton("Duplicate")
        self.delete_btn = QPushButton("Delete")
        button_row = QHBoxLayout()
        button_row.addWidget(self.new_btn)
        button_row.addWidget(self.duplicate_btn)
        button_row.addWidget(self.delete_btn)

        left_layout.addWidget(title)
        left_layout.addWidget(description)
        left_layout.addWidget(self.list, 1)
        left_layout.addLayout(button_row)
        left.setMaximumWidth(340)

        editor = QFrame()
        editor.setObjectName("EmberCard")
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(22, 20, 22, 20)

        editor_title = QLabel("Preset Configuration")
        editor_title.setObjectName("SectionTitle")

        self.name = QLineEdit()

        self.mode = QComboBox()
        self.mode.addItem("Stopwatch", "stopwatch")
        self.mode.addItem("Timer", "timer")

        self.minutes_row = QWidget()
        minutes_layout = QHBoxLayout(self.minutes_row)
        minutes_layout.setContentsMargins(0, 0, 0, 0)
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 720)
        self.minutes.setSuffix(" min")
        minutes_layout.addWidget(QLabel("Timer Duration"))
        minutes_layout.addWidget(self.minutes)
        minutes_layout.addStretch()

        self.visual = QComboBox()

        music_label = QLabel("Audio Playlist")
        music_label.setObjectName("SectionTitle")

        self.music_content = QWidget()
        self.music_layout = QVBoxLayout(self.music_content)
        self.music_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.music_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.music_content)
        scroll.setMinimumHeight(220)

        self.save_status = QLabel("")
        self.save_status.setObjectName("Muted")
        self.save_btn = QPushButton("Save Preset")
        self.save_btn.setObjectName("Primary")

        save_row = QHBoxLayout()
        save_row.addWidget(self.save_status)
        save_row.addStretch()
        save_row.addWidget(self.save_btn)

        editor_layout.addWidget(editor_title)
        editor_layout.addWidget(QLabel("Preset Name"))
        editor_layout.addWidget(self.name)
        editor_layout.addWidget(QLabel("Session Mode"))
        editor_layout.addWidget(self.mode)
        editor_layout.addWidget(self.minutes_row)
        editor_layout.addWidget(QLabel("Visual Ambience"))
        editor_layout.addWidget(self.visual)
        editor_layout.addWidget(music_label)
        editor_layout.addWidget(scroll, 1)
        editor_layout.addLayout(save_row)

        root.addWidget(left)
        root.addWidget(editor, 1)

        self.list.currentItemChanged.connect(self._selection_changed)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.save_btn.clicked.connect(self.save_current)
        self.new_btn.clicked.connect(self.new_preset)
        self.duplicate_btn.clicked.connect(self.duplicate_preset)
        self.delete_btn.clicked.connect(self.delete_preset)

        store.presets_changed.connect(self.refresh)
        store.resources_changed.connect(self.refresh_resources)
        store.defaults_changed.connect(self.refresh_resources)

        self.refresh()

    def refresh(self) -> None:
        wanted = self.current_id
        self.list.blockSignals(True)
        self.list.clear()

        for preset in self.store.presets:
            name = preset.get("name", "Preset")
            if preset.get("id") == "default":
                name = "Default  •  Permanent"
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, preset.get("id"))
            self.list.addItem(item)

        self.list.blockSignals(False)

        row = 0
        if wanted:
            for index in range(self.list.count()):
                if self.list.item(index).data(Qt.ItemDataRole.UserRole) == wanted:
                    row = index
                    break

        self.list.setCurrentRow(row)
        self._selection_changed(self.list.currentItem(), None)

    def refresh_resources(self) -> None:
        preset = self.store.preset_by_id(self.current_id) or {}
        selected_music = set(preset.get("music_ids", []))
        current_visual = preset.get("visual_id")

        while self.music_layout.count():
            item = self.music_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.music_boxes.clear()

        audio_count = 0
        for resource in self.store.resources:
            if resource.get("kind") != "audio":
                continue

            rid = resource.get("id")
            status = self.store.resource_status(rid)
            label = resource.get("name", "Audio")
            if status != "Available":
                label += f"  [{status}]"

            box = QCheckBox(label)
            box.setChecked(rid in selected_music)
            self.music_layout.addWidget(box)
            self.music_boxes[rid] = box
            audio_count += 1

        if audio_count == 0:
            empty = QLabel("No audio resources are available.")
            empty.setObjectName("Muted")
            self.music_layout.addWidget(empty)

        self.music_layout.addStretch()

        self.visual.blockSignals(True)
        self.visual.clear()
        self.visual.addItem("No Visual", None)

        for resource in self.store.resources:
            if resource.get("kind") not in {"image", "gif", "video"}:
                continue

            rid = resource.get("id")
            status = self.store.resource_status(rid)
            label = resource.get("name", "Visual")
            if status != "Available":
                label += f"  [{status}]"
            self.visual.addItem(label, rid)

        index = self.visual.findData(current_visual)
        self.visual.setCurrentIndex(index if index >= 0 else 0)
        self.visual.blockSignals(False)

    def _selection_changed(self, current, previous) -> None:
        if not current:
            return

        self.current_id = current.data(Qt.ItemDataRole.UserRole)
        preset = self.store.preset_by_id(self.current_id)
        if not preset:
            return

        self.save_status.clear()
        self.name.setText(preset.get("name", ""))
        self.name.setEnabled(self.current_id != "default")

        mode_index = self.mode.findData(preset.get("mode", "stopwatch"))
        self.mode.setCurrentIndex(mode_index if mode_index >= 0 else 0)
        self.minutes.setValue(max(1, int(preset.get("minutes", 50))))

        self.refresh_resources()
        self._mode_changed()

        self.delete_btn.setEnabled(self.current_id != "default")

    def _mode_changed(self) -> None:
        self.minutes_row.setVisible(self.mode.currentData() == "timer")

    def save_current(self) -> None:
        if not self.current_id:
            return

        music = [rid for rid, box in self.music_boxes.items() if box.isChecked()]

        preset = {
            "id": self.current_id,
            "name": (
                "Default"
                if self.current_id == "default"
                else (self.name.text().strip() or "Untitled Preset")
            ),
            "mode": self.mode.currentData() or "stopwatch",
            "minutes": self.minutes.value(),
            "music_ids": music,
            "visual_id": self.visual.currentData(),
        }

        self.store.upsert_preset(preset)
        self.save_status.setText("Preset Saved")
        self.save_btn.setText("Saved")
        QTimer.singleShot(1700, self._clear_saved_indicator)

    def _clear_saved_indicator(self) -> None:
        self.save_status.clear()
        self.save_btn.setText("Save Preset")

    def new_preset(self) -> None:
        preset = {
            "id": new_id(),
            "name": "New Preset",
            "mode": "stopwatch",
            "minutes": 50,
            "music_ids": [],
            "visual_id": None,
        }
        self.current_id = preset["id"]
        self.store.upsert_preset(preset)

    def duplicate_preset(self) -> None:
        source = self.store.preset_by_id(self.current_id)
        if not source:
            return

        copy = deepcopy(source)
        copy["id"] = new_id()
        copy["name"] = f"{source.get('name', 'Preset')} Copy"
        self.current_id = copy["id"]
        self.store.upsert_preset(copy)

    def delete_preset(self) -> None:
        if not self.current_id:
            return

        if self.current_id == "default":
            QMessageBox.information(
                self,
                "Default Preset",
                "The Default preset is permanent. You can edit it, but it cannot be deleted.",
            )
            return

        preset = self.store.preset_by_id(self.current_id)
        if not preset:
            return

        if (
            QMessageBox.question(
                self,
                "Delete Preset",
                f"Delete “{preset.get('name', 'Preset')}”?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.current_id = "default"
            self.store.delete_preset(preset.get("id"))
