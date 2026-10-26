from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

class SettingsPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(12)
        title = QLabel("Settings")
        title.setObjectName("workspaceTitle")
        subtitle = QLabel("Workbench preferences and integration status.")
        subtitle.setObjectName("workspaceSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        for heading, detail in [
            ("Native device & filesystem engine", "Device discovery, filesystem detection, and recovery integration."),
            ("Sanitization engine", "Policy, execution, and verification integration."),
            ("Evidence analysis service", "Timeline, graph, conclusions, and deleted-data intelligence."),
            ("Audit & reporting service", "Operation records, chain of custody, and report generation."),
        ]:
            panel = QFrame()
            panel.setStyleSheet("QFrame { background:#19191c; border:1px solid #3a3a40; border-radius:8px; }")
            box = QVBoxLayout(panel)
            box.setContentsMargins(16, 13, 16, 13)
            title_label = QLabel(heading)
            title_label.setStyleSheet("font-size:13px;font-weight:800;border:none;")
            detail_label = QLabel(detail)
            detail_label.setWordWrap(True)
            detail_label.setStyleSheet("font-size:11px;color:#a7a5ac;border:none;")
            status = QLabel("INTEGRATION STATUS · DEPENDS ON BACKEND")
            status.setStyleSheet("font-size:9px;font-weight:700;letter-spacing:.08em;color:#e8bd75;border:none;")
            box.addWidget(title_label)
            box.addWidget(detail_label)
            box.addWidget(status)
            layout.addWidget(panel)
        layout.addStretch(1)
