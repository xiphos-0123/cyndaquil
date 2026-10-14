import copy
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QDate, QItemSelectionModel
from PySide6.QtWidgets import QApplication
from project.history import HistoryPage
from project.persistence import PersistenceError
from project.session import SessionManager
from project.session_entry import SessionEntryDialog
from project.store import Store
from project.ui_helpers import CompletionDialog


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = Store(self.root)
        self.addCleanup(self.store._resource_timer.stop)
        today = datetime.now().astimezone().replace(hour=12, minute=0, second=0, microsecond=0)
        self.today = today
        for number, age in enumerate((60, 15, 2, 0)):
            start = today - timedelta(days=age)
            self.store.add_session({
                'id': str(number), 'started_at': start.isoformat(),
                'ended_at': (start + timedelta(hours=1)).isoformat(),
                'focused_seconds': 1800, 'mission': f'Example {number}',
                'completion_note': 'First line\n\nSecond paragraph\nThird line',
                'distractions': ['Keep this thought'],
                'custom_field': {'preserved': True},
                **({'tags': ['Waking Up Arc']} if number < 2 else {}),
            })
        self.page = HistoryPage(self.store)
        self.addCleanup(self.page.hide)

    def test_tabs_and_recent_and_custom_dates_do_not_change_records(self):
        before = self.store.sessions_path.read_bytes()
        self.assertEqual(self.page.tabs.tabText(0), 'Session History')
        self.assertEqual(self.page.tabs.tabText(1), 'Statistics')
        self.assertEqual(self.page.table.rowCount(), 4)
        self.page.period.setCurrentIndex(self.page.period.findData(7))
        self.assertEqual(self.page.table.rowCount(), 2)
        self.page.period.setCurrentIndex(self.page.period.findData(30))
        self.assertEqual(self.page.table.rowCount(), 3)
        self.page.period.setCurrentIndex(self.page.period.findData(-1))
        qday = QDate(self.today.year, self.today.month, self.today.day)
        self.page.from_date.setDate(qday)
        self.page.to_date.setDate(qday)
        self.assertEqual(self.page.table.rowCount(), 1)
        self.page.from_date.setDate(qday.addDays(1))
        self.assertEqual(self.page.table.rowCount(), 0)
        self.assertIn('Choose', self.page.result_count.text())
        self.page._reset_filters()
        self.assertEqual(self.page.table.rowCount(), 4)
        self.assertEqual(self.store.sessions_path.read_bytes(), before)

    def test_tags_filter_both_history_and_statistics(self):
        self.page.tag_filter.text.setText('waking up arc')
        self.assertEqual(self.page.table.rowCount(), 2)
        self.assertEqual(self.page.total[1].text(), '01:00:00')
        self.page.tag_mode.setCurrentIndex(self.page.tag_mode.findData('exclude'))
        self.assertEqual(self.page.table.rowCount(), 2)
        self.assertEqual({s['id'] for s in self.page._history_sessions()}, {'2', '3'})

    def test_notes_keep_newlines_and_full_detail(self):
        self.assertIn('\n', self.page.table.item(0, 9).text())
        self.page.table.selectRow(0)
        self.assertEqual(self.page.note_detail.toPlainText(), self.store.sessions[3]['completion_note'])
        self.page.table.clearSelection()
        self.assertFalse(self.page.open_entry.isEnabled())
        self.assertEqual(self.page.note_detail.toPlainText(), '')

    def test_bulk_tags_preserve_other_fields_and_reload(self):
        original = copy.deepcopy(self.store.sessions)
        self.assertEqual(self.store.update_session_tags(['0', '2'], ['Study']), 2)
        for index in (0, 2):
            for key, value in original[index].items():
                if key != 'tags':
                    self.assertEqual(self.store.sessions[index][key], value)
        self.assertEqual(self.store.sessions[1], original[1])
        restored = Store(self.root)
        self.addCleanup(lambda: restored._resource_timer.stop())
        self.assertEqual(restored.sessions[0]['tags'], ['Waking Up Arc', 'Study'])
        self.assertEqual(restored.sessions[2]['tags'], ['Study'])
        self.store.update_session_tags(['0', '2'], ['study'], remove=True)
        self.assertEqual(self.store.sessions[0]['tags'], ['Waking Up Arc'])
        self.assertEqual(self.store.sessions[2]['tags'], [])

    def test_failed_bulk_save_is_transactional(self):
        original = copy.deepcopy(self.store.sessions)
        before = self.store.sessions_path.read_bytes()
        with patch.object(self.store, '_write', side_effect=PersistenceError('disk full')):
            with self.assertRaises(PersistenceError):
                self.store.update_session_tags(['0', '1'], ['Study'])
        self.assertEqual(self.store.sessions, original)
        self.assertEqual(self.store.sessions_path.read_bytes(), before)

    def test_session_editor_collapses_distractions_and_preserves_record(self):
        original = copy.deepcopy(self.store.sessions[0])
        editor = SessionEntryDialog(self.store, original)
        self.assertFalse(editor.distraction_toggle.isChecked())
        self.assertTrue(editor.distractions.parentWidget().isHidden())
        editor.distraction_toggle.click()
        self.assertFalse(editor.distractions.parentWidget().isHidden())
        editor.tags.text.setText('Waking Up Arc, Reading')
        editor.save()
        saved = self.store.session_by_id('0')
        self.assertEqual(saved['tags'], ['Waking Up Arc', 'Reading'])
        self.assertEqual(saved['custom_field'], original['custom_field'])
        self.assertEqual(saved['distractions'], original['distractions'])
        self.assertEqual(saved['completion_note'], original['completion_note'])
        self.assertEqual(saved['focused_seconds'], original['focused_seconds'])
        self.assertEqual(saved['started_at'], original['started_at'])

    def test_tag_edit_preserves_timestamp_precision_and_multiline_distractions(self):
        record = self.store.sessions[0]
        record.update({'started_at': '2026-10-01T12:00:00.123456+05:30',
                       'ended_at': '2026-10-01T13:00:00.654321+05:30',
                       'distractions': ['One thought\nwith two lines', 'Another thought'],
                       'completion_note': '  Original formatting\n\n'})
        editor = SessionEntryDialog(self.store, record)
        editor.tags.text.setText('Study')
        before = copy.deepcopy(record)
        editor.save()
        saved = self.store.session_by_id('0')
        for key in ('started_at', 'ended_at', 'distractions', 'completion_note'):
            self.assertEqual(saved[key], before[key])

    def test_completion_tags_flow_to_session_payload(self):
        dialog = CompletionDialog(initial_note='A note', initial_tags=['Reading'], available_tags=['Study'])
        dialog.tags.text.setText('Reading, Study')
        session = SessionManager({'mode': 'stopwatch'})
        session.tags = dialog.tags.tags()
        self.assertEqual(session.finish_payload(dialog.text())['tags'], ['Reading', 'Study'])

    def test_multiple_selection_enables_bulk_action_only(self):
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        for row in (0, 1):
            self.page.table.selectionModel().select(self.page.table.model().index(row, 0), flags)
        self.assertTrue(self.page.tag_selected.isEnabled())
        self.assertFalse(self.page.open_entry.isEnabled())
        self.assertFalse(self.page.delete.isEnabled())
        self.page.refresh()
        self.assertEqual(len(self.page.selected_ids()), 2)
