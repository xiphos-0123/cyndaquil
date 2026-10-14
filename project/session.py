from __future__ import annotations

import ctypes
import os
import time

from PySide6.QtCore import QEvent, QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from .history_filters import normalize_tags
from .utils import new_id, now_iso


class SessionManager(QObject):
    changed = Signal()
    completed = Signal()

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = dict(config)
        self.mode = config.get("mode", "stopwatch")
        self.target_seconds = int(config.get("minutes", 0)) * 60 if self.mode == "timer" else 0
        self.accumulated = 0.0
        self.segment_started: float | None = None
        self.state = "paused"
        self.started_at = now_iso()
        self.distractions: list[str] = []
        self.work_notes: list[str] = []
        self.tags: list[str] = normalize_tags(config.get("tags", []))

        self.tick = QTimer(self)
        self.tick.setInterval(250)
        self.tick.timeout.connect(self._tick)

    def start(self) -> None:
        if self.state == "running" or self.state == "complete":
            return
        self.segment_started = time.monotonic()
        self.state = "running"
        self.tick.start()
        self.changed.emit()

    def pause(self) -> None:
        if self.state != "running":
            return
        self.accumulated = self.elapsed_focus()
        self.segment_started = None
        self.state = "paused"
        self.tick.stop()
        self.changed.emit()

    def toggle_pause(self) -> None:
        if self.state == "running":
            self.pause()
        elif self.state == "paused":
            self.start()

    def elapsed_focus(self) -> float:
        if self.state == "running" and self.segment_started is not None:
            return self.accumulated + (time.monotonic() - self.segment_started)
        return self.accumulated

    def display_seconds(self) -> float:
        if self.mode == "timer":
            return max(0, self.target_seconds - self.elapsed_focus())
        return self.elapsed_focus()

    def adjust_focus(self, seconds: int) -> None:
        current = self.elapsed_focus()
        self.accumulated = max(0.0, current + seconds)
        if self.state == "running":
            self.segment_started = time.monotonic()
        if (
            self.mode == "timer"
            and self.accumulated < self.target_seconds
            and self.state == "complete"
        ):
            self.state = "paused"
        self.changed.emit()

    def add_distraction(self, text: str) -> None:
        text = text.strip()
        if text:
            self.distractions.append(text)
            self.changed.emit()

    def add_work_note(self, text: str) -> None:
        """Keep temporary notes for the final Completion Notes editor.

        Work notes intentionally do not become a separate History field. They
        are only used to prefill the final completion note so the user can
        polish the wording before saving the session.
        """
        text = text.strip()
        if text:
            self.work_notes.append(text)
            self.changed.emit()

    def work_notes_text(self) -> str:
        return "\n\n".join(self.work_notes).strip()

    def finish_payload(self, completion_note: str = "") -> dict:
        self.pause()
        return {
            "id": new_id(),
            "started_at": self.started_at,
            "ended_at": now_iso(),
            "mission": self.config.get("mission", ""),
            "tags": normalize_tags(self.tags),
            "preset_id": self.config.get("preset_id"),
            "preset_name": self.config.get("preset_name", ""),
            "mode": self.mode,
            "target_seconds": self.target_seconds,
            "focused_seconds": int(round(self.elapsed_focus())),
            "distractions": list(self.distractions),
            "completion_note": completion_note.strip(),
            "music_ids": list(self.config.get("music_ids", [])),
            "visual_id": self.config.get("visual_id"),
        }

    def _tick(self) -> None:
        if (
            self.mode == "timer"
            and self.state == "running"
            and self.elapsed_focus() >= self.target_seconds
        ):
            self.accumulated = float(self.target_seconds)
            self.segment_started = None
            self.state = "complete"
            self.tick.stop()
            self.changed.emit()
            self.completed.emit()
            return
        self.changed.emit()


class IdleMonitor(QObject):
    idle_detected = Signal(int)

    def __init__(self, settings_getter, parent=None):
        super().__init__(parent)
        self.settings_getter = settings_getter
        self.timer = QTimer(self)
        self.timer.setInterval(15000)
        self.timer.timeout.connect(self.check)
        self.last_local_activity = time.monotonic()
        self.prompted_for_period = False
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    def start(self) -> None:
        self.prompted_for_period = False
        self.last_local_activity = time.monotonic()
        self.timer.start()

    def stop(self) -> None:
        self.timer.stop()
        self.prompted_for_period = False

    def eventFilter(self, obj, event):
        if event.type() in {
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.KeyPress,
            QEvent.Type.Wheel,
            QEvent.Type.TouchBegin,
        }:
            self.last_local_activity = time.monotonic()
            self.prompted_for_period = False
        return False

    def idle_seconds(self) -> int:
        if os.name == "nt":
            try:

                class LASTINPUTINFO(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

                info = LASTINPUTINFO()
                info.cbSize = ctypes.sizeof(info)
                if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
                    tick = ctypes.windll.kernel32.GetTickCount()
                    return max(0, int((tick - info.dwTime) / 1000))
            except Exception:
                pass
        return max(0, int(time.monotonic() - self.last_local_activity))

    def check(self) -> None:
        settings = self.settings_getter()
        if not settings.get("idle_enabled", True):
            return
        threshold = max(1, int(settings.get("idle_minutes", 8))) * 60
        idle = self.idle_seconds()
        if idle < max(15, threshold // 3):
            self.prompted_for_period = False
        if idle >= threshold and not self.prompted_for_period:
            self.prompted_for_period = True
            self.idle_detected.emit(idle)
