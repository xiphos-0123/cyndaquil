"""Productivity presentation; calculations live in history_analytics."""

from __future__ import annotations

import statistics
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .history_analytics import best_window, daily_totals, trend, window_days, window_total
from .history_chart import DailyProgressChart
from .history_records import _session_span_seconds
from .utils import current_reporting_day, format_seconds, reporting_day_bounds


class StatisticsView(QWidget):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        stats_layout = QVBoxLayout(self)
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
            self.current_day,
            self.last7,
            self.last30,
            self.last90,
            self.trend7,
            self.trend30,
            self.daily_average,
            self.total,
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
            self.average_session,
            self.median_session,
            self.longest_session,
            self.average_span,
            self.focus_efficiency,
            self.nonfocus_summary,
            self.best_day,
            self.best7,
            self.best30,
        ):
            analysis_layout.addWidget(metric)
        analysis_layout.addStretch()

        overview.addWidget(chart_card, 3)
        overview.addWidget(analysis_card, 2)
        stats_layout.addLayout(overview, 2)

        self.day_start.currentIndexChanged.connect(self._reporting_options_changed)
        self.chart_days.currentIndexChanged.connect(self._reporting_options_changed)
        self.store.settings_changed.connect(self._load_reporting_settings)
        self._load_reporting_settings()

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
        self.chart_days.setCurrentIndex(
            chart_index if chart_index >= 0 else self.chart_days.findData(14)
        )
        self.day_start.blockSignals(False)
        self.chart_days.blockSignals(False)

    def _reporting_options_changed(self, *args) -> None:
        self.store.update_settings(
            {
                "history_day_start_hour": int(self.day_start.currentData() or 0),
                "history_chart_days": int(self.chart_days.currentData() or 14),
            }
        )

    def refresh(self, sessions) -> None:
        now = datetime.now().astimezone()
        start_hour = int(self.store.settings.get("history_day_start_hour", 0))
        chart_days = int(self.store.settings.get("history_chart_days", 14))
        current_day = current_reporting_day(start_hour, now)
        totals = daily_totals(sessions, start_hour)

        # Current reporting day.
        current_seconds = totals.get(current_day, 0)
        start, end = reporting_day_bounds(current_day, start_hour, now.tzinfo)
        self.current_day[1].setText(format_seconds(current_seconds))
        self.current_day[2].setText(
            f"{start.strftime('%d %b %H:%M')} → {end.strftime('%d %b %H:%M')}"
        )

        # Rolling reporting-day totals.
        last7 = window_total(totals, current_day, 7)
        last30 = window_total(totals, current_day, 30)
        last90 = window_total(totals, current_day, 90)
        self.last7[1].setText(format_seconds(last7))
        self.last7[2].setText(f"Daily average {format_seconds(last7 / 7)}")
        self.last30[1].setText(format_seconds(last30))
        self.last30[2].setText(f"Daily average {format_seconds(last30 / 30)}")
        self.last90[1].setText(format_seconds(last90))
        self.last90[2].setText(f"Daily average {format_seconds(last90 / 90)}")

        # Window-over-window trends.
        current7, previous7, change7 = trend(totals, current_day, 7)
        current30, previous30, change30 = trend(totals, current_day, 30)
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

        total_seconds = sum(max(0, int(s.get("focused_seconds", 0) or 0)) for s in sessions)
        self.total[1].setText(format_seconds(total_seconds))
        if totals:
            first_day = min(totals)
            history_days = max(1, (current_day - first_day).days + 1)
            average_day = total_seconds / history_days
            self.daily_average[1].setText(format_seconds(average_day))
            self.daily_average[2].setText(
                f"Across {history_days} reporting days since {first_day.strftime('%d %b %Y')}"
            )
            self.total[2].setText(f"Recorded since {first_day.strftime('%d %b %Y')}")
        else:
            self.daily_average[1].setText("00:00:00")
            self.daily_average[2].setText("No reporting-day history yet")
            self.total[2].setText("No focused time recorded yet")

        # Progression chart.
        days = window_days(current_day, chart_days)
        chart_values = [(day, totals.get(day, 0)) for day in days]
        self.chart.set_data(chart_values)
        self.chart_subtitle.setText(
            f"{chart_days}-day view · Reporting boundary {start_hour:02d}:00 · "
            "orange bars = focused time · cream line = rolling 7-day daily average · yellow dashed line = selected-window average"
        )

        # Session-duration analysis.
        focused_values = [
            max(0, int(s.get("focused_seconds", 0) or 0))
            for s in sessions
            if int(s.get("focused_seconds", 0) or 0) > 0
        ]
        if focused_values:
            avg_focus = sum(focused_values) / len(focused_values)
            median_focus = statistics.median(focused_values)
            longest = max(sessions, key=lambda s: int(s.get("focused_seconds", 0) or 0))
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
        for session in sessions:
            span = _session_span_seconds(session)
            if span is None or span <= 0:
                continue
            focus = max(0, int(session.get("focused_seconds", 0) or 0))
            spans.append(span)
            nonfocus_values.append(max(0, span - focus))
            efficiency_focus += min(focus, span)
            efficiency_span += span

        if spans:
            self.average_span.setText(
                f"Average Session Span\n{format_seconds(sum(spans) / len(spans))}"
            )
            efficiency = (efficiency_focus / efficiency_span * 100) if efficiency_span else 0.0
            self.focus_efficiency.setText(
                f"Focus Efficiency\n{efficiency:.1f}% of recorded session span"
            )
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
            best7_start, best7_end, best7_seconds = best_window(totals, current_day, 7)
            best30_start, best30_end, best30_seconds = best_window(totals, current_day, 30)
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
