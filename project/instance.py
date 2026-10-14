"""Single-process coordination, independent of window construction."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QWidget


class SingleInstanceGuard:
    """
    A global lock prevents multiple Cyndaquil processes, including copies
    launched from different folders. A local server asks the existing process
    to restore its main window when Cyndaquil is launched again.
    """

    SERVER_NAME = "Cyndaquil_Productivity_Instance"

    def __init__(self):
        temp_dir = Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)
        )
        self.lock = QLockFile(str(temp_dir / "Cyndaquil_Productivity.lock"))
        self.lock.setStaleLockTime(10000)
        self.server: QLocalServer | None = None

    def acquire(self) -> bool:
        if self.lock.tryLock(0):
            return True

        # Ask the running instance to show itself.
        self.notify_existing()

        # If the lock was left by a crashed process, allow Qt to remove only
        # a lock it considers stale, then try once more.
        if self.lock.removeStaleLockFile():
            return self.lock.tryLock(0)

        return False

    def notify_existing(self) -> None:
        socket = QLocalSocket()
        socket.connectToServer(self.SERVER_NAME)
        if socket.waitForConnected(250):
            socket.write(b"show")
            socket.waitForBytesWritten(250)
            socket.disconnectFromServer()

    def start_server(self, window: QWidget) -> None:
        QLocalServer.removeServer(self.SERVER_NAME)
        self.server = QLocalServer(window)

        if self.server.listen(self.SERVER_NAME):
            self.server.newConnection.connect(lambda: self._incoming(window))

    def _incoming(self, window: QWidget) -> None:
        if not self.server:
            return

        socket = self.server.nextPendingConnection()
        if socket:
            socket.waitForReadyRead(100)
            socket.readAll()
            socket.disconnectFromServer()

        window.restore_main()
