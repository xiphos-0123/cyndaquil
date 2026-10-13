from __future__ import annotations

from copy import deepcopy
import statistics
from datetime import date, datetime, timedelta

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .store import Store
from .utils import (
    current_reporting_day,
    format_seconds,
    parse_iso_datetime,
    reporting_day_bounds,
    reporting_day_key,
)


def _seconds_to_editor(value: int | float | None) -> str:
    seconds = max(0, int(value or 0))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _parse_duration(text: str, field_name: str) -> int:
    raw = text.strip().lower()
    if not raw:
        return 0
    try:
        if raw.endswith("h"):
            return max(0, int(round(float(raw[:-1].strip()) * 3600)))
        if raw.endswith("m"):
            return max(0, int(round(float(raw[:-1].strip()) * 60)))
        if raw.endswith("s"):
            return max(0, int(round(float(raw[:-1].strip()))))
        if ":" not in raw:
            return max(0, int(round(float(raw))))
        parts = raw.split(":")
        if len(parts) == 2:
            minutes, seconds = [int(part.strip()) for part in parts]
            if seconds < 0 or seconds >= 60:
                raise ValueError
            return max(0, minutes * 60 + seconds)
        if len(parts) == 3:
            hours, minutes, seconds = [int(part.strip()) for part in parts]
            if minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60:
                raise ValueError
            return max(0, hours * 3600 + minutes * 60 + seconds)
    except (TypeError, ValueError):
        pass
    raise ValueError(
        f"{field_name} must be HH:MM:SS, MM:SS, seconds, or a value such as 45m / 1.5h."
    )


def _datetime_to_editor(value: str | None) -> str:
    parsed = parse_iso_datetime(value)
    if parsed:
        return parsed.isoformat(sep=" ", timespec="seconds")
    return str(value or "")


def _parse_datetime(text: str, field_name: str) -> str:
    raw = text.strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be a valid date/time, for example 2026-10-09 18:45:00+05:30."
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.isoformat(timespec="seconds")


def _session_span_seconds(session: dict) -> int | None:
    start = parse_iso_datetime(session.get("started_at"))
    end = parse_iso_datetime(session.get("ended_at"))
    if not start or not end:
        return None
    return max(0, int(round((end - start).total_seconds())))


def _session_nonfocus_seconds(session: dict) -> int | None:
    span = _session_span_seconds(session)
    if span is None:
        return None
    return max(0, span - max(0, int(session.get("focused_seconds", 0) or 0)))


def _short_datetime(value: str | None) -> str:
    parsed = parse_iso_datetime(value)
    return parsed.strftime("%Y-%m-%d %H:%M") if parsed else "—"


