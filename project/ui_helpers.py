"""Shared input behavior and session completion dialog."""
from .tag_editor import TagEditor

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import (QAbstractScrollArea, QAbstractSpinBox, QComboBox, QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout)


class WheelInputGuard(QObject):
    """
    Prevent accidental mouse-wheel changes on numeric fields and combo boxes.

    When one of these controls sits inside a scrollable page, the wheel is
    redirected to that page instead so normal scrolling still works.
    """

    def eventFilter(self, watched, event):
        if event.type() != QEvent.Type.Wheel:
            return False

        if not isinstance(watched, (QAbstractSpinBox, QComboBox)):
            return False

        parent = watched.parentWidget()
        scroll_area = None
        while parent is not None:
            if isinstance(parent, QAbstractScrollArea):
                scroll_area = parent
                break
            parent = parent.parentWidget()

        if scroll_area is not None:
            bar = scroll_area.verticalScrollBar()
            delta = event.angleDelta().y()
            if delta:
                step = max(24, bar.singleStep() * 3)
                bar.setValue(bar.value() - (step if delta > 0 else -step))

        event.accept()
        return True


class CompletionDialog(QDialog):
    SAVE = 1
    FAILURE = 2

    def __init__(self, parent=None, initial_note: str = "", initial_tags=(), available_tags=()):
        super().__init__(parent)
        self.setWindowTitle("Complete Focus Session")
        self.resize(640, 400)
        self.choice = 0

        root = QVBoxLayout(self)

        title = QLabel("Session Completion")
        title.setObjectName("SectionTitle")

        description = QLabel(
            "Optionally record what was completed and the next action."
        )
        description.setObjectName("Muted")

        self.tags = TagEditor(initial_tags, available_tags)
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText("Completion notes (optional)")
        self.note.setPlainText(initial_note.strip())

        info = QLabel(
            "Save to History records the focused time. "
            "Finish as Failure ends the session without creating a History entry."
        )
        info.setWordWrap(True)
        info.setObjectName("Muted")

        buttons = QDialogButtonBox()
        save = buttons.addButton(
            "Save to History",
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        failure = buttons.addButton(
            "Finish as Failure — Do Not Save",
            QDialogButtonBox.ButtonRole.DestructiveRole,
        )
        cancel = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)

        save.clicked.connect(self._save)
        failure.clicked.connect(self._failure)
        cancel.clicked.connect(self.reject)

        root.addWidget(title)
        root.addWidget(description)
        root.addWidget(self.note, 1)
        root.addWidget(QLabel("Session Tags"))
        root.addWidget(self.tags)
        root.addWidget(info)
        root.addWidget(buttons)

    def _save(self):
        self.choice = self.SAVE
        self.done(self.SAVE)

    def _failure(self):
        self.choice = self.FAILURE
        self.done(self.FAILURE)

    def text(self) -> str:
        return self.note.toPlainText().strip()


