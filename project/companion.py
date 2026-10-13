from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QContextMenuEvent, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizeGrip,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .media import MediaVisual
from .session import SessionManager
from .store import DEFAULT_SETTINGS, Store
from .utils import format_seconds


VISUAL_KEYS = (
    "visual_companion_enabled",
    "visual_companion_width",
    "visual_companion_height",
    "visual_companion_lock_aspect",
    "visual_companion_opacity",
)

CONTROL_KEYS = (
    "control_companion_enabled",
    "control_companion_width",
    "control_companion_opacity",
    "control_companion_clock_size",
    "control_companion_button_size",
    "control_companion_button_height",
    "control_companion_padding",
    "control_companion_spacing",
    "control_companion_show_timer",
    "control_companion_show_status",
    "control_companion_show_pause",
    "control_companion_show_adjust",
    "control_companion_show_main",
    "control_companion_show_finish",
    "control_companion_show_customize",
)


class StableSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setKeyboardTracking(False)

    def wheelEvent(self, event):
        event.ignore()


@dataclass
class VisualCompanionConfig:
    enabled: bool = True
    width: int = 480
    height: int = 270
    lock_aspect: bool = True
    opacity: int = 100

    @classmethod
    def from_mapping(cls, mapping: dict) -> "VisualCompanionConfig":
        return cls(
            enabled=bool(mapping.get("visual_companion_enabled", DEFAULT_SETTINGS["visual_companion_enabled"])),
            width=max(120, min(2200, int(mapping.get("visual_companion_width", DEFAULT_SETTINGS["visual_companion_width"])))),
            height=max(90, min(1600, int(mapping.get("visual_companion_height", DEFAULT_SETTINGS["visual_companion_height"])))),
            lock_aspect=bool(mapping.get("visual_companion_lock_aspect", DEFAULT_SETTINGS["visual_companion_lock_aspect"])),
            opacity=max(35, min(100, int(mapping.get("visual_companion_opacity", DEFAULT_SETTINGS["visual_companion_opacity"])))),
        )

    def to_dict(self) -> dict:
        return {
            "visual_companion_enabled": self.enabled,
            "visual_companion_width": self.width,
            "visual_companion_height": self.height,
            "visual_companion_lock_aspect": self.lock_aspect,
            "visual_companion_opacity": self.opacity,
        }


@dataclass
class ControlCompanionConfig:
    enabled: bool = True
    width: int = 360
    opacity: int = 96
    clock_size: int = 32
    button_size: int = 10
    button_height: int = 30
    padding: int = 8
    spacing: int = 4
    show_timer: bool = True
    show_status: bool = False
    show_pause: bool = True
    show_adjust: bool = True
    show_main: bool = True
    show_finish: bool = False
    show_customize: bool = True

    @classmethod
    def from_mapping(cls, mapping: dict) -> "ControlCompanionConfig":
        return cls(
            enabled=bool(mapping.get("control_companion_enabled", DEFAULT_SETTINGS["control_companion_enabled"])),
            width=max(150, min(1800, int(mapping.get("control_companion_width", DEFAULT_SETTINGS["control_companion_width"])))),
            opacity=max(35, min(100, int(mapping.get("control_companion_opacity", DEFAULT_SETTINGS["control_companion_opacity"])))),
            clock_size=max(12, min(120, int(mapping.get("control_companion_clock_size", DEFAULT_SETTINGS["control_companion_clock_size"])))),
            button_size=max(7, min(32, int(mapping.get("control_companion_button_size", DEFAULT_SETTINGS["control_companion_button_size"])))),
            button_height=max(20, min(80, int(mapping.get("control_companion_button_height", DEFAULT_SETTINGS["control_companion_button_height"])))),
            padding=max(0, min(30, int(mapping.get("control_companion_padding", DEFAULT_SETTINGS["control_companion_padding"])))),
            spacing=max(0, min(20, int(mapping.get("control_companion_spacing", DEFAULT_SETTINGS["control_companion_spacing"])))),
            show_timer=bool(mapping.get("control_companion_show_timer", DEFAULT_SETTINGS["control_companion_show_timer"])),
            show_status=bool(mapping.get("control_companion_show_status", DEFAULT_SETTINGS["control_companion_show_status"])),
            show_pause=bool(mapping.get("control_companion_show_pause", DEFAULT_SETTINGS["control_companion_show_pause"])),
            show_adjust=bool(mapping.get("control_companion_show_adjust", DEFAULT_SETTINGS["control_companion_show_adjust"])),
            show_main=bool(mapping.get("control_companion_show_main", DEFAULT_SETTINGS["control_companion_show_main"])),
            show_finish=bool(mapping.get("control_companion_show_finish", DEFAULT_SETTINGS["control_companion_show_finish"])),
            show_customize=bool(mapping.get("control_companion_show_customize", DEFAULT_SETTINGS["control_companion_show_customize"])),
        )

    def to_dict(self) -> dict:
        return {
            "control_companion_enabled": self.enabled,
            "control_companion_width": self.width,
            "control_companion_opacity": self.opacity,
            "control_companion_clock_size": self.clock_size,
            "control_companion_button_size": self.button_size,
            "control_companion_button_height": self.button_height,
            "control_companion_padding": self.padding,
            "control_companion_spacing": self.spacing,
            "control_companion_show_timer": self.show_timer,
            "control_companion_show_status": self.show_status,
            "control_companion_show_pause": self.show_pause,
            "control_companion_show_adjust": self.show_adjust,
            "control_companion_show_main": self.show_main,
            "control_companion_show_finish": self.show_finish,
            "control_companion_show_customize": self.show_customize,
        }

    def any_content(self) -> bool:
        return any((
            self.show_timer,
            self.show_status,
            self.show_pause,
            self.show_adjust,
            self.show_main,
            self.show_finish,
            self.show_customize,
        ))


