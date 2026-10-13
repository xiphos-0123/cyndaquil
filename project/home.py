from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget
)

from .media import MediaVisual
from .session import SessionManager
from .store import Store
from .utils import current_reporting_day, format_seconds, parse_iso_datetime, reporting_day_bounds, reporting_day_key


class HomePage(QWidget):
    start_requested = Signal(dict)
    pause_requested = Signal()
    adjust_requested = Signal(int)
    companion_requested = Signal()
    finish_requested = Signal()
    distraction_requested = Signal()
    work_note_requested = Signal()
    audio_toggle_requested = Signal()
    audio_next_requested = Signal()
    audio_previous_requested = Signal()
    audio_volume_changed = Signal(int)

    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self.session: SessionManager | None = None
        self._has_music = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Focus Session")
        title.setObjectName("Title")
        subtitle = QLabel("Set the objective, choose the environment, and begin.")
        subtitle.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        root.addLayout(header)

        # ---------- idle/start dashboard ----------
        self.start_dashboard = QWidget()
        dash = QHBoxLayout(self.start_dashboard)
        dash.setContentsMargins(0, 0, 0, 0)
        dash.setSpacing(18)

        self.start_card = QFrame()
        self.start_card.setObjectName("EmberCard")
        start_layout = QVBoxLayout(self.start_card)
        start_layout.setContentsMargins(22, 22, 22, 22)
        start_layout.setSpacing(14)

        cap = QLabel("Session Setup")
        cap.setObjectName("SectionTitle")
        intro = QLabel("Define one clear objective. Cyndaquil will keep the timer, ambience, and session controls together.")
        intro.setWordWrap(True)
        intro.setObjectName("Muted")

        mission_label = QLabel("Session Objective")
        mission_label.setStyleSheet("font-weight: 700;")
        self.mission = QLineEdit()
        self.mission.setPlaceholderText("Optional — e.g. Draft the chapter outline")

        preset_label = QLabel("Focus Preset")
        preset_label.setStyleSheet("font-weight: 700;")
        self.preset = QComboBox()

        self.mode = QComboBox()
        self.mode.addItem("Stopwatch", "stopwatch")
        self.mode.addItem("Timer", "timer")

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Session Mode"))
        mode_row.addWidget(self.mode, 1)

        self.minutes_row = QWidget()
        minutes_layout = QHBoxLayout(self.minutes_row)
        minutes_layout.setContentsMargins(0, 0, 0, 0)
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 720)
        self.minutes.setSuffix(" min")
        minutes_layout.addWidget(QLabel("Timer Duration"))
        minutes_layout.addWidget(self.minutes, 1)

        self.media_summary = QLabel("")
        self.media_summary.setWordWrap(True)
        self.media_summary.setObjectName("Muted")

        self.start_btn = QPushButton("Begin Focus Session")
        self.start_btn.setObjectName("Primary")
        self.start_btn.setMinimumHeight(44)

        start_layout.addWidget(cap)
        start_layout.addWidget(intro)
        start_layout.addSpacing(6)
        start_layout.addWidget(mission_label)
        start_layout.addWidget(self.mission)
        start_layout.addWidget(preset_label)
        start_layout.addWidget(self.preset)
        start_layout.addLayout(mode_row)
        start_layout.addWidget(self.minutes_row)
        start_layout.addStretch()
        start_layout.addWidget(self.media_summary)
        start_layout.addWidget(self.start_btn)

        # Right-hand dashboard uses the extra space on a maximized window.
        right = QVBoxLayout()
        right.setSpacing(18)

        preset_card = QFrame()
        preset_card.setObjectName("Card")
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setContentsMargins(16, 16, 16, 16)
        preset_title = QLabel("Selected Preset")
        preset_title.setObjectName("SectionTitle")
        self.preview_visual = MediaVisual(store)
        self.preview_visual.setMinimumHeight(230)
        self.preview_name = QLabel("Default")
        self.preview_name.setStyleSheet("font-size: 18px; font-weight: 800; color: #FFD16A;")
        self.preview_details = QLabel("")
        self.preview_details.setWordWrap(True)
        self.preview_details.setObjectName("Muted")
        preset_layout.addWidget(preset_title)
        preset_layout.addWidget(self.preview_visual, 1)
        preset_layout.addWidget(self.preview_name)
        preset_layout.addWidget(self.preview_details)

        today_card = QFrame()
        today_card.setObjectName("Card")
        today_layout = QGridLayout(today_card)
        today_title = QLabel("Current Reporting Day")
        today_title.setObjectName("SectionTitle")
        self.today_time = QLabel("00:00:00")
        self.today_time.setStyleSheet("font-size: 24px; font-weight: 900; color: #FFD16A;")
        self.today_sessions = QLabel("0 completed sessions")
        self.today_sessions.setObjectName("Muted")
        today_layout.addWidget(today_title, 0, 0, 1, 2)
        today_layout.addWidget(self.today_time, 1, 0)
        today_layout.addWidget(self.today_sessions, 2, 0)

        shortcut_card = QFrame()
        shortcut_card.setObjectName("Card")
        shortcut_layout = QVBoxLayout(shortcut_card)
        shortcut_title = QLabel("Session Shortcuts")
        shortcut_title.setObjectName("SectionTitle")
        shortcut_text = QLabel(
            "Space — Pause / Resume\n"
            "Ctrl + N — Work Note\n"
            "Ctrl + D — Distraction Dump\n"
        )
        shortcut_text.setObjectName("Muted")
        shortcut_layout.addWidget(shortcut_title)
        shortcut_layout.addWidget(shortcut_text)

        right.addWidget(preset_card, 1)
        right.addWidget(today_card)
        right.addWidget(shortcut_card)

        dash.addWidget(self.start_card, 3)
        dash.addLayout(right, 2)

        # ---------- active session ----------
        self.active_card = QFrame()
        self.active_card.setObjectName("EmberCard")
        active = QVBoxLayout(self.active_card)
        active.setContentsMargins(22, 18, 22, 18)
        active.setSpacing(10)

        self.active_mission = QLabel("")
        self.active_mission.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.active_mission.setWordWrap(True)
        self.active_mission.setStyleSheet("font-size: 24px; font-weight: 800; color: #FFE2A8;")

        self.visual = MediaVisual(store)
        self.visual.setMinimumHeight(240)

        self.clock = QLabel("00:00:00")
        self.clock.setObjectName("Clock")
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setObjectName("Muted")

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1000)

        self.music_panel = QFrame()
        self.music_panel.setObjectName("Card")
        music_layout = QHBoxLayout(self.music_panel)
        self.track = QLabel("")
        self.track.setMinimumWidth(160)
        prev_btn = QPushButton("Previous")
        play_btn = QPushButton("Play / Pause")
        next_btn = QPushButton("Next")
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(store.settings.get("audio_volume", 55)))
        music_layout.addWidget(prev_btn)
        music_layout.addWidget(play_btn)
        music_layout.addWidget(next_btn)
        music_layout.addWidget(self.track, 1)
        music_layout.addWidget(QLabel("Volume"))
        music_layout.addWidget(self.volume, 1)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setObjectName("Primary")
        self.minus_btn = QPushButton("−1 Minute")
        self.plus_btn = QPushButton("+1 Minute")
        self.dump_btn = QPushButton("Distraction Dump")
        self.note_btn = QPushButton("Work Note")
        self.companion_btn = QPushButton("Open Floating Companions")
        self.companion_btn.setObjectName("Warm")
        self.finish_btn = QPushButton("Finish Session")
        self.finish_btn.setObjectName("Danger")
        for button in (
            self.pause_btn, self.minus_btn, self.plus_btn,
            self.note_btn, self.dump_btn, self.companion_btn, self.finish_btn
        ):
            controls.addWidget(button)

        active.addWidget(self.active_mission)
        active.addWidget(self.visual, 1)
        active.addWidget(self.clock)
        active.addWidget(self.status)
        active.addWidget(self.progress)
        active.addWidget(self.music_panel)
        active.addLayout(controls)

        root.addWidget(self.start_dashboard, 1)
        root.addWidget(self.active_card, 1)
        self.active_card.hide()

        # ---------- connections ----------
        self.preset.currentIndexChanged.connect(self.apply_selected_preset)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.start_btn.clicked.connect(self._request_start)
        self.pause_btn.clicked.connect(self.pause_requested)
        self.minus_btn.clicked.connect(lambda: self.adjust_requested.emit(-60))
        self.plus_btn.clicked.connect(lambda: self.adjust_requested.emit(60))
        self.dump_btn.clicked.connect(self.distraction_requested)
        self.note_btn.clicked.connect(self.work_note_requested)
        self.companion_btn.clicked.connect(self.companion_requested)
        self.finish_btn.clicked.connect(self.finish_requested)
        prev_btn.clicked.connect(self.audio_previous_requested)
        play_btn.clicked.connect(self.audio_toggle_requested)
        next_btn.clicked.connect(self.audio_next_requested)
        self.volume.valueChanged.connect(self.audio_volume_changed)

        store.presets_changed.connect(self.refresh_presets)
        store.resources_changed.connect(self.apply_selected_preset)
        store.sessions_changed.connect(self.refresh_today)
        store.settings_changed.connect(self.refresh_today)
        store.defaults_changed.connect(self.apply_selected_preset)

        self.refresh_presets()
        self.refresh_today()

    def refresh_presets(self) -> None:
        current = self.preset.currentData()
        self.preset.blockSignals(True)
        self.preset.clear()
        for preset in self.store.presets:
            self.preset.addItem(preset.get("name", "Preset"), preset.get("id"))
        self.preset.blockSignals(False)

        index = self.preset.findData(current)
        self.preset.setCurrentIndex(index if index >= 0 else 0)
        self.apply_selected_preset()

    def selected_preset(self):
        return self.store.preset_by_id(self.preset.currentData())

    def apply_selected_preset(self) -> None:
        if self.session is not None:
            return
        preset = self.selected_preset()
        if not preset:
            return

        mode = preset.get("mode", "stopwatch")
        mode_index = self.mode.findData(mode)
        self.mode.setCurrentIndex(mode_index if mode_index >= 0 else 0)
        self.minutes.setValue(max(1, int(preset.get("minutes", 50))))

        audio_names = []
        for rid in preset.get("music_ids", []):
            path, _ = self.store.resolve_resource(rid)
            item = self.store.resource_by_id(rid)
            if path and item:
                audio_names.append(item.get("name", path.stem))

        visual_id = preset.get("visual_id")
        visual_path, _ = self.store.resolve_resource(visual_id)
        self.preview_visual.set_resource(visual_id if visual_path else None)

        self.preview_name.setText(preset.get("name", "Preset"))
        mode_text = "Stopwatch" if mode == "stopwatch" else f"Timer · {preset.get('minutes', 50)} minutes"
        ambience = ", ".join(audio_names[:3]) if audio_names else "No audio"
        if len(audio_names) > 3:
            ambience += f" + {len(audio_names) - 3} more"

        visual_text = "Visual available" if visual_path else "No visual"
        self.preview_details.setText(f"{mode_text}\n{ambience}\n{visual_text}")

        summary = []
        if audio_names:
            summary.append(f"{len(audio_names)} audio track{'s' if len(audio_names) != 1 else ''}")
        if visual_path:
            summary.append("1 visual")
        self.media_summary.setText(
            "Ambience: " + (" · ".join(summary) if summary else "None")
        )
        self._mode_changed()

    def _mode_changed(self) -> None:
        self.minutes_row.setVisible(self.mode.currentData() == "timer")

    def _request_start(self) -> None:
        preset = self.selected_preset() or {}
        mode = self.mode.currentData() or "stopwatch"
        self.start_requested.emit({
            "mission": self.mission.text().strip(),
            "preset_id": preset.get("id"),
            "preset_name": preset.get("name", ""),
            "mode": mode,
            "minutes": self.minutes.value() if mode == "timer" else 0,
            "music_ids": list(preset.get("music_ids", [])),
            "visual_id": preset.get("visual_id"),
        })

    def refresh_today(self) -> None:
        now = datetime.now().astimezone()
        start_hour = int(self.store.settings.get("history_day_start_hour", 0))
        day = current_reporting_day(start_hour, now)
        window_start, window_end = reporting_day_bounds(day, start_hour, now.tzinfo)
        seconds = 0
        count = 0
        for session in self.store.sessions:
            started = parse_iso_datetime(session.get("started_at"))
            if not started:
                continue
            if reporting_day_key(started, start_hour) == day:
                seconds += int(session.get("focused_seconds", 0) or 0)
                count += 1

        self.today_time.setText(format_seconds(seconds))
        self.today_sessions.setText(
            f"{count} completed session{'s' if count != 1 else ''} · "
            f"{window_start.strftime('%b %d %H:%M')} → {window_end.strftime('%b %d %H:%M')}"
        )

    def set_active(self, config: dict, session: SessionManager, has_music: bool, track_name: str = "") -> None:
        self.session = session
        self.start_dashboard.hide()
        self.active_card.show()

        mission = config.get("mission", "")
        self.active_mission.setText(mission)
        self.active_mission.setVisible(bool(mission.strip()))

        self.visual.set_resource(config.get("visual_id"))
        self._has_music = bool(has_music)
        self.music_panel.setVisible(self._has_music)
        self.track.setText(track_name)
        self.volume.setValue(int(self.store.settings.get("audio_volume", 55)))

        self.refresh_active()

    def clear_active(self) -> None:
        self.visual.stop()
        self.visual.hide()
        self.session = None
        self._has_music = False
        self.active_card.hide()
        self.start_dashboard.show()
        self.mission.clear()
        self.apply_selected_preset()
        self.refresh_today()

    def set_track(self, name: str) -> None:
        self.track.setText(name)

    def set_ritual(self, seconds: int) -> None:
        self.status.setText(f"Starting in {seconds}")

    def refresh_active(self) -> None:
        if not self.session:
            return

        self.clock.setText(format_seconds(self.session.display_seconds()))
        labels = {
            "running": "FOCUSING",
            "paused": "PAUSED",
            "complete": "SESSION COMPLETE",
        }
        state = self.session.state
        self.status.setText(labels.get(state, state.upper()))
        self.pause_btn.setText("Pause" if state == "running" else "Resume")
        self.pause_btn.setEnabled(state != "complete")
        note_count = len(getattr(self.session, "work_notes", []))
        self.note_btn.setText(f"Work Notes ({note_count})" if note_count else "Work Note")

        if self.session.mode == "timer" and self.session.target_seconds > 0:
            elapsed = min(self.session.elapsed_focus(), self.session.target_seconds)
            self.progress.setValue(int(elapsed / self.session.target_seconds * 1000))
            self.progress.show()
        else:
            self.progress.hide()
