import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from project.main import MainWindow
from project.persistence import PersistenceError
from project.session import SessionManager
from project.store import Store
from tests.qt_helpers import dispose


class WindowSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name))
        self.window = MainWindow(self.store)
        self.addCleanup(self.store._resource_timer.stop)
        self.addCleanup(lambda: dispose(self.window))

    def test_failed_save_keeps_session_available_for_retry(self):
        self.window.session = SessionManager({"mode": "stopwatch"})
        session = self.window.session
        session.start()
        with patch.object(self.store, "add_session", side_effect=PersistenceError("disk full")):
            with patch("project.main.QMessageBox.critical") as dialog:
                self.window._end_session("keep this note")
                dialog.assert_called_once()
        self.assertIs(self.window.session, session)
        self.assertEqual(session.state, "paused")
        self.assertEqual(session.work_notes_text(), "keep this note")
        self.assertEqual(self.store.sessions, [])

    def test_close_without_tray_uses_quit_confirmation(self):
        event = QCloseEvent()
        with patch("project.main.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            with patch.object(self.window, "quit_requested") as quit_requested:
                self.window.closeEvent(event)
                quit_requested.assert_called_once()
        self.assertFalse(event.isAccepted())
        self.assertFalse(self.window._quitting)

    def test_sidebar_opens_history_and_statistics_directly(self):
        self.window.sidebar.buttons[2].click()
        self.assertEqual(self.window.stack.currentWidget(), self.window.history)
        self.assertEqual(self.window.history.views.currentIndex(), 0)
        self.window.sidebar.buttons[3].click()
        self.assertEqual(self.window.history.views.currentIndex(), 1)
        self.assertTrue(self.window.sidebar.buttons[3].isChecked())
        self.assertFalse(self.window.sidebar.buttons[2].isChecked())
        self.window.history.views.setCurrentIndex(0)
        self.assertTrue(self.window.sidebar.buttons[2].isChecked())
        self.assertEqual(self.window.sidebar.version_label.text(), "Version 5.3.0")

    def test_quit_and_save_preserves_work_notes(self):
        session = SessionManager({"mode": "stopwatch"})
        session.add_work_note("Keep this work note when quitting")
        self.window.session = session
        save, discard, cancel = object(), object(), object()
        box = MagicMock()
        box.addButton.side_effect = [save, discard, cancel]
        box.clickedButton.return_value = save
        with (
            patch("project.main.QMessageBox", return_value=box),
            patch("project.main.QApplication.quit"),
        ):
            self.window.quit_requested()
        self.assertEqual(
            self.store.sessions[-1]["completion_note"], "Keep this work note when quitting"
        )
