"""Qt stylesheets for DecodeMRI."""

LIGHT_THEME = """
QMainWindow, QWidget {
    background-color: #f5f7fa;
    color: #18212b;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI";
    font-size: 13px;
}
QMenuBar, QMenu, QToolBar, QStatusBar {
    background-color: #ffffff;
    color: #18212b;
}
QDockWidget::title {
    background-color: #e9eef5;
    padding: 8px;
    font-weight: 600;
}
QTreeWidget, QTableWidget, QListWidget, QTextEdit, QLineEdit {
    background-color: #ffffff;
    color: #18212b;
    border: 1px solid #c8d1dc;
    selection-background-color: #3478f6;
    selection-color: #ffffff;
    gridline-color: #d8dee7;
}
QGraphicsView {
    background-color: #11161d;
    border: 1px solid #c8d1dc;
}
QPushButton, QToolButton {
    background-color: #ffffff;
    border: 1px solid #b8c2cf;
    border-radius: 4px;
    padding: 6px 10px;
}
QPushButton:hover, QToolButton:hover {
    background-color: #e8eef7;
}
QPushButton:disabled, QToolButton:disabled {
    color: #8b95a1;
    background-color: #edf0f4;
}
QHeaderView::section {
    background-color: #e9eef5;
    color: #18212b;
    border: 0;
    padding: 6px;
}
QProgressBar {
    background-color: #dfe5ec;
    border: 1px solid #c8d1dc;
    border-radius: 4px;
    min-height: 8px;
}
QProgressBar::chunk {
    background-color: #3478f6;
    border-radius: 3px;
}
QSplitter::handle {
    background-color: #c8d1dc;
}
"""

DARK_THEME = """
QMainWindow, QWidget {
    background-color: #12161c;
    color: #e6edf3;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI";
    font-size: 13px;
}
QMenuBar, QMenu, QToolBar, QStatusBar {
    background-color: #171c23;
    color: #e6edf3;
}
QDockWidget {
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}
QDockWidget::title {
    background-color: #1d242d;
    padding: 8px;
    font-weight: 600;
}
QTreeWidget, QTableWidget, QListWidget {
    background-color: #0f1318;
    border: 1px solid #2f3a46;
    selection-background-color: #2563eb;
    gridline-color: #2f3a46;
}
QGraphicsView {
    background-color: #05070a;
    border: 1px solid #2f3a46;
}
QPushButton, QToolButton {
    background-color: #232b35;
    border: 1px solid #3a4654;
    border-radius: 4px;
    padding: 6px 10px;
}
QPushButton:hover, QToolButton:hover {
    background-color: #2d3744;
}
QHeaderView::section {
    background-color: #1d242d;
    color: #e6edf3;
    border: 0;
    padding: 6px;
}
QSplitter::handle {
    background-color: #2f3a46;
}
"""
