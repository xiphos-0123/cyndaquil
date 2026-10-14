from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QSystemTrayIcon,
    QWidget,
)

from . import APP_NAME, VERSION
from .bootstrap import runtime_icon
from .companion import CompanionManager
from .history import HistoryPage
from .home import HomePage
from .library import ResourcesPage
from .media import AudioController
from .navigation import NavigationPanel
from .persistence import PersistenceError
from .presets import PresetsPage
from .session import IdleMonitor, SessionManager
from .settings import SettingsPage
from .store import Store
from .tag_editor import available_tags
from .ui_helpers import CompletionDialog


def app_root() -> Path:
    return Path(__file__).resolve().parent.parent


class MainWindow(QMainWindow):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.session: SessionManager | None = None
        self.audio: AudioController | None = None
        self.companion: CompanionManager | None = None
        self._quitting = False

        self.setWindowTitle("Cyndaquil")
        self.setMinimumSize(900, 620)
        self._apply_runtime_icon()

        central = QWidget()
        self.setCentralWidget(central)

        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.sidebar = NavigationPanel()
        self.emblem = self.sidebar.emblem
        self.quit_btn = self.sidebar.quit_button
        self.sidebar.page_requested.connect(
            lambda page, tab: self.navigate(page, tab if tab >= 0 else None)
        )
        self.sidebar.about_requested.connect(self.show_about)
        self._apply_runtime_icon()

        self.stack = QStackedWidget()
        self.home = HomePage(store)
        self.presets = PresetsPage(store)
        self.history = HistoryPage(store)
        self.resources = ResourcesPage(store)
        self.settings = SettingsPage(store)

        self.pages = [
            ("Focus Session", self.home),
            ("Focus Presets", self.presets),
            ("History", self.history),
            ("Resource Library", self.resources),
            ("Application Settings", self.settings),
        ]

        for _, page in self.pages:
            self.stack.addWidget(page)
        self.history.tabs.currentChanged.connect(self._history_tab_changed)

        shell.addWidget(self.sidebar)
        shell.addWidget(self.stack, 1)

        self._connect_home()

        self.store.settings_changed.connect(self.apply_application_settings)
        self.store.branding_changed.connect(self._apply_runtime_icon)
        self.quit_btn.clicked.connect(self.quit_requested)

        self.idle = IdleMonitor(lambda: self.store.settings, self)
        self.idle.idle_detected.connect(self.on_idle_detected)

        self.ritual_timer = QTimer(self)
        self.ritual_timer.timeout.connect(self._ritual_step)
        self.ritual_remaining = 0

        QShortcut(QKeySequence("Space"), self, activated=self.pause_resume)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self.distraction_dump)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.work_note)

        self._setup_tray()
        self.navigate(0)
        self.apply_application_settings()

    def _connect_home(self) -> None:
        self.home.start_requested.connect(self.start_session)
        self.home.pause_requested.connect(self.pause_resume)
        self.home.adjust_requested.connect(self.adjust_time)
        self.home.companion_requested.connect(self.open_companion)
        self.home.finish_requested.connect(self.finish_session)
        self.home.distraction_requested.connect(self.distraction_dump)
        self.home.work_note_requested.connect(self.work_note)
        self.home.audio_toggle_requested.connect(
            lambda: self.audio.toggle() if self.audio else None
        )
        self.home.audio_next_requested.connect(lambda: self.audio.next() if self.audio else None)
        self.home.audio_previous_requested.connect(
            lambda: self.audio.previous() if self.audio else None
        )
        self.home.audio_volume_changed.connect(self.set_volume)

    def _apply_runtime_icon(self) -> None:
        icon = runtime_icon(self.store.current_icon_path())
        self.setWindowIcon(icon)

        app = QApplication.instance()
        if app:
            app.setWindowIcon(icon)

        if hasattr(self, "tray"):
            self.tray.setIcon(icon)

        if hasattr(self, "emblem"):
            pixmap = QPixmap(str(self.store.current_icon_path()))
            if not pixmap.isNull():
                self.emblem.setPixmap(
                    pixmap.scaled(
                        self.emblem.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

    def apply_application_settings(self) -> None:
        app = QApplication.instance()
        if app:
            app.setFont(
                QFont(
                    self.store.settings.get("font_family", "Segoe UI"),
                    int(self.store.settings.get("font_size", 10)),
                )
            )

        if self.companion:
            self.companion.apply_settings(resize_windows=True)
            self.companion.refresh()

    def navigate(self, index: int, history_tab: int | None = None) -> None:
        if index == 2 and history_tab is not None:
            self.history.tabs.setCurrentIndex(history_tab)
        self.stack.setCurrentIndex(index)
        self.sidebar.set_current(index, self.history.tabs.currentIndex())

    def _history_tab_changed(self, tab: int) -> None:
        if self.stack.currentIndex() == 2:
            self.sidebar.set_current(2, tab)

    def show_about(self) -> None:
        folder = Path(__file__).resolve().parent.parent
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"{APP_NAME} {VERSION}\n\nFocus sessions, ambience, and session history.\n\n"
            f"Application folder: {folder}\nData folder: {self.store.data_dir}\n\n"
            "After pulling an update, fully quit Cyndaquil before launching it again.",
        )

    def start_session(self, config: dict) -> None:
        if self.session is not None:
            self.navigate(0)
            return

        self.navigate(0)
        config = dict(config)

        self.session = SessionManager(config, self)
        self.session.changed.connect(self.refresh_session)
        self.session.completed.connect(self.session_completed)

        self.audio = AudioController(self.store, self)
        ritual = max(0, int(self.store.settings.get("ritual_seconds", 0)))
        self.audio.set_playlist(
            config.get("music_ids", []),
            autoplay=(ritual == 0),
        )
        self.audio.track_changed.connect(self.home.set_track)
        self.audio.set_volume(int(self.store.settings.get("audio_volume", 55)))

        self.home.set_active(
            config,
            self.session,
            self.audio.has_music(),
            self.audio.current_name(),
        )

        self.idle.start()
        self._update_tray()
        self.refresh_session()

        if ritual > 0:
            self.ritual_remaining = ritual
            self.home.set_ritual(self.ritual_remaining)
            self.ritual_timer.start(1000)
        else:
            self.session.start()

    def _ritual_step(self) -> None:
        if not self.session:
            self.ritual_timer.stop()
            return

        self.ritual_remaining -= 1
        if self.ritual_remaining <= 0:
            self.ritual_timer.stop()
            if self.audio and self.audio.has_music():
                self.audio.player.play()
            self.session.start()
        else:
            self.home.set_ritual(self.ritual_remaining)

    def refresh_session(self) -> None:
        if not self.session:
            return

        self.home.refresh_active()
        if self.companion:
            self.companion.refresh()
        self._update_tray()

    def pause_resume(self) -> None:
        if not self.session or self.ritual_timer.isActive():
            return
        self.session.toggle_pause()

    def adjust_time(self, seconds: int) -> None:
        if self.session:
            self.session.adjust_focus(seconds)

    def distraction_dump(self) -> None:
        if not self.session:
            return

        from PySide6.QtWidgets import QInputDialog

        text, accepted = QInputDialog.getMultiLineText(
            self,
            "Distraction Dump",
            "Record the distracting thought, then return to the session:",
        )
        if accepted and text.strip():
            self.session.add_distraction(text)

    def work_note(self) -> None:
        if not self.session:
            return

        from PySide6.QtWidgets import QInputDialog

        text, accepted = QInputDialog.getMultiLineText(
            self,
            "Work Note",
            "Capture a note for the final Completion Notes editor:",
        )
        if accepted and text.strip():
            self.session.add_work_note(text)

    def set_volume(self, value: int) -> None:
        self.store.settings["audio_volume"] = int(value)
        self.store.save_state()
        if self.audio:
            self.audio.set_volume(value)

    def open_companion(self) -> None:
        if not self.session:
            return

        if self.companion is None:
            self.companion = CompanionManager(self.store, self.session, self)
            self.companion.pause_requested.connect(self.pause_resume)
            self.companion.adjust_requested.connect(self.adjust_time)
            self.companion.main_requested.connect(self.restore_main)
            self.companion.finish_requested.connect(self.finish_session)
        else:
            self.companion.apply_settings(resize_windows=False)
            self.companion.refresh()

        if self.companion.show():
            self.hide()
        else:
            QMessageBox.information(
                self,
                "Floating Companions Disabled",
                "Both companion windows are disabled, or the enabled companion has no visible content. "
                "Configure them in Application Settings.",
            )

    def restore_main(self) -> None:
        if self.companion:
            self.companion.hide()

        self.show()
        self.raise_()
        self.activateWindow()
        self.navigate(0)

    def session_completed(self) -> None:
        if self.tray.isVisible():
            self.tray.showMessage(
                "Cyndaquil",
                "The focus timer has completed.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )

    def _confirm_failure_discard(self, parent) -> bool:
        box = QMessageBox(parent)
        box.setWindowTitle("Discard Session Without Saving?")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("This session will be permanently discarded and will not appear in History.")
        box.setInformativeText(
            "Focused time, completion notes, and the session record cannot be recovered after this action."
        )
        discard = box.addButton("Discard Session", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.exec()
        return box.clickedButton() == discard

    def finish_session(self) -> None:
        if not self.session:
            return

        parent = (
            self.companion.dialog_parent()
            if self.companion and self.companion.isVisible()
            else self
        )

        dialog = CompletionDialog(
            parent,
            self.session.work_notes_text(),
            self.session.tags,
            available_tags(self.store.sessions),
        )
        result = dialog.exec()

        if result == CompletionDialog.SAVE:
            self.session.tags = dialog.tags.tags()
            self._end_session(dialog.text(), save_history=True)
        elif result == CompletionDialog.FAILURE:
            if self._confirm_failure_discard(parent):
                self._end_session("", save_history=False)

    def _end_session(self, note: str = "", save_history: bool = True) -> None:
        if not self.session:
            return

        self.ritual_timer.stop()
        payload = self.session.finish_payload(note)

        if save_history:
            try:
                self.store.add_session(payload)
            except PersistenceError as error:
                # Retain the edited completion note when the user retries.
                self.session.work_notes = [note] if note else []
                QMessageBox.critical(self, "Session Was Not Saved", str(error))
                return

        if self.audio:
            self.audio.stop()
            self.audio.deleteLater()
            self.audio = None

        if self.companion:
            self.companion.shutdown()
            self.companion.deleteLater()
            self.companion = None

        self.idle.stop()
        self.session.deleteLater()
        self.session = None

        self.sidebar.show()
        self.home.clear_active()
        self._update_tray()

        self.show()
        self.raise_()
        self.navigate(0)

    # ---------- inactivity ----------
    def on_idle_detected(self, idle_seconds: int) -> None:
        if not self.session or self.session.state != "running":
            return

        parent = (
            self.companion.dialog_parent()
            if self.companion and self.companion.isVisible()
            else self
        )

        minutes = max(1, round(idle_seconds / 60))
        box = QMessageBox(parent)
        box.setWindowTitle("Inactivity Check")
        box.setText(
            f"No keyboard or mouse activity was detected for approximately {minutes} minutes."
        )
        box.setInformativeText("How should this time be handled?")

        box.addButton(
            "Keep Counting",
            QMessageBox.ButtonRole.AcceptRole,
        )
        pause = box.addButton(
            "Pause Session",
            QMessageBox.ButtonRole.ActionRole,
        )
        remove = box.addButton(
            "Remove Idle Time and Pause",
            QMessageBox.ButtonRole.DestructiveRole,
        )

        box.exec()
        clicked = box.clickedButton()

        if clicked == pause:
            self.session.pause()
        elif clicked == remove:
            self.session.adjust_focus(-idle_seconds)
            self.session.pause()

    # ---------- tray ----------
    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(
            runtime_icon(self.store.current_icon_path()),
            self,
        )

        menu = QMenu()
        self.tray_show = QAction("Show Cyndaquil", self)
        self.tray_pause = QAction("Pause / Resume Session", self)
        self.tray_companion = QAction("Open Floating Companions", self)
        self.tray_quit = QAction("Quit Cyndaquil", self)

        self.tray_show.triggered.connect(self.restore_main)
        self.tray_pause.triggered.connect(self.pause_resume)
        self.tray_companion.triggered.connect(self.open_companion)
        self.tray_quit.triggered.connect(self.quit_requested)

        menu.addAction(self.tray_show)
        menu.addAction(self.tray_pause)
        menu.addAction(self.tray_companion)
        menu.addSeparator()
        menu.addAction(self.tray_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        self._update_tray()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.restore_main()

    def _update_tray(self) -> None:
        active = self.session is not None
        self.tray_pause.setVisible(active)
        self.tray_companion.setVisible(active)

    # ---------- quit ----------
    def quit_requested(self) -> None:
        if self.session:
            parent = (
                self.companion.dialog_parent()
                if self.companion and self.companion.isVisible()
                else self
            )

            box = QMessageBox(parent)
            box.setWindowTitle("Quit Cyndaquil")
            box.setText("A focus session is currently active.")

            save = box.addButton(
                "Save Session and Quit",
                QMessageBox.ButtonRole.AcceptRole,
            )
            discard = box.addButton(
                "Finish as Failure and Quit",
                QMessageBox.ButtonRole.DestructiveRole,
            )
            cancel = box.addButton(
                "Cancel",
                QMessageBox.ButtonRole.RejectRole,
            )

            box.exec()
            clicked = box.clickedButton()

            if clicked == cancel or clicked is None:
                return

            if clicked == discard and not self._confirm_failure_discard(parent):
                return
            self._end_session(self.session.work_notes_text(), save_history=(clicked == save))
            if self.session is not None:
                return

        self._quitting = True
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        if self._quitting:
            event.accept()
            return

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            event.ignore()
        else:
            event.ignore()
            self.quit_requested()


def run() -> None:
    """Compatibility entry point for existing launchers and local integrations."""
    from .app import run as run_application

    run_application(app_root())