def companion_configs(mapping: dict) -> tuple[VisualCompanionConfig, ControlCompanionConfig]:
    return VisualCompanionConfig.from_mapping(mapping), ControlCompanionConfig.from_mapping(mapping)


class DraggableToolWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._drag_offset: QPoint | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class VisualCompanionWindow(DraggableToolWindow):
    main_requested = Signal()
    customize_requested = Signal()

    def __init__(self, store: Store, session: SessionManager):
        super().__init__()
        self.store = store
        self.session = session
        self._config = VisualCompanionConfig.from_mapping(store.settings)
        self._aspect_adjusting = False
        self._source_ratio = 16 / 9

        self.setObjectName("VisualCompanion")
        self.setMinimumSize(120, 90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.visual = MediaVisual(store)
        self.visual.set_fit_mode("contain")
        # The standalone visual has no controls of its own. Let mouse events
        # reach the outer window so dragging and double-click-to-main work
        # across the entire visual surface.
        self.visual.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.visual, 1)

        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        self.grip.raise_()

        self.apply_config(self._config, resize_window=True)
        self.set_resource(session.config.get("visual_id"))

    def set_resource(self, resource_id: str | None) -> None:
        if self.visual.set_resource(resource_id):
            QTimer.singleShot(80, self._update_source_ratio)
        else:
            self.hide()

    def _update_source_ratio(self) -> None:
        ratio = self.visual.source_aspect_ratio()
        if ratio and ratio > 0:
            self._source_ratio = ratio
            if self._config.lock_aspect:
                target_h = max(90, round(self.width() / ratio))
                if target_h != self.height():
                    self._aspect_adjusting = True
                    self.resize(self.width(), target_h)
                    self._aspect_adjusting = False

    def apply_config(self, config: VisualCompanionConfig, resize_window: bool = False) -> None:
        self._config = config
        self.setWindowOpacity(config.opacity / 100.0)
        if resize_window:
            self.resize(config.width, config.height)
        self.visual.set_fit_mode("contain")

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.main_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        customize = menu.addAction("Customize Companions…")
        main = menu.addAction("Return to Main Window")
        chosen = menu.exec(event.globalPos())
        if chosen == customize:
            self.customize_requested.emit()
        elif chosen == main:
            self.main_requested.emit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.grip.move(max(0, self.width() - self.grip.width()), max(0, self.height() - self.grip.height()))

        if self._aspect_adjusting or not self._config.lock_aspect or self._source_ratio <= 0:
            return

        old = event.oldSize()
        new = event.size()
        if not old.isValid():
            return
        dw = abs(new.width() - old.width())
        dh = abs(new.height() - old.height())
        self._aspect_adjusting = True
        try:
            if dw >= dh:
                h = max(90, round(new.width() / self._source_ratio))
                if h != new.height():
                    self.resize(new.width(), h)
            else:
                w = max(120, round(new.height() * self._source_ratio))
                if w != new.width():
                    self.resize(w, new.height())
        finally:
            self._aspect_adjusting = False

    def shutdown(self) -> None:
        self.visual.stop()
        self.hide()


