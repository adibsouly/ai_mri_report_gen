"""Qt stylesheet for the AI MRI Analyzer dark theme."""

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
