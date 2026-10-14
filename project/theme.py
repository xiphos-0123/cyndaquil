"""Shared palette and widget styling for the desktop application."""

from string import Template

# The five supplied palette colors, with darker blue surfaces for readable text.
COLORS = {
    "blue": "#3a637b",
    "slate": "#63849d",
    "bronze": "#c4a46b",
    "cream": "#ffefa5",
    "gold": "#ffde00",
    "background": "#182b36",
    "sidebar": "#213c4b",
    "surface": "#284858",
    "field": "#1e3542",
    "alternate": "#243f4f",
    "border": "#42687f",
    "muted": "#bed0dc",
    "text": "#f5f0e0",
}

CYNDAQUIL_QSS = Template("""
* {
    font-family: "Segoe UI";
    font-size: 13px;
    color: $text;
}
QWidget { background: transparent; }
QMainWindow, QDialog { background: $background; }
QScrollArea, QStackedWidget { background: $background; border: none; }
QLabel { background: transparent; border: none; padding: 0px; }
QFrame#Sidebar { background: $sidebar; border-right: 1px solid $border; }
QFrame#Card, QWidget#Card, QFrame#NotesCard {
    background: $surface;
    border: 1px solid $border;
    border-radius: 12px;
}
QFrame#EmberCard {
    background: $surface;
    border: 1px solid $bronze;
    border-radius: 12px;
}
QLabel#Title { font-size: 28px; font-weight: 700; color: $cream; }
QLabel#SectionTitle { font-size: 18px; font-weight: 600; color: $cream; }
QLabel#Muted { color: $muted; }
QLabel#Clock { font-size: 54px; font-weight: 800; color: $gold; }
QPushButton {
    background: $blue;
    border: 1px solid $slate;
    border-radius: 8px;
    padding: 9px 14px;
    color: $text;
}
QPushButton:hover { background: $slate; border-color: $slate; color: $background; }
QPushButton:pressed { background: $field; color: $cream; }
QPushButton:disabled { background: $alternate; color: $slate; border-color: $border; }
QPushButton#Primary {
    background: $gold;
    border: 1px solid $gold;
    color: $background;
    font-weight: 700;
}
QPushButton#Primary:hover { background: $cream; border-color: $cream; }
QPushButton#Primary:disabled { background: $alternate; color: $slate; border-color: $border; }
QPushButton#Warm { background: $bronze; border: 1px solid $bronze; color: $background; }
QPushButton#Danger { background: transparent; border: 1px solid $bronze; color: $cream; }
QPushButton#Danger:hover { background: $bronze; color: $background; }
QPushButton#Danger:disabled { background: transparent; color: $slate; border-color: $border; }
QPushButton#Nav {
    text-align: left;
    padding: 12px 14px;
    border: 1px solid transparent;
    background: transparent;
    color: $text;
}
QPushButton#Nav:hover { background: $surface; color: $cream; }
QPushButton#Nav:checked { background: $blue; border-color: $slate; color: $gold; }
QToolButton { background: $blue; border: 1px solid $slate; border-radius: 7px; padding: 6px; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QAbstractSpinBox {
    background: $field;
    border: 1px solid $border;
    border-radius: 7px;
    padding: 8px;
    selection-background-color: $blue;
    selection-color: $cream;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QAbstractSpinBox:focus {
    border: 1px solid $bronze;
}
QPlainTextEdit#NoteReader {
    background: transparent;
    border: none;
    padding: 0px;
    font-size: 14px;
}
QComboBox::drop-down { border: none; width: 24px; }
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
    width: 0px; height: 0px; border: none; background: transparent;
}
QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow { width: 0px; height: 0px; }
QTableWidget, QListView, QTreeWidget {
    background: $field;
    alternate-background-color: $alternate;
    border: 1px solid $border;
    gridline-color: $border;
    border-radius: 10px;
    selection-background-color: $blue;
    selection-color: $cream;
}
QTableWidget::item { padding: 8px; border: none; }
QTableWidget::item:selected { background: $blue; color: $cream; }
QHeaderView::section {
    background: $blue;
    color: $cream;
    padding: 12px 10px;
    border: none;
    border-bottom: 1px solid $slate;
    font-weight: 600;
}
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 0; }
QScrollBar::handle:vertical { background: $slate; min-height: 28px; border-radius: 5px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0 4px; }
QScrollBar::handle:horizontal { background: $slate; min-width: 28px; border-radius: 5px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QCheckBox { spacing: 10px; background: transparent; }
QCheckBox::indicator, QListView::indicator { width: 18px; height: 18px; }
QCheckBox::indicator:unchecked, QListView::indicator:unchecked {
    border: 1px solid $slate; border-radius: 4px; background: $field;
}
QCheckBox::indicator:checked, QListView::indicator:checked {
    border: 1px solid $bronze; border-radius: 4px; background: $bronze;
}
QProgressBar { background: $field; border: 1px solid $border; border-radius: 6px; min-height: 12px; text-align: center; }
QProgressBar::chunk { background: $bronze; border-radius: 5px; }
QSlider::groove:horizontal { height: 5px; border-radius: 2px; background: $border; }
QSlider::handle:horizontal { background: $bronze; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
QGroupBox { border: 1px solid $border; border-radius: 10px; margin-top: 18px; padding-top: 12px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: $cream; }
QTabBar::tab { background: $surface; border: 1px solid $border; padding: 10px 16px; }
QTabBar::tab:selected { background: $blue; color: $gold; }
QMenu { background: $surface; border: 1px solid $slate; padding: 8px; }
QMenu::item { background: transparent; padding: 9px 24px 9px 12px; border-radius: 5px; }
QMenu::item:selected { background: $blue; color: $cream; }
QToolTip { background: $sidebar; color: $cream; border: 1px solid $slate; padding: 6px; }
QSplitter::handle:vertical { background: transparent; }
QSplitter::handle:vertical:hover { background: $border; border-radius: 8px; }
QWidget#VisualCompanion { background: $field; border: 1px solid $slate; }
QWidget#ControlCompanion { background: $surface; border: 1px solid $bronze; border-radius: 9px; }
""").substitute(COLORS)
