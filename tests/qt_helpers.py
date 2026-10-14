"""Destroy test widgets while QApplication and native services are still alive."""

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


def dispose(widget):
    widget.hide()
    widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()
