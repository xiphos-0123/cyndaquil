"""Integration checks for record preservation and failed history saves."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from project.persistence import PersistenceError
from project.store import Store


class StoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = Store(self.root)
        self.addCleanup(self.store._resource_timer.stop)

    def test_failed_history_changes_preserve_memory_and_disk(self):
        self.store.add_session({'id': 'saved', 'focused_seconds': 12})
        before = self.store.sessions_path.read_bytes()
        with patch.object(self.store, '_write', side_effect=PersistenceError('disk full')):
            for operation in (
                lambda: self.store.add_session({'id': 'new'}),
                lambda: self.store.update_session('saved', {'focused_seconds': 99}),
                lambda: self.store.delete_session('saved'),
            ):
                with self.assertRaises(PersistenceError):
                    operation()
                self.assertEqual(self.store.sessions, [{'id': 'saved', 'focused_seconds': 12}])
                self.assertEqual(self.store.sessions_path.read_bytes(), before)

    def test_existing_checkout_history_survives_reload_on_a_copy(self):
        source = Path(__file__).resolve().parents[1] / '.cyndaquil' / 'sessions.json'
        records = json.loads(source.read_text(encoding='utf-8'))
        shutil.copy2(source, self.store.sessions_path)
        restored = Store(self.root)
        self.addCleanup(lambda: restored._resource_timer.stop())
        expected = [{k: v for k, v in record.items() if k != 'break_seconds'} for record in records]
        self.assertEqual(restored.sessions, expected)
        self.assertEqual(json.loads(restored.sessions_path.read_text(encoding='utf-8')), expected)

    def test_corrupt_history_stops_startup_without_overwriting(self):
        self.store.sessions_path.write_bytes(b'broken history')
        with self.assertRaises(PersistenceError):
            Store(self.root)
        self.assertEqual(self.store.sessions_path.read_bytes(), b'broken history')
