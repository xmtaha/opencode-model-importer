STYLE = """
QWidget {
    background-color: #16181d;
    color: #d8dbe2;
}
QMainWindow, QGroupBox {
    background-color: #16181d;
}
QGroupBox {
    border: 1px solid #262a33;
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 12px 10px 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #8b93a5;
}
QLineEdit, QComboBox {
    background-color: #1e2129;
    border: 1px solid #2c313c;
    border-radius: 6px;
    padding: 7px 9px;
    selection-background-color: #3b6fd4;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #4a7dd6;
}
QLineEdit:disabled, QComboBox:disabled {
    background-color: #1a1d23;
    border-color: #23262e;
    color: #6d7485;
}
QComboBox QAbstractItemView {
    background-color: #1e2129;
    border: 1px solid #2c313c;
    selection-background-color: #2f4a7d;
    outline: 0;
}
QPushButton {
    background-color: #23262f;
    border: 1px solid #30353f;
    border-radius: 6px;
    padding: 7px 14px;
}
QPushButton:hover {
    background-color: #2b2f3a;
}
QPushButton:disabled {
    color: #5c6370;
    background-color: #1d2027;
}
QPushButton#primary {
    background-color: #3567c9;
    border: 1px solid #3d74dd;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#primary:hover {
    background-color: #3f75dc;
}
QPushButton#primary:disabled {
    background-color: #23324d;
    border-color: #23324d;
    color: #7b869b;
}
QPushButton#danger {
    color: #e0858e;
    border-color: #46292e;
    background-color: #241a1d;
}
QPushButton#danger:hover {
    background-color: #3a2429;
    border-color: #5c323a;
}
QPushButton#danger:disabled {
    color: #6a4a4f;
    background-color: #1d191b;
    border-color: #2a2124;
}
QLabel#title {
    font-size: 16px;
    font-weight: 600;
    color: #e8ebf1;
}
QTabWidget::pane {
    border: 1px solid #262a33;
    border-radius: 8px;
    background-color: #16181d;
}
QTabBar::tab {
    background: transparent;
    color: #8b93a5;
    padding: 8px 16px;
    margin-right: 4px;
    border: 0;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:hover {
    color: #c3c9d6;
}
QTabBar::tab:selected {
    color: #e8ebf1;
    border-bottom: 2px solid #4a7dd6;
}
QTableWidget {
    background-color: #1a1d24;
    alternate-background-color: #1d2028;
    border: 1px solid #262a33;
    border-radius: 6px;
    gridline-color: #262a33;
}
QHeaderView::section {
    background-color: #1e2129;
    color: #8b93a5;
    border: 0;
    border-bottom: 1px solid #262a33;
    padding: 6px 8px;
}
QTableWidget::item {
    padding: 4px 6px;
}
QCheckBox {
    color: #aeb4c2;
}
QProgressBar {
    background-color: #23262f;
    border: 0;
    border-radius: 4px;
    max-height: 8px;
}
QProgressBar::chunk {
    background-color: #4a7dd6;
    border-radius: 4px;
}
QLabel#hint {
    color: #6d7485;
    font-size: 11px;
}
QMessageBox {
    background-color: #1a1d24;
}
"""
