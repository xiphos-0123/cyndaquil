CYNDAQUIL_QSS = """
* {
    font-family: "Segoe UI";
    font-size: 13px;
    color: #F7E9C8;
}
QWidget {
    background: transparent;
}
QMainWindow, QDialog {
    background: #0E1A24;
}
QScrollArea, QStackedWidget {
    background: #0E1A24;
    border: none;
}
QLabel {
    background: transparent;
    border: none;
    padding: 0px;
}
QCheckBox {
    background: transparent;
}
QFrame#Sidebar {
    background: #101F2C;
    border-right: 1px solid #284052;
}
QFrame#Card, QWidget#Card {
    background: #152838;
    border: 1px solid #2B455A;
    border-radius: 12px;
}
QFrame#EmberCard {
    background: #192A37;
    border: 1px solid #C65C31;
    border-radius: 13px;
}
QLabel#Title {
    font-size: 28px;
    font-weight: 800;
    color: #FFF0C9;
}
QLabel#SectionTitle {
    font-size: 18px;
    font-weight: 700;
    color: #FFE2A8;
}
QLabel#Muted {
    color: #AFC1CC;
}
QLabel#Clock {
    font-size: 54px;
    font-weight: 900;
    color: #FFD16A;
}
QPushButton {
    background: #20394B;
    border: 1px solid #35566D;
    border-radius: 8px;
    padding: 7px 11px;
    color: #F7E9C8;
}
QPushButton:hover {
    background: #294A60;
    border-color: #557A91;
}
QPushButton:pressed {
    background: #182D3D;
}
QPushButton:disabled {
    color: #70828C;
    background: #162733;
    border-color: #253B49;
}
QPushButton#Primary {
    background: #E66C35;
    border: 1px solid #F48A4E;
    color: #101820;
    font-weight: 800;
}
QPushButton#Primary:hover {
    background: #F27A3D;
}
QPushButton#Warm {
    background: #D79A37;
    border: 1px solid #F0BD58;
    color: #101820;
    font-weight: 700;
}
QPushButton#Danger {
    background: #5C2A2C;
    border: 1px solid #8B4140;
}
QPushButton#Nav {
    text-align: left;
    padding: 9px 12px;
    border: 1px solid transparent;
    background: transparent;
}
QPushButton#Nav:hover {
    background: #192E3E;
}
QPushButton#Nav:checked {
    background: #243F52;
    border-color: #3A6077;
    color: #FFD16A;
}
QToolButton {
    background: #20394B;
    border: 1px solid #35566D;
    border-radius: 7px;
    padding: 4px;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: #0A151D;
    border: 1px solid #345064;
    border-radius: 7px;
    padding: 6px;
    selection-background-color: #D86A36;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}

QAbstractSpinBox::up-button,
QAbstractSpinBox::down-button {
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}
QAbstractSpinBox::up-arrow,
QAbstractSpinBox::down-arrow {
    width: 0px;
    height: 0px;
}
QTableWidget, QListWidget, QTreeWidget {
    background: #0B1720;
    alternate-background-color: #10202B;
    border: 1px solid #2B455A;
    gridline-color: #233B4B;
    border-radius: 7px;
}
QHeaderView::section {
    background: #183042;
    color: #FFDCA0;
    padding: 7px;
    border: none;
    border-right: 1px solid #2E4B5E;
}
QScrollBar:vertical {
    background: #0E1A24;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #36586D;
    min-height: 24px;
    border-radius: 5px;
}
QScrollBar:horizontal {
    background: #0E1A24;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background: #36586D;
    min-width: 24px;
    border-radius: 5px;
}
QCheckBox {
    spacing: 9px;
    background: transparent;
}
QCheckBox::indicator, QListView::indicator {
    width: 18px;
    height: 18px;
}
QCheckBox::indicator:unchecked, QListView::indicator:unchecked {
    border: 2px solid #7B9AAC;
    border-radius: 4px;
    background: #0A151D;
}
QCheckBox::indicator:checked, QListView::indicator:checked {
    border: 2px solid #F29A4A;
    border-radius: 4px;
    background: #E66C35;
}
QProgressBar {
    background: #0A151D;
    border: 1px solid #345064;
    border-radius: 6px;
    text-align: center;
    min-height: 12px;
}
QProgressBar::chunk {
    background: #E66C35;
    border-radius: 5px;
}
QSlider::groove:horizontal {
    height: 5px;
    border-radius: 2px;
    background: #2B455A;
}
QSlider::handle:horizontal {
    background: #FFD16A;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QGroupBox {
    border: 1px solid #2B455A;
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #FFD16A;
}
QTabBar::tab {
    background: #183042;
    border: 1px solid #2B455A;
    padding: 7px 13px;
}
QTabBar::tab:selected {
    background: #E66C35;
    color: #111A21;
}

QMenu {
    background: #152838;
    border: 1px solid #35566D;
    padding: 5px;
}
QMenu::item {
    background: transparent;
    padding: 6px 22px 6px 10px;
    border-radius: 5px;
}
QMenu::item:selected {
    background: #294A60;
    color: #FFF0C9;
}

QToolTip {
    background: #182B39;
    color: #FFF1CF;
    border: 1px solid #557A91;
}


QSplitter::handle:vertical {
    background: #294A60;
    height: 5px;
    margin-left: 20px;
    margin-right: 20px;
    border-radius: 2px;
}
QSplitter::handle:vertical:hover {
    background: #E66C35;
}

QWidget#VisualCompanion {
    background: #070D12;
    border: 1px solid #35566D;
}
QWidget#ControlCompanion {
    background: #142633;
    border: 1px solid #C65C31;
    border-radius: 9px;
}
"""
