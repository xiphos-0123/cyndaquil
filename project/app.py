"""Application bootstrap: Qt setup, data loading, and process coordination."""

import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_NAME, VERSION
from .bootstrap import runtime_icon, set_windows_app_id
from .instance import SingleInstanceGuard
from .main import MainWindow
from .persistence import PersistenceError
from .store import Store
from .theme import CYNDAQUIL_QSS
from .ui_helpers import WheelInputGuard


def run(root: Path | None = None) -> None:
    """Start the desktop application using its existing data directory."""
    root = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    set_windows_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(CYNDAQUIL_QSS)

    wheel_guard = WheelInputGuard(app)
    app.installEventFilter(wheel_guard)
    app._wheel_input_guard = wheel_guard

    guard = SingleInstanceGuard()
    if not guard.acquire():
        return

    try:
        store = Store(root)
    except PersistenceError as error:
        QMessageBox.critical(None, "Unable to Load Cyndaquil", str(error))
        return

    app.setFont(
        QFont(
            store.settings.get("font_family", "Segoe UI"),
            int(store.settings.get("font_size", 10)),
        )
    )
    app.setWindowIcon(runtime_icon(store.current_icon_path()))

    window = MainWindow(store)
    guard.start_server(window)

    # Keep the guard alive for the lifetime of the application.
    window._single_instance_guard = guard

    # Maximized is Cyndaquil's native/default workspace. It uses the available
    # screen without forcing an exclusive borderless full-screen mode.
    window.showMaximized()

    sys.exit(app.exec())
