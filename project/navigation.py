"""Application sidebar and page selection, without session or storage logic."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from . import APP_NAME, VERSION
from .theme import COLORS


class NavigationPanel(QFrame):
    page_requested = Signal(int, int)
    about_requested = Signal()

    ROUTES = (
        ("Focus Session", 0, -1),
        ("Focus Presets", 1, -1),
        ("Session History", 2, 0),
        ("Statistics", 2, 1),
        ("Resource Library", 3, -1),
        ("Application Settings", 4, -1),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(210)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 14)
        brand = QHBoxLayout()
        self.emblem = QLabel()
        self.emblem.setFixedSize(48, 48)
        self.emblem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emblem.setStyleSheet("background: transparent; border: none;")
        name = QLabel(APP_NAME)
        name.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {COLORS['cream']};")
        brand.addWidget(self.emblem)
        brand.addWidget(name)
        brand.addStretch()
        layout.addLayout(brand)
        layout.addSpacing(18)
        self.buttons = []
        for label, page, tab in self.ROUTES:
            button = QPushButton(label)
            button.setObjectName("Nav")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, page=page, tab=tab: self.page_requested.emit(page, tab)
            )
            layout.addWidget(button)
            self.buttons.append(button)
        layout.addStretch()
        self.version_label = QLabel(f"Version {VERSION}")
        self.version_label.setObjectName("Muted")
        layout.addWidget(self.version_label)
        about = QPushButton("About Cyndaquil")
        about.clicked.connect(self.about_requested)
        layout.addWidget(about)
        self.quit_button = QPushButton("Quit Cyndaquil")
        self.quit_button.setObjectName("Danger")
        layout.addWidget(self.quit_button)

    def set_current(self, page, history_view=0):
        for button, (_, target, tab) in zip(self.buttons, self.ROUTES):
            button.setChecked(target == page and (tab < 0 or tab == history_view))
