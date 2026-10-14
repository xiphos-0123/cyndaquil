import unittest
from datetime import date

from project.history_analytics import best_window, daily_totals, trend, window_total


class AnalyticsTests(unittest.TestCase):
    def test_reporting_boundary_keeps_early_session_on_previous_day(self):
        sessions = [
            {"started_at": "2026-10-14T03:59:00+05:30", "focused_seconds": 600},
            {"started_at": "2026-10-14T04:00:00+05:30", "focused_seconds": 1200},
            {"started_at": "invalid", "focused_seconds": 9999},
        ]
        self.assertEqual(
            daily_totals(sessions, 4), {date(2026, 10, 13): 600, date(2026, 10, 14): 1200}
        )

    def test_trend_compares_adjacent_windows(self):
        totals = {date(2026, 10, 7): 100, date(2026, 10, 14): 150}
        self.assertEqual(trend(totals, date(2026, 10, 14), 7), (150, 100, 50.0))
        self.assertEqual(window_total(totals, date(2026, 10, 14), 1), 150)

    def test_best_window_counts_missing_days_as_zero(self):
        totals = {date(2026, 10, 1): 100, date(2026, 10, 3): 200, date(2026, 10, 10): 50}
        self.assertEqual(
            best_window(totals, date(2026, 10, 14), 3), (date(2026, 10, 1), date(2026, 10, 3), 300)
        )
        self.assertEqual(best_window({}, date(2026, 10, 14), 7), (None, None, 0))
