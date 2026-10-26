from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


class EvidencePage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 18, 24, 22)
        outer.setSpacing(14)
        title = QLabel("Evidence intelligence")
        title.setObjectName("workspaceTitle")
        subtitle = QLabel("Traceable analysis modules for a selected case. These sections remain empty until real evidence and analysis services are connected.")
        subtitle.setObjectName("workspaceSubtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(title)
        outer.addWidget(subtitle)

        case_row = QFrame()
        case_row.setStyleSheet("QFrame { background:#19191c; border:1px solid #3a3a40; border-radius:8px; }")
        row = QHBoxLayout(case_row)
        row.setContentsMargins(14, 10, 14, 10)
        self.case_context = QLabel("No case selected")
        self.case_context.setStyleSheet("font-size:12px;font-weight:700;border:none;")
        row.addWidget(QLabel("ACTIVE CASE"))
        row.addWidget(self.case_context, 1)
        self.open_cases = QPushButton("Open cases")
        self.open_cases.clicked.connect(lambda: self.main_window.show_page("cases"))
        row.addWidget(self.open_cases)
        outer.addWidget(case_row)

        grid = QGridLayout()
        grid.setSpacing(12)
        features = [
            ("01", "Cross-Artifact Timeline Reconstruction", "Normalize timestamps across filesystem metadata, logs, recovered files, and device artifacts. Expose time-zone offsets and uncertainty."),
            ("02", "Evidence Relationship Graph", "Explore links between artifacts, paths, devices, hashes, and events. Each relationship should lead back to its supporting evidence."),
            ("03", "Evidence-Backed Conclusions Engine", "Build reviewable findings with supporting artifact references, alternative explanations, confidence rationale, and analyst approval."),
            ("04", "Deleted-Data Intelligence", "Correlate deleted directory entries, carved fragments, filesystem remnants, and recovery confidence without overstating uncertain results."),
        ]
        for index, (number, name, description) in enumerate(features):
            card = QFrame()
            card.setObjectName("evidenceFeatureCard")
            card.setStyleSheet("QFrame#evidenceFeatureCard { background:#19191c; border:1px solid #3a3a40; border-radius:8px; } QFrame#evidenceFeatureCard:hover { border-color:#f0525b; background:#202024; }")
            card.setMinimumHeight(168)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            box = QVBoxLayout(card)
            box.setContentsMargins(16, 14, 16, 14)
            box.setSpacing(8)
            num = QLabel(number + "  /  INTELLIGENCE MODULE")
            num.setStyleSheet("font-size:10px;font-weight:800;letter-spacing:.1em;color:#f0525b;border:none;")
            heading = QLabel(name)
            heading.setWordWrap(True)
            heading.setStyleSheet("font-size:14px;font-weight:800;color:#f3f1ee;border:none;")
            copy = QLabel(description)
            copy.setWordWrap(True)
            copy.setStyleSheet("font-size:11px;color:#a7a5ac;border:none;")
            state = QLabel("AWAITING CASE EVIDENCE  ·  NOT CONNECTED")
            state.setStyleSheet("font-size:9px;font-weight:700;letter-spacing:.08em;color:#77757e;border:none;padding-top:4px;")
            box.addWidget(num)
            box.addWidget(heading)
            box.addWidget(copy, 1)
            box.addWidget(state)
            grid.addWidget(card, index // 2, index % 2)
        outer.addLayout(grid)

        artifact_panel = QFrame()
        artifact_panel.setStyleSheet("QFrame { background:#19191c; border:1px solid #3a3a40; border-radius:8px; }")
        artifact_layout = QVBoxLayout(artifact_panel)
        artifact_layout.setContentsMargins(16, 14, 16, 14)
        artifact_layout.setSpacing(8)
        artifacts_title = QLabel("Case artifacts")
        artifacts_title.setStyleSheet("font-size:13px;font-weight:800;border:none;")
        self.artifacts_state = QLabel("Select a case and attach media to begin building the evidence manifest.")
        self.artifacts_state.setWordWrap(True)
        self.artifacts_state.setStyleSheet("font-size:11px;color:#a7a5ac;border:none;")
        artifact_layout.addWidget(artifacts_title)
        artifact_layout.addWidget(self.artifacts_state)
        outer.addWidget(artifact_panel)
        outer.addStretch(1)

    def on_show(self):
        case = self.main_window.active_case
        if not case:
            self.case_context.setText("No case selected")
            self.artifacts_state.setText("Select a case and attach media to begin building the evidence manifest.")
            return
        self.case_context.setText(case.get("name", "Unnamed case"))
        devices = case.get("devices", [])
        if devices:
            self.artifacts_state.setText("Attached sources: " + ", ".join(d.get("name", "Unnamed media") for d in devices) + ". Evidence artifacts will appear after acquisition/indexing services are connected.")
        else:
            self.artifacts_state.setText("This case has no attached sources yet. Open Media Explorer, select a device, and attach it from the Cases page.")
