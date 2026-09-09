WINDOW_BG = "#121517"
PANEL_BG = "#171c1f"
PANEL_ALT = "#1a2025"
SURFACE = "#1d2429"
SURFACE_LIGHT = "#222b31"
BORDER = "#2b363d"
TEXT = "#edf1ef"
TEXT_MUTED = "#9aa5a1"
ACCENT = "#829b92"
ACCENT_SOFT = "#9db2a9"
TERRACOTTA = "#b66a5d"
SUCCESS = "#7db88a"
WARNING = "#d5b36a"
DANGER = "#d77c69"

APP_STYLESHEET = f"""
QMainWindow {{
    background: {WINDOW_BG};
    color: {TEXT};
}}

QWidget {{
    background: transparent;
    color: {TEXT};
    font-family: 'Segoe UI';
}}

QLabel {{
    color: {TEXT};
}}

QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    color: {TEXT};
    padding: 7px 12px;
    min-height: 30px;
    font-weight: 600;
}}

QPushButton:hover {{
    border-color: {ACCENT};
}}

QPushButton:pressed {{
    background: {PANEL_ALT};
}}

QPushButton.primary {{
    background: #829b92;
    color: #18201f;
    border: 1px solid {ACCENT};
}}

QPushButton.danger {{
    background: {TERRACOTTA};
    color: #fff;
    border: 1px solid {TERRACOTTA};
}}

QPushButton.secondary {{
    background: {SURFACE_LIGHT};
    color: {TEXT};
}}

QFrame.section {{
    background: {PANEL_BG};
    border: 1px solid {BORDER};
}}

QFrame.panel {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
}}

QHeaderView::section {{
    background: {SURFACE};
    color: {TEXT};
    padding: 8px;
    border: 1px solid {BORDER};
    font-weight: 600;
}}

QTableView {{
    background: {PANEL_ALT};
    color: {TEXT};
    alternate-background-color: {SURFACE};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
}}

QTableView::item {{
    padding: 8px 10px;
    border: none;
}}

QTreeWidget, QListWidget, QComboBox, QLineEdit, QTextEdit {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
}}

QComboBox {{
    padding: 6px 10px;
}}

QProgressBar {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    text-align: center;
    color: {TEXT};
    min-height: 18px;
}}

QProgressBar::chunk {{
    background: {ACCENT};
}}

QScrollBar:vertical {{
    background: {PANEL_BG};
    width: 10px;
}}

QScrollBar::handle:vertical {{
    background: {SURFACE_LIGHT};
    border-radius: 4px;
}}

QLabel.muted {{
    color: {TEXT_MUTED};
}}

QLabel.accent {{
    color: {ACCENT_SOFT};
}}

QLabel.good {{
    color: {SUCCESS};
}}

QLabel.warn {{
    color: {WARNING};
}}

QLabel.danger {{
    color: {DANGER};
}}

QLabel.heading {{
    font-size: 19px;
    font-weight: 600;
}}

QLabel.subheading {{
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {TEXT_MUTED};
}}

QLabel.title {{
    font-size: 15px;
    font-weight: 600;
}}

QLabel.code {{
    font-family: 'Consolas';
}}

QToolTip {{
    background: {PANEL_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
}}
"""
