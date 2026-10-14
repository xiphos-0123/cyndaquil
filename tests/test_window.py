import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication
from project.main import MainWindow
from project.persistence import PersistenceError
from project.session import SessionManager
from project.store import Store


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
        self.addCleanup(self.window.hide)

    def test_failed_save_keeps_session_available_for_retry(self):
        self.window.session = SessionManager({'mode': 'stopwatch'})
        session = self.window.session
        session.start()
        with patch.object(self.store, 'add_session', side_effect=PersistenceError('disk full')):
            with patch('project.main.QMessageBox.critical') as dialog:
                self.window._end_session('keep this note')
                dialog.assert_called_once()
        self.assertIs(self.window.session, session)
        self.assertEqual(session.state, 'paused')
        self.assertEqual(session.work_notes_text(), 'keep this note')
        self.assertEqual(self.store.sessions, [])

    def test_close_without_tray_uses_quit_confirmation(self):
        event = QCloseEvent()
        with patch('project.main.QSystemTrayIcon.isSystemTrayAvailable', return_value=False):
            with patch.object(self.window, 'quit_requested') as quit_requested:
                self.window.closeEvent(event)
                quit_requested.assert_called_once()
        self.assertFalse(event.isAccepted())
        self.assertFalse(self.window._quitting)