class ControlCompanionWindow(DraggableToolWindow):
    pause_requested = Signal()
    adjust_requested = Signal(int)
    main_requested = Signal()
    finish_requested = Signal()
    customize_requested = Signal()

    def __init__(self, store: Store, session: SessionManager):
        super().__init__()
        self.store = store
        self.session = session
        self._config = ControlCompanionConfig.from_mapping(store.settings)

        self.setObjectName("ControlCompanion")
        self.setMinimumWidth(150)

        self.root = QVBoxLayout(self)
        self.root.setSpacing(4)

        self.clock = QLabel("00:00:00")
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status = QLabel("FOCUSING")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setObjectName("Muted")

        self.button_row = QWidget()
        self.buttons_layout = QHBoxLayout(self.button_row)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.pause_btn = QPushButton("Pause")
        self.minus_btn = QPushButton("−1 min")
        self.plus_btn = QPushButton("+1 min")
        self.main_btn = QPushButton("Main")
        self.finish_btn = QPushButton("Finish")
        self.customize_btn = QPushButton("⚙")
        self.customize_btn.setToolTip("Customize Companions")

        self._button_specs = [
            ("pause", self.pause_btn),
            ("minus", self.minus_btn),
            ("plus", self.plus_btn),
            ("main", self.main_btn),
            ("finish", self.finish_btn),
            ("customize", self.customize_btn),
        ]
        for _, button in self._button_specs:
            self.buttons_layout.addWidget(button, 1)

        self.root.addWidget(self.clock)
        self.root.addWidget(self.status)
        self.root.addWidget(self.button_row)

        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(14, 14)
        self.grip.raise_()

        self.pause_btn.clicked.connect(self.pause_requested)
        self.minus_btn.clicked.connect(lambda: self.adjust_requested.emit(-60))
        self.plus_btn.clicked.connect(lambda: self.adjust_requested.emit(60))
        self.main_btn.clicked.connect(self.main_requested)
        self.finish_btn.clicked.connect(self.finish_requested)
        self.customize_btn.clicked.connect(self.customize_requested)

        self.apply_config(self._config, resize_window=True)
        self.refresh()

    def apply_config(self, config: ControlCompanionConfig, resize_window: bool = False) -> None:
        self._config = config
        self.setWindowOpacity(config.opacity / 100.0)
        self.root.setContentsMargins(config.padding, config.padding, config.padding, config.padding)
        self.buttons_layout.setSpacing(config.spacing)

        self.clock.setVisible(config.show_timer)
        self.status.setVisible(config.show_status)
        self.pause_btn.setVisible(config.show_pause)
        self.minus_btn.setVisible(config.show_adjust)
        self.plus_btn.setVisible(config.show_adjust)
        self.main_btn.setVisible(config.show_main)
        self.finish_btn.setVisible(config.show_finish)
        self.customize_btn.setVisible(config.show_customize)

        self.clock.setStyleSheet(
            f"font-size:{config.clock_size}px; font-weight:900; color:#FFD16A; background:transparent;"
        )
        self.status.setStyleSheet("background:transparent; border:none; padding:0px;")
        for _, button in self._button_specs:
            button.setMinimumHeight(config.button_height)
            button.setMaximumHeight(config.button_height)
            button.setStyleSheet(
                f"font-size:{config.button_size}px; padding:2px 5px;"
            )

        if resize_window:
            self.resize(config.width, self.sizeHint().height())
        else:
            self.resize(self.width(), self.sizeHint().height())
        self._refresh_button_labels()

    def has_content(self) -> bool:
        return self._config.any_content()

    def refresh(self) -> None:
        self.clock.setText(format_seconds(self.session.display_seconds()))
        state = self.session.state
        labels = {
            "running": "FOCUSING",
            "paused": "PAUSED",
            "complete": "SESSION COMPLETE",
        }
        self.status.setText(labels.get(state, state.upper()))
        self._refresh_button_labels()

    def _refresh_button_labels(self) -> None:
        visible = [button for _, button in self._button_specs if not button.isHidden()]
        count = max(1, len(visible))
        usable = max(1, self.width() - self._config.padding * 2 - self._config.spacing * (count - 1))
        per_button = usable / count
        running = self.session.state == "running"

        if per_button >= 76:
            labels = {
                "pause": "Pause" if running else "Resume",
                "minus": "−1 min",
                "plus": "+1 min",
                "main": "Main",
                "finish": "Finish",
                "customize": "Customize",
            }
        elif per_button >= 46:
            labels = {
                "pause": "Pause" if running else "Play",
                "minus": "−1",
                "plus": "+1",
                "main": "Main",
                "finish": "✓",
                "customize": "⚙",
            }
        else:
            labels = {
                "pause": "Ⅱ" if running else "▶",
                "minus": "−",
                "plus": "+",
                "main": "M",
                "finish": "✓",
                "customize": "⚙",
            }
        for key, button in self._button_specs:
            button.setText(labels[key])

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        customize = menu.addAction("Customize Companions…")
        main = menu.addAction("Return to Main Window")
        chosen = menu.exec(event.globalPos())
        if chosen == customize:
            self.customize_requested.emit()
        elif chosen == main:
            self.main_requested.emit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.grip.move(max(0, self.width() - self.grip.width()), max(0, self.height() - self.grip.height()))
        self._refresh_button_labels()