class DailyProgressChart(QWidget):
    """Focused-hours bars with a rolling seven-day trend line."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values: list[tuple[date, int]] = []
        self.average = 0.0
        self.rolling: list[float] = []
        self.setMinimumHeight(250)

    def set_data(self, values: list[tuple[date, int]]) -> None:
        self.values = list(values)
        self.average = (
            sum(seconds for _, seconds in self.values) / len(self.values)
            if self.values else 0.0
        )
        self.rolling = []
        raw = [seconds for _, seconds in self.values]
        for index in range(len(raw)):
            start = max(0, index - 6)
            window = raw[start:index + 1]
            self.rolling.append(sum(window) / len(window))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(48, 18, -18, -36)
        if rect.width() <= 10 or rect.height() <= 10:
            return

        painter.setPen(QColor("#60788A"))
        if not self.values:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No session data yet")
            return

        max_seconds = max(
            max(v for _, v in self.values),
            max(self.rolling, default=0),
            3600,
        )
        max_hours = max(1, int((max_seconds + 3599) // 3600))
        max_seconds = max_hours * 3600

        for i in range(5):
            y = rect.bottom() - rect.height() * i / 4
            painter.setPen(QPen(QColor("#274052"), 1))
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))
            hours = max_hours * i / 4
            painter.setPen(QColor("#8EA4B3"))
            painter.drawText(2, int(y) - 8, 42, 16, Qt.AlignmentFlag.AlignRight, f"{hours:g}h")

        count = len(self.values)
        slot = rect.width() / max(1, count)
        bar_width = max(3.0, min(32.0, slot * 0.58))

        for index, (day, seconds) in enumerate(self.values):
            ratio = seconds / max_seconds if max_seconds else 0
            height = rect.height() * ratio
            x = rect.left() + slot * index + (slot - bar_width) / 2
            y = rect.bottom() - height
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#E66C35") if seconds else QColor("#294A60"))
            painter.drawRoundedRect(QRectF(x, y, bar_width, max(2, height)), 3, 3)

            label_every = 1 if count <= 14 else 3 if count <= 35 else 7
            if index % label_every == 0 or index == count - 1:
                painter.setPen(QColor("#8EA4B3"))
                painter.drawText(
                    int(x - slot * 0.25), rect.bottom() + 7,
                    int(bar_width + slot * 0.5), 20,
                    Qt.AlignmentFlag.AlignHCenter,
                    day.strftime("%d %b"),
                )

        # Selected-window average.
        if self.average > 0:
            avg_y = rect.bottom() - rect.height() * (self.average / max_seconds)
            painter.setPen(QPen(QColor("#FFD16A"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(rect.left(), int(avg_y), rect.right(), int(avg_y))

        # Rolling 7-day average. For the first six points, this uses all
        # available days so the progression starts immediately.
        if self.rolling:
            painter.setPen(QPen(QColor("#F7E9C8"), 2))
            previous = None
            for index, seconds in enumerate(self.rolling):
                x = rect.left() + slot * index + slot / 2
                y = rect.bottom() - rect.height() * (seconds / max_seconds)
                point = (int(x), int(y))
                if previous is not None:
                    painter.drawLine(previous[0], previous[1], point[0], point[1])
                previous = point

        painter.setPen(QColor("#FFD16A"))
        painter.drawText(rect.right() - 150, rect.top(), 150, 18, Qt.AlignmentFlag.AlignRight, "— window average")
        painter.setPen(QColor("#F7E9C8"))
        painter.drawText(rect.right() - 150, rect.top() + 18, 150, 18, Qt.AlignmentFlag.AlignRight, "— rolling 7-day average")


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

        updated = dict(self.original)
        updated.pop("break_seconds", None)
        updated.update({
            "mission": self.mission.text().strip(),
            "preset_name": self.preset_name.text().strip(),
            "preset_id": self.preset_ref.currentData(),
            "mode": self.mode.currentData(),
            "started_at": started_at,
            "ended_at": ended_at,
            "target_seconds": target_seconds,
            "focused_seconds": focused_seconds,
            "completion_note": self.completion_note.toPlainText().strip(),
            "distractions": [line.strip() for line in self.distractions.toPlainText().splitlines() if line.strip()],
            "music_ids": self._selected_audio_ids(),
            "visual_id": self.visual.currentData(),
        })
        self.store.update_session(self.original.get("id"), updated)
        self.accept()


class HistoryPage(QWidget):
    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("History & Productivity")
        title.setObjectName("Title")
        subtitle = QLabel(
            "Time-based productivity analysis using a configurable reporting-day boundary. "
            "Changing the boundary only changes grouping; it never rewrites the original session timestamps."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        reporting_controls = QFrame()
        reporting_controls.setObjectName("Card")
        reporting_form = QFormLayout(reporting_controls)
        reporting_form.setContentsMargins(12, 10, 12, 10)
        self.day_start = QComboBox()
        for hour in range(24):
            self.day_start.addItem(f"{hour:02d}:00", hour)
        self.chart_days = QComboBox()
        for days in (7, 14, 30, 60, 90):
            self.chart_days.addItem(f"{days} Days", days)
        reporting_form.addRow("Reporting Day Starts", self.day_start)
        reporting_form.addRow("Progression Window", self.chart_days)
        header.addWidget(reporting_controls)
        root.addLayout(header)

        stats = QGridLayout()
        stats.setHorizontalSpacing(10)
        stats.setVerticalSpacing(10)
        self.current_day = self._card("Current Reporting Day")
        self.last7 = self._card("Last 7 Reporting Days")
        self.last30 = self._card("Last 30 Reporting Days")
        self.last90 = self._card("Last 90 Reporting Days")
        self.trend7 = self._card("7-Day Trend")
        self.trend30 = self._card("30-Day Trend")
        self.daily_average = self._card("All-History Daily Average")
        self.total = self._card("All-Time Focused")
        cards = (
            self.current_day, self.last7, self.last30, self.last90,
            self.trend7, self.trend30, self.daily_average, self.total,
        )
        for index, card in enumerate(cards):
            stats.addWidget(card[0], index // 4, index % 4)
        root.addLayout(stats)

        overview = QHBoxLayout()
        overview.setSpacing(12)

        chart_card = QFrame()
        chart_card.setObjectName("Card")
        chart_layout = QVBoxLayout(chart_card)
        chart_title = QLabel("Focused-Time Progression")
        chart_title.setObjectName("SectionTitle")
        self.chart_subtitle = QLabel("")
        self.chart_subtitle.setObjectName("Muted")
        self.chart_subtitle.setWordWrap(True)
        self.chart = DailyProgressChart()
        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(self.chart_subtitle)
        chart_layout.addWidget(self.chart, 1)

        analysis_card = QFrame()
        analysis_card.setObjectName("Card")
        analysis_card.setMinimumWidth(350)
        analysis_layout = QVBoxLayout(analysis_card)
        analysis_title = QLabel("Time Analysis")
        analysis_title.setObjectName("SectionTitle")
        analysis_layout.addWidget(analysis_title)

        self.average_session = self._analysis_metric("Average Focused Session")
        self.median_session = self._analysis_metric("Median Focused Session")
        self.longest_session = self._analysis_metric("Longest Focused Session")
        self.average_span = self._analysis_metric("Average Session Span")
        self.focus_efficiency = self._analysis_metric("Focus Efficiency")
        self.nonfocus_summary = self._analysis_metric("Average Non-Focus Time")
        self.best_day = self._analysis_metric("Best Reporting Day")
        self.best7 = self._analysis_metric("Best 7-Day Window")
        self.best30 = self._analysis_metric("Best 30-Day Window")

        for metric in (
            self.average_session, self.median_session, self.longest_session,
            self.average_span, self.focus_efficiency, self.nonfocus_summary,
            self.best_day, self.best7, self.best30,
        ):
            analysis_layout.addWidget(metric)
        analysis_layout.addStretch()

        overview.addWidget(chart_card, 3)
        overview.addWidget(analysis_card, 2)
        root.addLayout(overview, 2)

        buttons = QHBoxLayout()
        self.open_entry = QPushButton("Open Session Entry…")
        self.open_entry.setObjectName("Primary")
        self.delete = QPushButton("Delete Session")
        self.delete.setObjectName("Danger")
        buttons.addWidget(self.open_entry)
        buttons.addStretch()
        buttons.addWidget(self.delete)
        root.addLayout(buttons)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Started",
            "Finished",
            "Session Objective",
            "Mode",
            "Session Span",
            "Focused",
            "Non-Focus",
            "Preset",
            "Completion Note",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 3)

        self.open_entry.clicked.connect(self.open_selected_entry)
        self.delete.clicked.connect(self.delete_entry)
        self.table.cellDoubleClicked.connect(lambda row, column: self.open_selected_entry())
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.day_start.currentIndexChanged.connect(self._reporting_options_changed)
        self.chart_days.currentIndexChanged.connect(self._reporting_options_changed)
        self.store.sessions_changed.connect(self.refresh)
        self.store.settings_changed.connect(self._load_reporting_settings)
        self._load_reporting_settings()
        self.refresh()

    def _card(self, label):
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(13, 11, 13, 11)
        cap = QLabel(label)
        cap.setObjectName("Muted")
        value = QLabel("00:00:00")
        value.setStyleSheet("font-size: 20px; font-weight: 800; color: #FFD16A;")
        detail = QLabel("")
        detail.setObjectName("Muted")
        detail.setWordWrap(True)
        layout.addWidget(cap)
        layout.addWidget(value)
        layout.addWidget(detail)
        return frame, value, detail

    def _analysis_metric(self, label: str) -> QLabel:
        metric = QLabel(f"{label}\n—")
        metric.setWordWrap(True)
        metric.setObjectName("Muted")
        metric.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return metric

    def _load_reporting_settings(self) -> None:
        hour = int(self.store.settings.get("history_day_start_hour", 0))
        days = int(self.store.settings.get("history_chart_days", 14))
        self.day_start.blockSignals(True)
        self.chart_days.blockSignals(True)
        day_index = self.day_start.findData(hour)
        self.day_start.setCurrentIndex(day_index if day_index >= 0 else 0)
        chart_index = self.chart_days.findData(days)
        self.chart_days.setCurrentIndex(chart_index if chart_index >= 0 else self.chart_days.findData(14))
        self.day_start.blockSignals(False)
        self.chart_days.blockSignals(False)

    def _reporting_options_changed(self, *args) -> None:
        self.store.update_settings({
            "history_day_start_hour": int(self.day_start.currentData() or 0),
            "history_chart_days": int(self.chart_days.currentData() or 14),
        })
        self.refresh()

    def refresh(self) -> None:
        selected = self.selected_id()
        self.table.setRowCount(0)
        selected_row = -1

        for session in reversed(self.store.sessions):
            row = self.table.rowCount()
            self.table.insertRow(row)
            note = session.get("completion_note", "") or ""
            note_preview = " ".join(note.split())
            if len(note_preview) > 100:
                note_preview = note_preview[:97] + "…"
            span = _session_span_seconds(session)
            nonfocus = _session_nonfocus_seconds(session)
            values = [
                _short_datetime(session.get("started_at")),
                _short_datetime(session.get("ended_at")),
                session.get("mission", ""),
                str(session.get("mode", "")).title(),
                format_seconds(span) if span is not None else "—",
                format_seconds(session.get("focused_seconds", 0)),
                format_seconds(nonfocus) if nonfocus is not None else "—",
                session.get("preset_name", ""),
                note_preview,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, session.get("id"))
                if col == 6:
                    item.setToolTip("Derived automatically: Session Span minus Focused Time")
                if col == 8:
                    item.setToolTip(note)
                self.table.setItem(row, col, item)
            if session.get("id") == selected:
                selected_row = row

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        self._refresh_stats()
        self._update_actions()

    def _daily_totals(self, start_hour: int) -> dict[date, int]:
        totals: dict[date, int] = {}
        for session in self.store.sessions:
            started = parse_iso_datetime(session.get("started_at"))
            if not started:
                continue
            key = reporting_day_key(started, start_hour)
            totals[key] = totals.get(key, 0) + max(0, int(session.get("focused_seconds", 0) or 0))
        return totals

    @staticmethod
    def _window_days(end_day: date, days: int) -> list[date]:
        return [end_day - timedelta(days=i) for i in range(days - 1, -1, -1)]

    def _window_total(self, totals: dict[date, int], end_day: date, days: int) -> int:
        return sum(totals.get(day, 0) for day in self._window_days(end_day, days))

    def _trend(self, totals: dict[date, int], end_day: date, days: int) -> tuple[int, int, float | None]:
        current = self._window_total(totals, end_day, days)
        previous_end = end_day - timedelta(days=days)
        previous = self._window_total(totals, previous_end, days)
        if previous > 0:
            return current, previous, ((current - previous) / previous) * 100
        return current, previous, None

    def _best_window(self, totals: dict[date, int], current_day: date, days: int) -> tuple[date | None, date | None, int]:
        if not totals:
            return None, None, 0
        first = min(totals)
        if first > current_day:
            return None, None, 0
        best_total = -1
        best_start = first
        best_end = first
        end = first
        while end <= current_day:
            total = self._window_total(totals, end, days)
            if total > best_total:
                best_total = total
                best_end = end
                best_start = end - timedelta(days=days - 1)
            end += timedelta(days=1)
        return best_start, best_end, max(0, best_total)

    def _refresh_stats(self) -> None:
        now = datetime.now().astimezone()
        start_hour = int(self.store.settings.get("history_day_start_hour", 0))
        chart_days = int(self.store.settings.get("history_chart_days", 14))
        current_day = current_reporting_day(start_hour, now)
        totals = self._daily_totals(start_hour)

        # Current reporting day.
        current_seconds = totals.get(current_day, 0)
        start, end = reporting_day_bounds(current_day, start_hour, now.tzinfo)
        self.current_day[1].setText(format_seconds(current_seconds))
        self.current_day[2].setText(
            f"{start.strftime('%d %b %H:%M')} → {end.strftime('%d %b %H:%M')}"
        )

        # Rolling reporting-day totals.
        last7 = self._window_total(totals, current_day, 7)
        last30 = self._window_total(totals, current_day, 30)
        last90 = self._window_total(totals, current_day, 90)
        self.last7[1].setText(format_seconds(last7))
        self.last7[2].setText(f"Daily average {format_seconds(last7 / 7)}")
        self.last30[1].setText(format_seconds(last30))
        self.last30[2].setText(f"Daily average {format_seconds(last30 / 30)}")
        self.last90[1].setText(format_seconds(last90))
        self.last90[2].setText(f"Daily average {format_seconds(last90 / 90)}")

        # Window-over-window trends.
        current7, previous7, change7 = self._trend(totals, current_day, 7)
        current30, previous30, change30 = self._trend(totals, current_day, 30)
        if change7 is not None:
            self.trend7[1].setText(f"{change7:+.1f}%")
            self.trend7[2].setText(f"Previous 7 days {format_seconds(previous7)}")
        elif current7 > 0:
            self.trend7[1].setText("New Baseline")
            self.trend7[2].setText("Previous 7 days contained no focused time")
        else:
            self.trend7[1].setText("—")
            self.trend7[2].setText("No comparison data yet")

        if change30 is not None:
            self.trend30[1].setText(f"{change30:+.1f}%")
            self.trend30[2].setText(f"Previous 30 days {format_seconds(previous30)}")
        elif current30 > 0:
            self.trend30[1].setText("New Baseline")
            self.trend30[2].setText("Previous 30 days contained no focused time")
        else:
            self.trend30[1].setText("—")
            self.trend30[2].setText("No comparison data yet")

        total_seconds = sum(max(0, int(s.get("focused_seconds", 0) or 0)) for s in self.store.sessions)
        self.total[1].setText(format_seconds(total_seconds))
        if totals:
            first_day = min(totals)
            history_days = max(1, (current_day - first_day).days + 1)
            average_day = total_seconds / history_days
            self.daily_average[1].setText(format_seconds(average_day))
            self.daily_average[2].setText(f"Across {history_days} reporting days since {first_day.strftime('%d %b %Y')}")
            self.total[2].setText(f"Recorded since {first_day.strftime('%d %b %Y')}")
        else:
            self.daily_average[1].setText("00:00:00")
            self.daily_average[2].setText("No reporting-day history yet")
            self.total[2].setText("No focused time recorded yet")

        # Progression chart.
        days = self._window_days(current_day, chart_days)
        chart_values = [(day, totals.get(day, 0)) for day in days]
        self.chart.set_data(chart_values)
        self.chart_subtitle.setText(
            f"{chart_days}-day view · Reporting boundary {start_hour:02d}:00 · "
            "orange bars = focused time · cream line = rolling 7-day daily average · yellow dashed line = selected-window average"
        )

        # Session-duration analysis.
        focused_values = [
            max(0, int(s.get("focused_seconds", 0) or 0))
            for s in self.store.sessions
            if int(s.get("focused_seconds", 0) or 0) > 0
        ]
        if focused_values:
            avg_focus = sum(focused_values) / len(focused_values)
            median_focus = statistics.median(focused_values)
            longest = max(self.store.sessions, key=lambda s: int(s.get("focused_seconds", 0) or 0))
            self.average_session.setText(f"Average Focused Session\n{format_seconds(avg_focus)}")
            self.median_session.setText(f"Median Focused Session\n{format_seconds(median_focus)}")
            self.longest_session.setText(
                f"Longest Focused Session\n{format_seconds(longest.get('focused_seconds', 0))}"
            )
        else:
            self.average_session.setText("Average Focused Session\n—")
            self.median_session.setText("Median Focused Session\n—")
            self.longest_session.setText("Longest Focused Session\n—")

        spans: list[int] = []
        nonfocus_values: list[int] = []
        efficiency_focus = 0
        efficiency_span = 0
        for session in self.store.sessions:
            span = _session_span_seconds(session)
            if span is None or span <= 0:
                continue
            focus = max(0, int(session.get("focused_seconds", 0) or 0))
            spans.append(span)
            nonfocus_values.append(max(0, span - focus))
            efficiency_focus += min(focus, span)
            efficiency_span += span

        if spans:
            self.average_span.setText(f"Average Session Span\n{format_seconds(sum(spans) / len(spans))}")
            efficiency = (efficiency_focus / efficiency_span * 100) if efficiency_span else 0.0
            self.focus_efficiency.setText(f"Focus Efficiency\n{efficiency:.1f}% of recorded session span")
            self.nonfocus_summary.setText(
                f"Average Non-Focus Time\n{format_seconds(sum(nonfocus_values) / len(nonfocus_values))}"
            )
        else:
            self.average_span.setText("Average Session Span\nAdd Finish times to calculate")
            self.focus_efficiency.setText("Focus Efficiency\nAdd Finish times to calculate")
            self.nonfocus_summary.setText("Average Non-Focus Time\nAdd Finish times to calculate")

        if totals:
            best_day, best_seconds = max(totals.items(), key=lambda item: item[1])
            self.best_day.setText(
                f"Best Reporting Day\n{format_seconds(best_seconds)} · {best_day.strftime('%d %b %Y')}"
            )
            best7_start, best7_end, best7_seconds = self._best_window(totals, current_day, 7)
            best30_start, best30_end, best30_seconds = self._best_window(totals, current_day, 30)
            self.best7.setText(
                f"Best 7-Day Window\n{format_seconds(best7_seconds)} · "
                f"{best7_start.strftime('%d %b') if best7_start else '—'} → {best7_end.strftime('%d %b') if best7_end else '—'}"
            )
            self.best30.setText(
                f"Best 30-Day Window\n{format_seconds(best30_seconds)} · "
                f"{best30_start.strftime('%d %b') if best30_start else '—'} → {best30_end.strftime('%d %b') if best30_end else '—'}"
            )
        else:
            self.best_day.setText("Best Reporting Day\n—")
            self.best7.setText("Best 7-Day Window\n—")
            self.best30.setText("Best 30-Day Window\n—")

    def selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def selected_session(self):
        return self.store.session_by_id(self.selected_id())

    def _update_actions(self) -> None:
        selected = self.selected_id() is not None
        self.open_entry.setEnabled(selected)
        self.delete.setEnabled(selected)

    def open_selected_entry(self) -> None:
        session = self.selected_session()
        if session:
            SessionEntryDialog(self.store, session, self).exec()

    def delete_entry(self) -> None:
        sid = self.selected_id()
        if sid and QMessageBox.question(
            self,
            "Delete Session",
            "Delete the selected session permanently?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.store.delete_session(sid)

