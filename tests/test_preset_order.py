import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from project.persistence import PersistenceError
from project.presets import PresetsPage
from project.store import Store
from tests.qt_helpers import dispose


class PresetOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = Store(self.root)
        self.addCleanup(self.store._resource_timer.stop)
        for pid in ("first", "second"):
            self.store.upsert_preset(
                {"id": pid, "name": pid.title(), "mode": "stopwatch", "minutes": 30, "custom": pid}
            )
        self.page = PresetsPage(self.store)
        self.addCleanup(lambda: dispose(self.page))

    def test_reordering_persists_with_default_and_details_intact(self):
        original = {p["id"]: copy.deepcopy(p) for p in self.store.presets}
        self.store.reorder_presets(["second", "default", "first"])
        restored = Store(self.root)
        self.addCleanup(lambda: restored._resource_timer.stop())
        self.assertEqual([p["id"] for p in restored.presets], ["second", "default", "first"])
        self.assertEqual({p["id"]: p for p in restored.presets}, original)

    def test_move_buttons_keep_unsaved_editor_text(self):
        self.page.list.setCurrentRow(2)
        self.page.name.setText("Unsaved draft name")
        self.page.move_up.click()
        self.assertEqual([p["id"] for p in self.store.presets], ["default", "second", "first"])
        self.assertEqual(self.page.list.currentRow(), 1)
        self.assertEqual(self.page.name.text(), "Unsaved draft name")
        self.assertEqual(self.store.preset_by_id("second")["name"], "Second")

    def test_invalid_or_failed_order_leaves_data_unchanged(self):
        original = copy.deepcopy(self.store.presets)
        before = self.store.state_path.read_bytes()
        with self.assertRaises(ValueError):
            self.store.reorder_presets(["first", "first", "default"])
        with patch.object(self.store, "_write", side_effect=PersistenceError("disk full")):
            with self.assertRaises(PersistenceError):
                self.store.reorder_presets(["second", "first", "default"])
        self.assertEqual(self.store.presets, original)
        self.assertEqual(self.store.state_path.read_bytes(), before)
