import copy
import unittest
from datetime import date

from project.history_filters import filter_sessions, normalize_tags


class HistoryFilterTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"id": "before", "started_at": "2026-10-13T03:59:59+05:30", "tags": ["Waking Up Arc"]},
            {"id": "start", "started_at": "2026-10-13T04:00:00+05:30", "tags": ["Reading"]},
            {"id": "end", "started_at": "2026-10-14T03:59:59+05:30"},
            {"id": "after", "started_at": "2026-10-14T04:00:00+05:30"},
            {"id": "legacy"},
        ]

    def test_reporting_day_range_is_inclusive_and_does_not_mutate(self):
        original = copy.deepcopy(self.records)
        selected = filter_sessions(
            self.records, start=date(2026, 10, 13), end=date(2026, 10, 13), start_hour=4
        )
        self.assertEqual([s["id"] for s in selected], ["start", "end"])
        self.assertEqual(self.records, original)
        self.assertEqual(filter_sessions(self.records), self.records)

    def test_include_and_exclude_any_tag_ignore_case(self):
        include = filter_sessions(self.records, tags=["waking up arc", "READING"])
        exclude = filter_sessions(
            self.records, tags=["waking up arc", "READING"], tag_mode="exclude"
        )
        self.assertEqual([s["id"] for s in include], ["before", "start"])
        self.assertEqual([s["id"] for s in exclude], ["end", "after", "legacy"])

    def test_tag_normalization_preserves_spelling(self):
        self.assertEqual(
            normalize_tags(" Waking Up Arc, Reading,reading,, "), ["Waking Up Arc", "Reading"]
        )
        self.assertEqual(normalize_tags(None), [])

    def test_combined_date_and_tag_filters(self):
        selected = filter_sessions(
            self.records,
            start=date(2026, 10, 13),
            end=date(2026, 10, 13),
            start_hour=4,
            tags=["Reading"],
        )
        self.assertEqual([s["id"] for s in selected], ["start"])