class CompanionSettingsDialog(QDialog):
    def __init__(self, store: Store, visual: VisualCompanionWindow | None, control: ControlCompanionWindow | None, parent=None):
        super().__init__(parent)
        self.store = store
        self.visual_window = visual
        self.control_window = control
        self.setWindowTitle("Companion Configuration")

        visual_cfg, control_cfg = companion_configs(store.settings)

        root = QVBoxLayout(self)
        columns = QHBoxLayout()
        columns.setSpacing(18)

        visual_group = QGroupBox("Visual Companion")
        visual_form = QFormLayout(visual_group)
        self.visual_enabled = QCheckBox("Enable Visual Companion")
        self.visual_enabled.setChecked(visual_cfg.enabled)
        self.visual_width = StableSpinBox(); self.visual_width.setRange(120, 2200); self.visual_width.setValue(visual_cfg.width); self.visual_width.setSuffix(" px")
        self.visual_height = StableSpinBox(); self.visual_height.setRange(90, 1600); self.visual_height.setValue(visual_cfg.height); self.visual_height.setSuffix(" px")
        self.visual_lock = QCheckBox("Lock to Visual Aspect Ratio"); self.visual_lock.setChecked(visual_cfg.lock_aspect)
        self.visual_opacity = StableSpinBox(); self.visual_opacity.setRange(35, 100); self.visual_opacity.setValue(visual_cfg.opacity); self.visual_opacity.setSuffix("%")
        visual_form.addRow("", self.visual_enabled)
        visual_form.addRow("Width", self.visual_width)
        visual_form.addRow("Height", self.visual_height)
        visual_form.addRow("", self.visual_lock)
        self.visual_height.setEnabled(not visual_cfg.lock_aspect)
        self.visual_lock.toggled.connect(lambda checked: self.visual_height.setEnabled(not checked))
        visual_form.addRow("Opacity", self.visual_opacity)
        visual_note = QLabel("The visual is its own window. Double-click it to return to the main Cyndaquil window.")
        visual_note.setWordWrap(True); visual_note.setObjectName("Muted")
        visual_form.addRow("", visual_note)

        control_group = QGroupBox("Control Companion")
        control_form = QFormLayout(control_group)
        self.control_enabled = QCheckBox("Enable Control Companion"); self.control_enabled.setChecked(control_cfg.enabled)
        self.control_width = StableSpinBox(); self.control_width.setRange(150, 1800); self.control_width.setValue(control_cfg.width); self.control_width.setSuffix(" px")
        self.control_opacity = StableSpinBox(); self.control_opacity.setRange(35, 100); self.control_opacity.setValue(control_cfg.opacity); self.control_opacity.setSuffix("%")
        self.clock_size = StableSpinBox(); self.clock_size.setRange(12, 120); self.clock_size.setValue(control_cfg.clock_size); self.clock_size.setSuffix(" px")
        self.button_size = StableSpinBox(); self.button_size.setRange(7, 32); self.button_size.setValue(control_cfg.button_size); self.button_size.setSuffix(" px")
        self.button_height = StableSpinBox(); self.button_height.setRange(20, 80); self.button_height.setValue(control_cfg.button_height); self.button_height.setSuffix(" px")
        self.padding = StableSpinBox(); self.padding.setRange(0, 30); self.padding.setValue(control_cfg.padding); self.padding.setSuffix(" px")
        self.spacing = StableSpinBox(); self.spacing.setRange(0, 20); self.spacing.setValue(control_cfg.spacing); self.spacing.setSuffix(" px")
        control_form.addRow("", self.control_enabled)
        control_form.addRow("Width", self.control_width)
        control_form.addRow("Opacity", self.control_opacity)
        control_form.addRow("Timer Text Size", self.clock_size)
        control_form.addRow("Button Text Size", self.button_size)
        control_form.addRow("Button Height", self.button_height)
        control_form.addRow("Panel Padding", self.padding)
        control_form.addRow("Button Spacing", self.spacing)

        visible_group = QGroupBox("Visible Control Companion Items")
        visible_grid = QGridLayout(visible_group)
        self.show_timer = QCheckBox("Timer"); self.show_timer.setChecked(control_cfg.show_timer)
        self.show_status = QCheckBox("Session Status"); self.show_status.setChecked(control_cfg.show_status)
        self.show_pause = QCheckBox("Pause / Resume"); self.show_pause.setChecked(control_cfg.show_pause)
        self.show_adjust = QCheckBox("−1 / +1 Minute"); self.show_adjust.setChecked(control_cfg.show_adjust)
        self.show_main = QCheckBox("Main Window"); self.show_main.setChecked(control_cfg.show_main)
        self.show_finish = QCheckBox("Finish Session"); self.show_finish.setChecked(control_cfg.show_finish)
        self.show_customize = QCheckBox("Customize"); self.show_customize.setChecked(control_cfg.show_customize)
        for i, widget in enumerate((self.show_timer, self.show_status, self.show_pause, self.show_adjust, self.show_main, self.show_finish, self.show_customize)):
            visible_grid.addWidget(widget, i // 2, i % 2)
        control_form.addRow("", visible_group)

        columns.addWidget(visual_group, 1)
        columns.addWidget(control_group, 1)
        root.addLayout(columns)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        screen = None
        if self.parentWidget():
            screen = self.parentWidget().screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(860, 520)
            return
        area = screen.availableGeometry()
        width = min(980, max(720, area.width() - 100))
        height = min(620, max(430, area.height() - 100))
        self.resize(width, height)
        self.move(area.center() - self.rect().center())

    def values(self) -> dict:
        visual = VisualCompanionConfig(
            enabled=self.visual_enabled.isChecked(),
            width=self.visual_width.value(),
            height=self.visual_height.value(),
            lock_aspect=self.visual_lock.isChecked(),
            opacity=self.visual_opacity.value(),
        )
        control = ControlCompanionConfig(
            enabled=self.control_enabled.isChecked(),
            width=self.control_width.value(),
            opacity=self.control_opacity.value(),
            clock_size=self.clock_size.value(),
            button_size=self.button_size.value(),
            button_height=self.button_height.value(),
            padding=self.padding.value(),
            spacing=self.spacing.value(),
            show_timer=self.show_timer.isChecked(),
            show_status=self.show_status.isChecked(),
            show_pause=self.show_pause.isChecked(),
            show_adjust=self.show_adjust.isChecked(),
            show_main=self.show_main.isChecked(),
            show_finish=self.show_finish.isChecked(),
            show_customize=self.show_customize.isChecked(),
        )
        result = visual.to_dict()
        result.update(control.to_dict())
        return result


class CompanionManager(QObject):
    pause_requested = Signal()
    adjust_requested = Signal(int)
    main_requested = Signal()
    finish_requested = Signal()

    def __init__(self, store: Store, session: SessionManager, parent=None):
        super().__init__(parent)
        self.store = store
        self.session = session
        self.visual_window = VisualCompanionWindow(store, session)
        self.control_window = ControlCompanionWindow(store, session)
        self._arranged_once = False

        self.visual_window.main_requested.connect(self.main_requested.emit)
        self.visual_window.customize_requested.connect(self.open_customizer)
        self.control_window.pause_requested.connect(self.pause_requested.emit)
        self.control_window.adjust_requested.connect(self.adjust_requested.emit)
        self.control_window.main_requested.connect(self.main_requested.emit)
        self.control_window.finish_requested.connect(self.finish_requested.emit)
        self.control_window.customize_requested.connect(self.open_customizer)

        self.apply_settings(resize_windows=True)

    def apply_settings(self, resize_windows: bool = False) -> None:
        visual_cfg, control_cfg = companion_configs(self.store.settings)
        self.visual_window.apply_config(visual_cfg, resize_window=resize_windows)
        self.control_window.apply_config(control_cfg, resize_window=resize_windows)

        if self.visual_window.isVisible() and not visual_cfg.enabled:
            self.visual_window.hide()
        if self.control_window.isVisible() and (not control_cfg.enabled or not control_cfg.any_content()):
            self.control_window.hide()

    def show(self) -> bool:
        self.apply_settings(resize_windows=True)
        visual_cfg, control_cfg = companion_configs(self.store.settings)
        visual_id = self.session.config.get("visual_id")
        visual_available = bool(self.store.resolve_resource(visual_id)[0])

        shown = False
        if visual_cfg.enabled and visual_available:
            self.visual_window.set_resource(visual_id)
            self.visual_window.show()
            self.visual_window.raise_()
            shown = True

        if control_cfg.enabled and control_cfg.any_content():
            self.control_window.refresh()
            self.control_window.show()
            self.control_window.raise_()
            shown = True

        if shown and not self._arranged_once:
            self._arrange_initially()
            self._arranged_once = True
        return shown

    def _arrange_initially(self) -> None:
        screen = QApplication.primaryScreen()
        if self.visual_window.isVisible():
            screen = self.visual_window.screen() or screen
        elif self.control_window.isVisible():
            screen = self.control_window.screen() or screen
        if not screen:
            return
        area = screen.availableGeometry()

        if self.visual_window.isVisible() and self.control_window.isVisible():
            total_w = self.visual_window.width() + 14 + self.control_window.width()
            x = area.center().x() - total_w // 2
            y = area.center().y() - max(self.visual_window.height(), self.control_window.height()) // 2
            self.visual_window.move(max(area.left(), x), max(area.top(), y))
            self.control_window.move(
                min(area.right() - self.control_window.width(), self.visual_window.x() + self.visual_window.width() + 14),
                self.visual_window.y(),
            )
        elif self.visual_window.isVisible():
            self.visual_window.move(area.center() - self.visual_window.rect().center())
        elif self.control_window.isVisible():
            self.control_window.move(area.center() - self.control_window.rect().center())

    def hide(self) -> None:
        self._capture_geometry()
        self.visual_window.hide()
        self.control_window.hide()

    def refresh(self) -> None:
        self.control_window.refresh()

    def isVisible(self) -> bool:
        return self.visual_window.isVisible() or self.control_window.isVisible()

    def dialog_parent(self) -> QWidget | None:
        if self.control_window.isVisible():
            return self.control_window
        if self.visual_window.isVisible():
            return self.visual_window
        return None

    def open_customizer(self) -> None:
        parent = self.dialog_parent()
        dialog = CompanionSettingsDialog(self.store, self.visual_window, self.control_window, parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.store.update_settings(dialog.values())
        self.apply_settings(resize_windows=True)
        if self.isVisible():
            self.hide()
            self.show()

    def _capture_geometry(self) -> None:
        updates = {}
        if self.visual_window.width() > 0 and self.visual_window.height() > 0:
            updates["visual_companion_width"] = self.visual_window.width()
            updates["visual_companion_height"] = self.visual_window.height()
        if self.control_window.width() > 0:
            updates["control_companion_width"] = self.control_window.width()
        if updates:
            self.store.settings.update(updates)
            self.store.save_state()

    def shutdown(self) -> None:
        self._capture_geometry()
        self.visual_window.shutdown()
        self.control_window.hide()
        self.visual_window.deleteLater()
        self.control_window.deleteLater()
