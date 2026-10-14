import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from project.bulk_session_entry import BulkSessionEntryDialog
from project.persistence import PersistenceError
from project.store import Store
from tests.qt_helpers import dispose


class BulkEditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = Store(self.root)
        self.addCleanup(self.store._resource_timer.stop)
        for number, name in enumerate(("Alice", "Bob", "Untouched")):
            self.store.add_session(
                {
                    "id": str(number),
                    "mission": f"Review {name}",
                    "completion_note": f"🌱 Focus: {name}\n\nWork completed\n",
                    "started_at": "2026-10-14T12:00:00.123456+05:30",
                    "ended_at": "2026-10-14T13:00:00.234567+05:30",
                    "focused_seconds": 1800 + number,
                    "tags": [name],
                    "distractions": ["A multiline\nthought"],
                    "custom": {"keep": name},
                }
            )
        self.original = copy.deepcopy(self.store.sessions)
        self.dialog = BulkSessionEntryDialog(self.store, self.store.sessions[:2])
        self.addCleanup(lambda: dispose(self.dialog))

    def test_bulk_common_edit_preserves_differences_and_unselected_data(self):
        template = self.dialog.notes.toPlainText()
        self.dialog.notes.setPlainText(template.replace("Work completed", "Work reviewed"))
        with patch.object(self.store, "_write", wraps=self.store._write) as writer:
            self.dialog.save()
            self.assertEqual(writer.call_count, 1)
        for index in (0, 1):
            saved = self.store.sessions[index]
            self.assertEqual(
                saved["completion_note"],
                self.original[index]["completion_note"].replace("Work completed", "Work reviewed"),
            )
            for key in (
                "id",
                "started_at",
                "ended_at",
                "focused_seconds",
                "tags",
                "custom",
                "distractions",
                "mission",
            ):
                self.assertEqual(saved[key], self.original[index][key])
        self.assertEqual(self.store.sessions[2], self.original[2])
        self.assertEqual(json.loads(self.store.sessions_path.read_text()), self.store.sessions)

    def test_unedited_and_unchecked_fields_are_not_saved(self):
        before = self.store.sessions_path.read_bytes()
        self.assertEqual(self.dialog.build_updates(), {})
        self.dialog.notes.setPlainText("Do not apply this")
        self.dialog.apply_fields["completion_note"].setChecked(False)
        self.dialog.save()
        self.assertEqual(self.store.sessions, self.original)
        self.assertEqual(self.store.sessions_path.read_bytes(), before)

    def test_replacing_marker_changes_that_part_for_all_records(self):
        token = next(iter(self.dialog.note_mixed.sections))
        self.dialog.notes.setPlainText(self.dialog.notes.toPlainText().replace(token, "Shared"))
        self.dialog.save()
        for record in self.store.sessions[:2]:
            self.assertEqual(record["completion_note"], "🌱 Focus: Shared\n\nWork completed\n")

    def test_failed_commit_preserves_all_selected_records(self):
        self.dialog.notes.setPlainText("New common notes\n\nSecond paragraph\n")
        before = self.store.sessions_path.read_bytes()
        with patch.object(self.store, "_write", side_effect=PersistenceError("disk full")):
            with patch("project.bulk_session_entry.QMessageBox.warning") as warning:
                self.dialog.save()
                warning.assert_called_once()
        self.assertEqual(self.store.sessions, self.original)
        self.assertEqual(self.store.sessions_path.read_bytes(), before)
        self.assertEqual(self.dialog.result(), 0)

    def test_broken_marker_cannot_be_saved_as_record_text(self):
        token = next(iter(self.dialog.note_mixed.sections))
        self.dialog.notes.setPlainText(self.dialog.notes.toPlainText().replace(token, token[:-1]))
        with patch("project.bulk_session_entry.QMessageBox.warning") as warning:
            self.dialog.save()
            warning.assert_called_once()
        self.assertEqual(self.store.sessions, self.original)

    def test_stale_record_and_invalid_time_abort_whole_batch(self):
        self.dialog.notes.setPlainText("Batch edit")
        self.store.update_session("0", {"completion_note": "Newer saved edit"})
        with patch("project.bulk_session_entry.QMessageBox.warning"):
            self.dialog.save()
        self.assertEqual(self.store.sessions[0]["completion_note"], "Newer saved edit")
        self.assertEqual(self.store.sessions[1], self.original[1])
        before = copy.deepcopy(self.store.sessions)
        with self.assertRaises(ValueError):
            self.store.update_sessions(
                {
                    "0": {"ended_at": "2026-10-14T10:00:00+05:30"},
                    "1": {"mission": "Should not save"},
                }
            )
        self.assertEqual(self.store.sessions, before)

    def test_metadata_and_tag_changes_preserve_notes(self):
        self.dialog.text_fields["mission"].setText("Shared objective")
        self.dialog.tags.text.setText("Study")
        self.dialog.value_fields["focused_seconds"].setText("45m")
        self.dialog.save()
        for index in (0, 1):
            self.assertEqual(self.store.sessions[index]["mission"], "Shared objective")
            self.assertEqual(self.store.sessions[index]["focused_seconds"], 2700)
            self.assertEqual(
                self.store.sessions[index]["tags"], [self.original[index]["tags"][0], "Study"]
            )
            self.assertEqual(
                self.store.sessions[index]["completion_note"],
                self.original[index]["completion_note"],
            )

    def test_highlighting_does_not_mark_notes_as_edited(self):
        self.dialog.show()
        self.app.processEvents()
        self.assertFalse(self.dialog.apply_fields["completion_note"].isChecked())
        self.assertFalse(self.dialog.save_button.isEnabled())
        self.assertEqual(self.dialog.build_updates(), {})

    def test_checking_unchanged_timestamp_preserves_original_precision(self):
        before = self.store.sessions_path.read_bytes()
        self.dialog.apply_fields["started_at"].setChecked(True)
        self.dialog.apply_fields["ended_at"].setChecked(True)
        self.dialog.save()
        self.assertEqual(self.store.sessions, self.original)
        self.assertEqual(self.store.sessions_path.read_bytes(), before)

    def test_nonfinite_duration_is_rejected_without_any_record_change(self):
        self.dialog.value_fields["focused_seconds"].setText("1e999m")
        with patch("project.bulk_session_entry.QMessageBox.warning") as warning:
            self.dialog.save()
            warning.assert_called_once()
        self.assertEqual(self.store.sessions, self.original)
        self.assertEqual(self.dialog.result(), 0)
