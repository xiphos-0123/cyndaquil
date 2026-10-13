from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .companion import ControlCompanionConfig, StableSpinBox, VisualCompanionConfig
from .media import MediaVisual
from .store import Store
from .utils import reveal_path


class VisualCompanionPreview(QFrame):
    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setObjectName("EmberCard")
        self.setMinimumSize(220, 130)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.visual = MediaVisual(store)
        self.visual.set_fit_mode("contain")
        layout.addWidget(self.visual, 1)

    def set_resource(self, resource_id: str | None) -> None:
        self.visual.set_resource(resource_id)

    def apply_config(self, config: VisualCompanionConfig) -> None:
        if not config.enabled:
            self.hide()
            return
        self.show()
        width = config.width
        height = config.height
        if config.lock_aspect:
            ratio = self.visual.source_aspect_ratio()
            if ratio and ratio > 0:
                height = max(90, round(width / ratio))
        max_w, max_h = 520, 300
        scale = min(max_w / max(width, 1), max_h / max(height, 1), 1.0)
        self.setFixedSize(max(180, int(width * scale)), max(110, int(height * scale)))


class ControlCompanionPreview(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EmberCard")
        self.root = QVBoxLayout(self)
        self.clock = QLabel("00:24:18")
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status = QLabel("FOCUSING")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setObjectName("Muted")

        self.button_host = QWidget()
        self.buttons_layout = QHBoxLayout(self.button_host)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.pause = QPushButton("Pause")
        self.minus = QPushButton("−1")
        self.plus = QPushButton("+1")
        self.main = QPushButton("Main")
        self.finish = QPushButton("✓")
        self.customize = QPushButton("⚙")
        self.buttons = [
            ("pause", self.pause),
            ("minus", self.minus),
            ("plus", self.plus),
            ("main", self.main),
            ("finish", self.finish),
            ("customize", self.customize),
        ]
        for _, button in self.buttons:
            button.setEnabled(False)
            self.buttons_layout.addWidget(button, 1)

        self.root.addWidget(self.clock)
        self.root.addWidget(self.status)
        self.root.addWidget(self.button_host)

    def apply_config(self, config: ControlCompanionConfig) -> None:
        if not config.enabled or not config.any_content():
            self.hide()
            return
        self.show()
        width = min(620, max(220, config.width))
        self.setFixedWidth(width)
        self.root.setContentsMargins(config.padding, config.padding, config.padding, config.padding)
        self.buttons_layout.setSpacing(config.spacing)
        self.clock.setVisible(config.show_timer)
        self.status.setVisible(config.show_status)
        self.pause.setVisible(config.show_pause)
        self.minus.setVisible(config.show_adjust)
        self.plus.setVisible(config.show_adjust)
        self.main.setVisible(config.show_main)
        self.finish.setVisible(config.show_finish)
        self.customize.setVisible(config.show_customize)
        self.clock.setStyleSheet(
            f"font-size:{config.clock_size}px; font-weight:900; color:#FFD16A; background:transparent;"
        )
        for _, button in self.buttons:
            button.setFixedHeight(config.button_height)
            button.setStyleSheet(f"font-size:{config.button_size}px; padding:2px 5px;")
        self.setFixedHeight(self.sizeHint().height())


class SettingsPage(QWidget):
    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self._current_visual_id = None
        self._loading_visual_framing = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        title = QLabel("Application Settings")
        title.setObjectName("Title")
        subtitle = QLabel(
            "Configure application appearance, Default preset ambience, session behavior, and the two independent companion windows."
        )
        subtitle.setObjectName("Muted")
        root.addWidget(title)
        root.addWidget(subtitle)

        # ---------- appearance ----------
        appearance = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance)
        self.font = QComboBox()
        self.font.addItems(QFontDatabase.families())
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 22)

        icon_panel = QWidget()
        icon_layout = QHBoxLayout(icon_panel)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(54, 54)
        self.icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.choose_icon = QPushButton("Choose Application Icon…")
        self.reset_icon = QPushButton("Restore Fallback Icon")
        icon_layout.addWidget(self.icon_preview)
        icon_layout.addWidget(self.choose_icon)
        icon_layout.addWidget(self.reset_icon)
        icon_layout.addStretch()

        appearance_form.addRow("Application Font", self.font)
        appearance_form.addRow("Font Size", self.font_size)
        appearance_form.addRow("Application Icon", icon_panel)
        icon_note = QLabel(
            "This icon is used only by the running Cyndaquil application, including the taskbar, system tray, and in-app branding."
        )
        icon_note.setWordWrap(True)
        icon_note.setObjectName("Muted")
        appearance_form.addRow("", icon_note)

        # ---------- default ambience ----------
        defaults = QGroupBox("Default Preset Ambience")
        defaults_form = QFormLayout(defaults)
        self.audio_status = QLabel(); self.audio_status.setObjectName("Muted")
        self.visual_status = QLabel(); self.visual_status.setObjectName("Muted")

        audio_controls = QWidget(); audio_row = QHBoxLayout(audio_controls); audio_row.setContentsMargins(0,0,0,0)
        self.choose_audio = QPushButton("Choose Default Audio…")
        self.reset_audio = QPushButton("Use Generated Audio")
        audio_row.addWidget(self.choose_audio); audio_row.addWidget(self.reset_audio); audio_row.addStretch()

        visual_controls = QWidget(); visual_row = QHBoxLayout(visual_controls); visual_row.setContentsMargins(0,0,0,0)
        self.choose_visual = QPushButton("Choose Default Visual…")
        self.reset_visual = QPushButton("Use Generated Visual")
        visual_row.addWidget(self.choose_visual); visual_row.addWidget(self.reset_visual); visual_row.addStretch()

        defaults_form.addRow("Default Audio", self.audio_status)
        defaults_form.addRow("", audio_controls)
        defaults_form.addRow("Default Visual", self.visual_status)
        defaults_form.addRow("", visual_controls)

        # ---------- session behavior ----------
        session = QGroupBox("Session Behavior")
        session_form = QFormLayout(session)
        self.ritual_seconds = QSpinBox(); self.ritual_seconds.setRange(0, 30); self.ritual_seconds.setSuffix(" sec")
        self.volume = QSpinBox(); self.volume.setRange(0, 100); self.volume.setSuffix("%")
        session_form.addRow("Session Start Delay", self.ritual_seconds)
        session_form.addRow("Default Audio Volume", self.volume)

        # ---------- inactivity ----------
        idle = QGroupBox("Inactivity Check")
        idle_form = QFormLayout(idle)
        self.idle_enabled = QCheckBox("Ask whether the session should continue after prolonged inactivity")
        self.idle_minutes = QSpinBox(); self.idle_minutes.setRange(1, 180); self.idle_minutes.setSuffix(" min")
        idle_form.addRow("", self.idle_enabled)
        idle_form.addRow("Prompt After", self.idle_minutes)

        # ---------- companions ----------
        companion = QGroupBox("Floating Companions")
        companion_root = QVBoxLayout(companion)

        preview_row = QHBoxLayout()
        preview_label = QLabel("Preview Preset")
        self.preview_preset = QComboBox()
        preview_row.addWidget(preview_label)
        preview_row.addWidget(self.preview_preset, 1)
        preview_row.addStretch()
        companion_root.addLayout(preview_row)

        columns = QHBoxLayout()
        columns.setSpacing(20)

        visual_group = QGroupBox("Visual Companion")
        visual_form = QFormLayout(visual_group)
        self.visual_enabled = QCheckBox("Enable Visual Companion")
        self.visual_width = StableSpinBox(); self.visual_width.setRange(120, 2200); self.visual_width.setSuffix(" px")
        self.visual_height = StableSpinBox(); self.visual_height.setRange(90, 1600); self.visual_height.setSuffix(" px")
        self.visual_lock = QCheckBox("Lock to Visual Aspect Ratio")
        self.visual_opacity = StableSpinBox(); self.visual_opacity.setRange(35, 100); self.visual_opacity.setSuffix("%")
        self.visual_fit = QComboBox()
        self.visual_fit.addItem("Contain — Show Entire Visual", "contain")
        self.visual_fit.addItem("Cover — Fill and Crop", "cover")
        self.visual_fit.addItem("Stretch — Fill Exactly", "stretch")
        self.visual_zoom = StableSpinBox(); self.visual_zoom.setRange(100, 400); self.visual_zoom.setSuffix("%")
        self.visual_pan_x = StableSpinBox(); self.visual_pan_x.setRange(-100, 100); self.visual_pan_x.setSuffix("%")
        self.visual_pan_y = StableSpinBox(); self.visual_pan_y.setRange(-100, 100); self.visual_pan_y.setSuffix("%")
        self.visual_framing_status = QLabel(""); self.visual_framing_status.setObjectName("Muted")
        self.reset_visual_framing = QPushButton("Reset Visual Framing")
        visual_form.addRow("", self.visual_enabled)
        visual_form.addRow("Width", self.visual_width)
        visual_form.addRow("Height", self.visual_height)
        visual_form.addRow("", self.visual_lock)
        visual_form.addRow("Opacity", self.visual_opacity)
        visual_form.addRow("Fit Mode", self.visual_fit)
        visual_form.addRow("Crop Zoom", self.visual_zoom)
        visual_form.addRow("Horizontal Crop", self.visual_pan_x)
        visual_form.addRow("Vertical Crop", self.visual_pan_y)
        framing_row = QHBoxLayout(); framing_row.addWidget(self.visual_framing_status); framing_row.addStretch(); framing_row.addWidget(self.reset_visual_framing)
        visual_form.addRow("", framing_row)
        visual_note = QLabel("Framing is saved per visual resource, so portrait videos and widescreen visuals can use different crops. Double-click the live visual companion to return to the main window.")
        visual_note.setWordWrap(True); visual_note.setObjectName("Muted")
        visual_form.addRow("", visual_note)
        self.visual_preview = VisualCompanionPreview(store)
        visual_form.addRow("Live Preview", self.visual_preview)

        control_group = QGroupBox("Control Companion")
        control_form = QFormLayout(control_group)
        self.control_enabled = QCheckBox("Enable Control Companion")
        self.control_width = StableSpinBox(); self.control_width.setRange(150, 1800); self.control_width.setSuffix(" px")
        self.control_opacity = StableSpinBox(); self.control_opacity.setRange(35, 100); self.control_opacity.setSuffix("%")
        self.control_clock_size = StableSpinBox(); self.control_clock_size.setRange(12, 120); self.control_clock_size.setSuffix(" px")
        self.control_button_size = StableSpinBox(); self.control_button_size.setRange(7, 32); self.control_button_size.setSuffix(" px")
        self.control_button_height = StableSpinBox(); self.control_button_height.setRange(20, 80); self.control_button_height.setSuffix(" px")
        self.control_padding = StableSpinBox(); self.control_padding.setRange(0, 30); self.control_padding.setSuffix(" px")
        self.control_spacing = StableSpinBox(); self.control_spacing.setRange(0, 20); self.control_spacing.setSuffix(" px")
        control_form.addRow("", self.control_enabled)
        control_form.addRow("Width", self.control_width)
        control_form.addRow("Opacity", self.control_opacity)
        control_form.addRow("Timer Text Size", self.control_clock_size)
        control_form.addRow("Button Text Size", self.control_button_size)
        control_form.addRow("Button Height", self.control_button_height)
        control_form.addRow("Panel Padding", self.control_padding)
        control_form.addRow("Button Spacing", self.control_spacing)

        visible = QGroupBox("Visible Items")
        visible_grid = QGridLayout(visible)
        self.show_timer = QCheckBox("Timer")
        self.show_status = QCheckBox("Session Status")
        self.show_pause = QCheckBox("Pause / Resume")
        self.show_adjust = QCheckBox("−1 / +1 Minute")
        self.show_main = QCheckBox("Main Window")
        self.show_finish = QCheckBox("Finish Session")
        self.show_customize = QCheckBox("Customize")
        for i, widget in enumerate((self.show_timer, self.show_status, self.show_pause, self.show_adjust, self.show_main, self.show_finish, self.show_customize)):
            visible_grid.addWidget(widget, i // 2, i % 2)
        control_form.addRow("", visible)
        self.control_preview = ControlCompanionPreview()
        control_form.addRow("Live Preview", self.control_preview)

        columns.addWidget(visual_group, 1)
        columns.addWidget(control_group, 1)
        companion_root.addLayout(columns)

        companion_note = QLabel(
            "The two windows are independent. Disable either one, or disable both if you do not want a Floating Companion. "
            "Changes below are previewed immediately but are saved only when you press Save Companion Configuration or Save Settings."
        )
        companion_note.setWordWrap(True); companion_note.setObjectName("Muted")
        companion_root.addWidget(companion_note)

        companion_save_row = QHBoxLayout()
        self.companion_saved = QLabel(""); self.companion_saved.setObjectName("Muted")
        self.save_companion = QPushButton("Save Companion Configuration"); self.save_companion.setObjectName("Warm")
        companion_save_row.addWidget(self.companion_saved); companion_save_row.addStretch(); companion_save_row.addWidget(self.save_companion)
        companion_root.addLayout(companion_save_row)

        # ---------- resources ----------
        library = QGroupBox("Resource Library")
        library_layout = QHBoxLayout(library)
        library_text = QLabel("Files placed inside the resources folder are detected automatically. Run a manual scan when you want immediate reconciliation.")
        library_text.setWordWrap(True)
        self.scan_resources = QPushButton("Scan Resource Library")
        self.open_resources = QPushButton("Open Resource Library Folder")
        library_layout.addWidget(library_text, 1)
        library_layout.addWidget(self.scan_resources)
        library_layout.addWidget(self.open_resources)

        self.saved_label = QLabel(""); self.saved_label.setObjectName("Muted")
        self.save_button = QPushButton("Save Settings"); self.save_button.setObjectName("Primary")
        save_row = QHBoxLayout(); save_row.addWidget(self.saved_label); save_row.addStretch(); save_row.addWidget(self.save_button)

        for group in (appearance, defaults, session, idle, companion, library):
            root.addWidget(group)
        root.addLayout(save_row)
        root.addStretch()

        self._connect()
        self.load()

    def _connect(self) -> None:
        self.save_button.clicked.connect(self.save_settings)
        self.save_companion.clicked.connect(self.save_companion_settings)
        self.choose_icon.clicked.connect(self._choose_icon)
        self.reset_icon.clicked.connect(self.store.reset_custom_icon)
        self.choose_audio.clicked.connect(self._choose_audio)
        self.reset_audio.clicked.connect(self.store.reset_default_audio)
        self.choose_visual.clicked.connect(self._choose_visual)
        self.reset_visual.clicked.connect(self.store.reset_default_visual)
        self.scan_resources.clicked.connect(self._scan_resources)
        self.open_resources.clicked.connect(lambda: reveal_path(self.store.resources_dir))
        self.preview_preset.currentIndexChanged.connect(self._preview_preset_changed)
        self.store.presets_changed.connect(self._refresh_presets)
        self.store.resources_changed.connect(self._preview_preset_changed)
        self.store.branding_changed.connect(self._refresh_asset_status)
        self.store.defaults_changed.connect(self._refresh_asset_status)
        self.reset_visual_framing.clicked.connect(self._reset_visual_framing)
        self.visual_fit.currentIndexChanged.connect(self._save_visual_framing)
        for widget in (self.visual_zoom, self.visual_pan_x, self.visual_pan_y):
            widget.editingFinished.connect(self._save_visual_framing)

        companion_widgets = [
            self.visual_width, self.visual_height, self.visual_opacity,
            self.control_width, self.control_opacity, self.control_clock_size,
            self.control_button_size, self.control_button_height,
            self.control_padding, self.control_spacing,
        ]
        for widget in companion_widgets:
            widget.valueChanged.connect(self._update_companion_preview)
        for widget in (
            self.visual_enabled, self.control_enabled,
            self.show_timer, self.show_status, self.show_pause, self.show_adjust,
            self.show_main, self.show_finish, self.show_customize,
        ):
            widget.toggled.connect(self._update_companion_preview)
        self.visual_lock.toggled.connect(self._visual_lock_changed)

    def _visual_lock_changed(self, checked: bool) -> None:
        self.visual_height.setEnabled(not checked)
        self._update_companion_preview()

    def _visual_config(self) -> VisualCompanionConfig:
        return VisualCompanionConfig(
            enabled=self.visual_enabled.isChecked(),
            width=self.visual_width.value(),
            height=self.visual_height.value(),
            lock_aspect=self.visual_lock.isChecked(),
            opacity=self.visual_opacity.value(),
        )

    def _control_config(self) -> ControlCompanionConfig:
        return ControlCompanionConfig(
            enabled=self.control_enabled.isChecked(),
            width=self.control_width.value(),
            opacity=self.control_opacity.value(),
            clock_size=self.control_clock_size.value(),
            button_size=self.control_button_size.value(),
            button_height=self.control_button_height.value(),
            padding=self.control_padding.value(),
            spacing=self.control_spacing.value(),
            show_timer=self.show_timer.isChecked(),
            show_status=self.show_status.isChecked(),
            show_pause=self.show_pause.isChecked(),
            show_adjust=self.show_adjust.isChecked(),
            show_main=self.show_main.isChecked(),
            show_finish=self.show_finish.isChecked(),
            show_customize=self.show_customize.isChecked(),
        )

    def _companion_values(self) -> dict:
        result = self._visual_config().to_dict()
        result.update(self._control_config().to_dict())
        return result

    def _general_values(self) -> dict:
        return {
            "font_family": self.font.currentText(),
            "font_size": self.font_size.value(),
            "ritual_seconds": self.ritual_seconds.value(),
            "audio_volume": self.volume.value(),
            "idle_enabled": self.idle_enabled.isChecked(),
            "idle_minutes": self.idle_minutes.value(),
        }

    def load(self) -> None:
        s = self.store.settings
        self.font.setCurrentText(s.get("font_family", "Segoe UI"))
        self.font_size.setValue(int(s.get("font_size", 10)))
        self.ritual_seconds.setValue(int(s.get("ritual_seconds", 0)))
        self.volume.setValue(int(s.get("audio_volume", 55)))
        self.idle_enabled.setChecked(bool(s.get("idle_enabled", True)))
        self.idle_minutes.setValue(int(s.get("idle_minutes", 8)))

        visual = VisualCompanionConfig.from_mapping(s)
        control = ControlCompanionConfig.from_mapping(s)
        self.visual_enabled.setChecked(visual.enabled)
        self.visual_width.setValue(visual.width)
        self.visual_height.setValue(visual.height)
        self.visual_lock.setChecked(visual.lock_aspect)
        self.visual_height.setEnabled(not visual.lock_aspect)
        self.visual_opacity.setValue(visual.opacity)

        self.control_enabled.setChecked(control.enabled)
        self.control_width.setValue(control.width)
        self.control_opacity.setValue(control.opacity)
        self.control_clock_size.setValue(control.clock_size)
        self.control_button_size.setValue(control.button_size)
        self.control_button_height.setValue(control.button_height)
        self.control_padding.setValue(control.padding)
        self.control_spacing.setValue(control.spacing)
        self.show_timer.setChecked(control.show_timer)
        self.show_status.setChecked(control.show_status)
        self.show_pause.setChecked(control.show_pause)
        self.show_adjust.setChecked(control.show_adjust)
        self.show_main.setChecked(control.show_main)
        self.show_finish.setChecked(control.show_finish)
        self.show_customize.setChecked(control.show_customize)

        self._refresh_presets()
        self._refresh_asset_status()
        self._update_companion_preview()

    def save_companion_settings(self) -> None:
        self.store.update_settings(self._companion_values())
        self.companion_saved.setText("Companion Configuration Saved")
        QTimer.singleShot(1800, self.companion_saved.clear)

    def save_settings(self) -> None:
        values = self._general_values()
        values.update(self._companion_values())
        self.store.update_settings(values)
        self.saved_label.setText("Settings Saved")
        self.save_button.setText("Saved")
        QTimer.singleShot(1800, self._clear_saved)

    def _clear_saved(self) -> None:
        self.saved_label.clear()
        self.save_button.setText("Save Settings")

    def _refresh_presets(self) -> None:
        current = self.preview_preset.currentData()
        self.preview_preset.blockSignals(True)
        self.preview_preset.clear()
        for preset in self.store.presets:
            self.preview_preset.addItem(preset.get("name", "Preset"), preset.get("id"))
        self.preview_preset.blockSignals(False)
        index = self.preview_preset.findData(current)
        self.preview_preset.setCurrentIndex(index if index >= 0 else 0)
        self._preview_preset_changed()

    def _preview_preset_changed(self, *args) -> None:
        preset = self.store.preset_by_id(self.preview_preset.currentData())
        self._current_visual_id = preset.get("visual_id") if preset else None
        self.visual_preview.set_resource(self._current_visual_id)
        self._load_visual_framing()
        self._update_companion_preview()

    def _load_visual_framing(self) -> None:
        self._loading_visual_framing = True
        framing = self.store.visual_framing(self._current_visual_id)
        index = self.visual_fit.findData(framing.get("fit", "contain"))
        self.visual_fit.setCurrentIndex(index if index >= 0 else 0)
        self.visual_zoom.setValue(int(framing.get("zoom", 100)))
        self.visual_pan_x.setValue(int(framing.get("pan_x", 0)))
        self.visual_pan_y.setValue(int(framing.get("pan_y", 0)))
        enabled = self._current_visual_id is not None
        for widget in (self.visual_fit, self.visual_zoom, self.visual_pan_x, self.visual_pan_y, self.reset_visual_framing):
            widget.setEnabled(enabled)
        self.visual_framing_status.setText("" if enabled else "Select a preset with a visual to edit framing")
        self._loading_visual_framing = False

    def _save_visual_framing(self, *args) -> None:
        if self._loading_visual_framing or not self._current_visual_id:
            return
        framing = {
            "fit": self.visual_fit.currentData() or "contain",
            "zoom": self.visual_zoom.value(),
            "pan_x": self.visual_pan_x.value(),
            "pan_y": self.visual_pan_y.value(),
        }
        self.store.update_visual_framing(self._current_visual_id, framing)
        self.visual_preview.visual.set_framing(**framing)
        self.visual_framing_status.setText("Visual Framing Saved")
        QTimer.singleShot(1600, lambda: self.visual_framing_status.setText(""))

    def _reset_visual_framing(self) -> None:
        if not self._current_visual_id:
            return
        self.store.reset_visual_framing(self._current_visual_id)
        self._load_visual_framing()
        self.visual_preview.visual.set_framing(fit="contain", zoom=100, pan_x=0, pan_y=0)
        self.visual_framing_status.setText("Visual Framing Reset")
        QTimer.singleShot(1600, lambda: self.visual_framing_status.setText(""))

    def _update_companion_preview(self, *args) -> None:
        self.visual_preview.apply_config(self._visual_config())
        self.control_preview.apply_config(self._control_config())

    def _refresh_asset_status(self) -> None:
        pixmap = QPixmap(str(self.store.current_icon_path()))
        if not pixmap.isNull():
            self.icon_preview.setPixmap(
                pixmap.scaled(self.icon_preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        custom_icon = self.store._resolve_setting_path("custom_icon_path")
        self.reset_icon.setEnabled(custom_icon is not None)
        audio_custom = self.store._resolve_setting_path("default_audio_path")
        visual_custom = self.store._resolve_setting_path("default_visual_path")
        self.audio_status.setText(f"Custom: {audio_custom.name}" if audio_custom else "Generated fallback ambience")
        self.visual_status.setText(f"Custom: {visual_custom.name}" if visual_custom else "Generated fallback visual")
        self.reset_audio.setEnabled(audio_custom is not None)
        self.reset_visual.setEnabled(visual_custom is not None)
        self._preview_preset_changed()

    def _choose_icon(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose Application Icon", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            try:
                self.store.set_custom_icon(Path(path))
            except Exception as exc:
                QMessageBox.warning(self, "Icon Update Failed", str(exc))

    def _choose_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose Default Audio", "", "Audio (*.mp3 *.wav *.ogg *.flac *.m4a *.aac)")
        if path:
            try:
                self.store.set_default_audio(Path(path))
            except Exception as exc:
                QMessageBox.warning(self, "Audio Update Failed", str(exc))

    def _choose_visual(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Default Visual",
            "",
            "Visual Media (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.mp4 *.mkv *.mov *.avi *.webm *.m4v)",
        )
        if path:
            try:
                self.store.set_default_visual(Path(path))
            except Exception as exc:
                QMessageBox.warning(self, "Visual Update Failed", str(exc))

    def _scan_resources(self) -> None:
        result = self.store.repair_resources()
        QMessageBox.information(
            self,
            "Resource Library Scan",
            "Resource Library scan completed.\n\n"
            f"Added: {result['added']}\n"
            f"Removed: {result['removed']}\n"
            f"Relinked: {result['repaired']}\n"
            f"Backup Fallbacks Available: {result['backup_ready']}",
        )
