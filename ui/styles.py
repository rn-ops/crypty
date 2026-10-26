WINDOW_BG = "#111113"
PANEL_BG = "#19191d"
PANEL_ALT = "#202025"
SURFACE = "#26262c"
SURFACE_LIGHT = "#303038"
BORDER = "#414149"
TEXT = "#f5f5f7"
TEXT_MUTED = "#b4b4bf"
ACCENT = "#e04b54"
ACCENT_SOFT = "#ff777e"
TERRACOTTA = "#c93440"
SUCCESS = "#8bd5a4"
WARNING = "#f1c777"
DANGER = "#ff6b75"

APP_STYLESHEET = f"""
QMainWindow {{
    background: {WINDOW_BG};
    color: {TEXT};
}}

QWidget {{
    background: transparent;
    color: {TEXT};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 12px;
}}

QLabel {{
    color: {TEXT};
}}

QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    color: {TEXT};
    padding: 8px 14px;
    min-height: 34px;
    border-radius: 3px;
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

QLabel#breadcrumb {{
    color: #bac8c6;
    background: #141b1f;
    border: 1px solid #253238;
    padding: 8px 12px;
    font-size: 12px;
}}

QLabel#workspaceTitle {{ font-size: 23px; font-weight: 600; color: #f1f5f3; }}
QLabel#workspaceSubtitle, QLabel#muted {{ color: #95a5a8; font-size: 12px; }}
QLabel#panelEyebrow {{ color: #9aabaa; font-size: 10px; font-weight: 600; letter-spacing: 0.12em; }}
QLabel#previewName {{ font-size: 13px; font-weight: 600; }}
QLabel#statusLine {{ color: #ff777e; font-size: 11px; }}
QLabel#metadataKey {{ color: #97a5a7; font-size: 11px; }}
QLabel#metadataValue {{ color: #e3ebea; font-size: 11px; }}
QLabel#paperPreview {{
    background: #e9eceb;
    color: #20282a;
    border: 1px solid #536063;
    padding: 26px 12px;
    font-size: 11px;
    line-height: 1.7;
}}

QFrame#inspectionPanel {{ background: #12191d; border: 1px solid #2b393e; }}
QToolButton#toolbarButton {{
    background: #172126;
    border: 1px solid #314148;
    color: #b9cccc;
    min-width: 30px;
    min-height: 30px;
}}
QLineEdit {{
    background: #161f24;
    color: #e9f0ee;
    border: 1px solid #34434a;
    padding: 7px 10px;
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QTableWidget {{
    background: #121a1e;
    alternate-background-color: #172126;
    color: #dce7e5;
    border: 1px solid #2c3a40;
    gridline-color: #26343a;
}}
QTableWidget::item {{ padding: 7px 8px; border-bottom: 1px solid #223036; }}
QTableWidget::item:selected {{ background: #19353d; color: #f2ffff; }}
QTabWidget::pane {{ border: 1px solid #2c3a40; background: #11191d; }}
QTabBar::tab {{ background: #151f24; color: #aebdbc; border: none; padding: 8px 13px; }}
QTabBar::tab:selected {{ color: #ff777e; border-bottom: 2px solid #e04b54; background: #17242a; }}
QTextEdit#hexView {{
    background: #10181c;
    border: none;
    color: #b7cac8;
    font-family: Consolas, 'Cascadia Mono', monospace;
    font-size: 11px;
    padding: 10px;
}}

QPushButton#headerNav {{
    background: transparent;
    border: none;
    color: #aebdbc;
    min-height: 30px;
    padding: 5px 9px;
    font-size: 11px;
}}
QPushButton#headerNav:hover {{ color: #e8f4f1; background: #172329; }}
QPushButton#headerNav[active="true"] {{ color: #4ed8d0; border-bottom: 2px solid #4ed8d0; }}
QSplitter#mediaSidebar {{ background: #141b1f; border-right: 1px solid #2b393e; }}
QTreeWidget#mediaTree {{ background: transparent; border: none; color: #d7e3e0; }}
QTreeWidget#mediaTree::item {{ padding: 5px 3px; }}
QTreeWidget#mediaTree::item:selected {{ background: #19353d; color: #effffd; }}
QTextEdit#detailText {{ background: #10181c; border: 1px solid #2c3a40; color: #c7d6d3; font-size: 11px; }}
QFrame#globalFooter {{ background: #10171b; border-top: 1px solid #2b393e; }}
QLabel#globalFooterText {{ color: #a9bbb9; font-size: 10px; }}
QFrame#recoveryFooter {{ background: #11191d; border: 1px solid #2b393e; }}
QFrame#recoveryFooter QLabel {{ color: #9eb4b3; font-size: 11px; }}
"""
