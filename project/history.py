"""Session browsing, read-only filters, and productivity statistics."""
from __future__ import annotations
import statistics
from datetime import date, datetime, timedelta
from PySide6.QtCore import QDate, QItemSelectionModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDialog, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)
from .store import Store
from .history_filters import filter_sessions, normalize_tags
from .tag_editor import BulkTagDialog, TagEditor, available_tags
from .persistence import PersistenceError
from .history_chart import DailyProgressChart
from .session_entry import SessionEntryDialog
from .history_records import _session_span_seconds, _session_nonfocus_seconds, _short_datetime
from .utils import current_reporting_day, format_seconds, parse_iso_datetime, reporting_day_bounds, reporting_day_key


class HistoryPage(QWidget):
    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel("History & Productivity")
        title.setObjectName("Title")
        root.addWidget(title)
        tag_controls = QHBoxLayout()
        tag_controls.addWidget(QLabel("Tags"))
        self.tag_filter = TagEditor(available=available_tags(store.sessions))
        self.tag_mode = QComboBox()
        self.tag_mode.addItem("Include any", "include")
        self.tag_mode.addItem("Exclude any", "exclude")
        tag_controls.addWidget(self.tag_mode)
        tag_controls.addWidget(self.tag_filter, 1)
        root.addLayout(tag_controls)
        tag_hint = QLabel("Leave tags empty to show everything. Tag filters apply to both views; dates below filter Session History.")
        tag_hint.setObjectName("Muted")
        tag_hint.setWordWrap(True)
        root.addWidget(tag_hint)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        history_view = QWidget()
        history_layout = QVBoxLayout(history_view)
        stats_scroll = QScrollArea()
        stats_scroll.setWidgetResizable(True)
        stats_scroll.setFrameShape(QFrame.Shape.NoFrame)
        stats_view = QWidget()
        stats_scroll.setWidget(stats_view)
        stats_layout = QVBoxLayout(stats_view)
        self.tabs.addTab(history_view, "Session History")
        self.tabs.addTab(stats_scroll, "Statistics")

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Statistics")
        title.setObjectName("SectionTitle")
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
        stats_layout.addLayout(header)

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
        stats_layout.addLayout(stats)

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
        stats_layout.addLayout(overview, 2)

        dates = QHBoxLayout()
        dates.addWidget(QLabel("Show"))
        self.period = QComboBox()
        for label, days in (("All time", 0), ("Today", 1), ("Last 7 days", 7),
                            ("Last 30 days", 30), ("Last 90 days", 90), ("Custom dates", -1)):
            self.period.addItem(label, days)
        dates.addWidget(self.period)
        self.from_date = QDateEdit(QDate.currentDate().addDays(-6))
        self.to_date = QDateEdit(QDate.currentDate())
        for editor in (self.from_date, self.to_date):
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd MMM yyyy")
        self.date_range_controls = QWidget()
        date_range = QHBoxLayout(self.date_range_controls)
        date_range.setContentsMargins(0, 0, 0, 0)
        date_range.addWidget(QLabel("From"))
        date_range.addWidget(self.from_date)
        date_range.addWidget(QLabel("Through"))
        date_range.addWidget(self.to_date)
        date_range.addStretch()
        dates.addStretch()
        self.clear_filters = QPushButton("Reset filters")
        dates.addWidget(self.clear_filters)
        history_layout.addLayout(dates)
        history_layout.addWidget(self.date_range_controls)
        self.date_range_controls.hide()
        self.result_count = QLabel()
        self.result_count.setObjectName("Muted")
        history_layout.addWidget(self.result_count)

        buttons = QHBoxLayout()
        self.open_entry = QPushButton("Open Session Entry…")
        self.open_entry.setObjectName("Primary")
        self.delete = QPushButton("Delete Session")
        self.delete.setObjectName("Danger")
        buttons.addWidget(self.open_entry)
        self.tag_selected = QPushButton("Tag selected…")
        buttons.addWidget(self.tag_selected)
        self.show_details = QCheckBox("Show timing details")
        self.show_details.toggled.connect(self._set_timing_details)
        buttons.addWidget(self.show_details)
        buttons.addStretch()
        buttons.addWidget(self.delete)
        history_layout.addLayout(buttons)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "Started",
            "Finished",
            "Session Objective",
            "Mode",
            "Session Span",
            "Focused",
            "Non-Focus",
            "Preset",
            "Tags",
            "Completion Notes",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setWordWrap(True)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._set_timing_details(False)
        self.session_splitter = QSplitter(Qt.Orientation.Vertical)
        self.session_splitter.setChildrenCollapsible(False)
        self.session_splitter.addWidget(self.table)
        self.note_detail = QPlainTextEdit()
        self.note_detail.setReadOnly(True)
        self.note_detail.setPlaceholderText("Select a session to read its complete notes here.")
        self.note_detail.setAccessibleName("Selected session completion notes")
        self.note_detail.setMinimumHeight(70)
        note_pane = QWidget()
        note_layout = QVBoxLayout(note_pane)
        note_layout.setContentsMargins(0, 0, 0, 0)
        note_layout.addWidget(QLabel("Selected Session · Completion Notes"))
        note_layout.addWidget(self.note_detail)
        self.session_splitter.addWidget(note_pane)
        self.session_splitter.setStretchFactor(0, 1)
        self.session_splitter.setStretchFactor(1, 0)
        self.session_splitter.setSizes([500, 130])
        history_layout.addWidget(self.session_splitter, 1)
        self.period.currentIndexChanged.connect(self._filters_changed)
        self.from_date.dateChanged.connect(self._filters_changed)
        self.to_date.dateChanged.connect(self._filters_changed)
        self.tag_filter.changed.connect(self.refresh)
        self.tag_mode.currentIndexChanged.connect(self.refresh)
        self.clear_filters.clicked.connect(self._reset_filters)
        self.from_date.setEnabled(False)
        self.to_date.setEnabled(False)

        self.tag_selected.clicked.connect(self.tag_selected_entries)
        self.open_entry.clicked.connect(self.open_selected_entry)
        self.delete.clicked.connect(self.delete_entry)
        self.table.cellDoubleClicked.connect(lambda row, column: self.open_selected_entry())
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.day_start.currentIndexChanged.connect(self._reporting_options_changed)
        self.chart_days.currentIndexChanged.connect(self._reporting_options_changed)
        self.store.sessions_changed.connect(self.refresh)
        self.store.settings_changed.connect(self._load_reporting_settings)
        self._load_reporting_settings()
        self.refresh()

    def _set_timing_details(self, visible):
        for column in (1, 3, 4, 6, 7):
            self.table.setColumnHidden(column, not visible)

    def _tagged_sessions(self):
        return filter_sessions(self.store.sessions, tags=self.tag_filter.tags(),
                               tag_mode=self.tag_mode.currentData())

    def _history_sessions(self):
        days = self.period.currentData()
        start = end = None
        if days == -1:
            start = self.from_date.date().toPython()
            end = self.to_date.date().toPython()
            if start > end:
                return []
        elif days:
            end = current_reporting_day(int(self.store.settings.get("history_day_start_hour", 0)))
            start = end - timedelta(days=days - 1)
        return filter_sessions(self._tagged_sessions(), start=start, end=end,
                               start_hour=int(self.store.settings.get("history_day_start_hour", 0)))

    def _filters_changed(self, *args):
        custom = self.period.currentData() == -1
        self.date_range_controls.setVisible(custom)
        self.from_date.setEnabled(custom)
        self.to_date.setEnabled(custom)
        self.refresh()

    def _reset_filters(self):
        self.period.setCurrentIndex(0)
        self.tag_filter.text.clear()
        self.tag_mode.setCurrentIndex(0)
        self.refresh()

    def _selection_changed(self):
        self._update_actions()
        session = self.selected_session()
        self.note_detail.setPlainText((session.get("completion_note", "") or "") if session else "")

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
        selected = set(self.selected_ids())
        self.table.setRowCount(0)
        selected_rows = []

        self.tag_filter.set_available(available_tags(self.store.sessions))
        sessions = self._history_sessions()
        invalid_dates = self.period.currentData() == -1 and self.from_date.date() > self.to_date.date()
        self.result_count.setText(
            "Choose a From date on or before Through." if invalid_dates else
            f"{len(sessions)} of {len(self.store.sessions)} sessions · Newest first · Dates use the reporting-day boundary"
        )
        def started_timestamp(session):
            started = parse_iso_datetime(session.get("started_at"))
            return started.timestamp() if started else float('-inf')
        for session in sorted(sessions, key=started_timestamp, reverse=True):
            row = self.table.rowCount()
            self.table.insertRow(row)
            note = session.get("completion_note", "") or ""
            lines = note.splitlines()
            note_preview = "\n".join(line[:120] + ("…" if len(line) > 120 else "") for line in lines[:3])
            if len(lines) > 3:
                note_preview += "\n…"
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
                ", ".join(normalize_tags(session.get("tags", []))),
                note_preview,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, session.get("id"))
                if col == 6:
                    item.setToolTip("Derived automatically: Session Span minus Focused Time")
                if col == 9:
                    item.setToolTip(note)
                self.table.setItem(row, col, item)
            if session.get("id") in selected:
                selected_rows.append(row)

        for column, width in enumerate((145, 145, 180, 90, 100, 100, 100, 140, 150, 340)):
            self.table.setColumnWidth(column, width)
        self.table.resizeRowsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        for row in selected_rows:
            self.table.selectionModel().select(
                self.table.model().index(row, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )
        self._refresh_stats()
        self._selection_changed()

    def _daily_totals(self, start_hour: int) -> dict[date, int]:
        totals: dict[date, int] = {}
        for session in self._tagged_sessions():
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

        total_seconds = sum(max(0, int(s.get("focused_seconds", 0) or 0)) for s in self._tagged_sessions())
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
            for s in self._tagged_sessions()
            if int(s.get("focused_seconds", 0) or 0) > 0
        ]
        if focused_values:
            avg_focus = sum(focused_values) / len(focused_values)
            median_focus = statistics.median(focused_values)
            longest = max(self._tagged_sessions(), key=lambda s: int(s.get("focused_seconds", 0) or 0))
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
        for session in self._tagged_sessions():
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

    def selected_ids(self):
        return [self.table.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
                for index in self.table.selectionModel().selectedRows()
                if self.table.item(index.row(), 0)]

    def selected_id(self):
        ids = self.selected_ids()
        return ids[0] if len(ids) == 1 else None

    def tag_selected_entries(self):
        ids = self.selected_ids()
        if not ids:
            return
        dialog = BulkTagDialog(len(ids), available_tags(self.store.sessions), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.store.update_session_tags(ids, dialog.editor.tags(), remove=dialog.mode.currentData())
            except PersistenceError as error:
                QMessageBox.critical(self, "Tags Were Not Saved", str(error))

    def selected_session(self):
        return self.store.session_by_id(self.selected_id())

    def _update_actions(self) -> None:
        selected = self.selected_id() is not None
        self.open_entry.setEnabled(selected)
        self.delete.setEnabled(selected)
        self.tag_selected.setEnabled(bool(self.selected_ids()))

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
            try:
                self.store.delete_session(sid)
            except PersistenceError as error:
                QMessageBox.critical(self, "Session Was Not Deleted", str(error))

