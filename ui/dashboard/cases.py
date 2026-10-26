from __future__ import annotations

from auth_client import AuthenticationError
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget,
)


class CasesPage(QWidget):
    """Case register and case context backed by the account service."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.cases: list[dict] = []
        self.active_case_id: str | None = None
        self.sync_error: str | None = None
        self._load_cases()
        self._build_ui()
        self._render_cases()

    def _load_cases(self):
        try:
            self.cases = self.main_window.auth_client.list_cases(self.main_window.session)
        except AuthenticationError as error:
            self.cases = []
            self.sync_error = str(error)

    def _panel(self, title: str, subtitle: str = ""):
        frame = QFrame()
        frame.setObjectName("casePanel")
        frame.setStyleSheet("QFrame#casePanel { background:#19191c; border:1px solid #3a3a40; border-radius:8px; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)
        heading = QLabel(title)
        heading.setStyleSheet("font-size:13px;font-weight:800;color:#f3f1ee;border:none;")
        layout.addWidget(heading)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setWordWrap(True)
            sub.setStyleSheet("font-size:11px;color:#a7a5ac;border:none;")
            layout.addWidget(sub)
        return frame, layout

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 18, 24, 22)
        outer.setSpacing(14)
        heading = QLabel("Cases")
        heading.setObjectName("workspaceTitle")
        sub = QLabel("Create a job or investigation first, then associate its media, operations, and evidence.")
        sub.setObjectName("workspaceSubtitle")
        sub.setWordWrap(True)
        outer.addWidget(heading)
        outer.addWidget(sub)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        form_panel, form_layout = self._panel("Create a case", "A case groups the work; each drive remains an individually identified evidence source.")
        form = QFormLayout()
        form.setSpacing(10)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Laptop refurbishment batch")
        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.addItems(["Laptop refurbishment", "Data recovery", "Forensic investigation", "Secure sanitization", "Incident response", "Asset disposition"])
        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText("Customer / work-order reference (optional)")
        self.operator_input = QLineEdit()
        self.operator_input.setText(getattr(self.main_window.session, "username", ""))
        self.scope_input = QTextEdit()
        self.scope_input.setPlaceholderText("Scope, authorization, and notes…")
        self.scope_input.setMinimumHeight(78)
        form.addRow("Case name *", self.name_input)
        form.addRow("Work category", self.category_input)
        form.addRow("Work-order ref.", self.reference_input)
        form.addRow("Operator", self.operator_input)
        form.addRow("Scope / notes", self.scope_input)
        form_layout.addLayout(form)
        create = QPushButton("Create case workspace")
        create.setProperty("class", "primary")
        create.clicked.connect(self._create_case)
        form_layout.addWidget(create)
        columns.addWidget(form_panel, 3)

        active_panel, active_layout = self._panel("Active case", "Current case context for the workbench.")
        self.active_title = QLabel("No case selected")
        self.active_title.setWordWrap(True)
        self.active_title.setStyleSheet("font-size:18px;font-weight:800;color:#f3f1ee;border:none;")
        self.active_meta = QLabel("Create or select a case to begin.")
        self.active_meta.setWordWrap(True)
        self.active_meta.setStyleSheet("font-size:12px;color:#a7a5ac;border:none;")
        self.active_scope = QLabel("")
        self.active_scope.setWordWrap(True)
        self.active_scope.setStyleSheet("font-size:12px;color:#d4d1d6;border:none;")
        self.attach_button = QPushButton("Attach selected media to case")
        self.attach_button.setProperty("class", "primary")
        self.attach_button.clicked.connect(self._attach_selected_device)
        self.attach_button.setEnabled(False)
        active_layout.addWidget(self.active_title)
        active_layout.addWidget(self.active_meta)
        active_layout.addWidget(self.active_scope)
        active_layout.addSpacing(8)
        active_layout.addWidget(self.attach_button)
        active_layout.addStretch(1)
        columns.addWidget(active_panel, 2)
        outer.addLayout(columns)

        register_panel, register_layout = self._panel("Case register", "Cases and attached-device fingerprints are stored in the Crypty account database.")
        self.sync_status = QLabel("")
        self.sync_status.setWordWrap(True)
        self.sync_status.setStyleSheet("font-size:11px;color:#e58b83;border:none;")
        register_layout.addWidget(self.sync_status)
        refresh = QPushButton("Refresh case register")
        refresh.clicked.connect(self._refresh_cases)
        register_layout.addWidget(refresh)
        self.case_list_layout = QVBoxLayout()
        self.case_list_layout.setSpacing(6)
        register_layout.addLayout(self.case_list_layout)
        outer.addWidget(register_panel, 1)
        if self.sync_error:
            self.sync_status.setText("Case service unavailable: " + self.sync_error)

    def _refresh_cases(self):
        try:
            self.cases = self.main_window.auth_client.list_cases(self.main_window.session)
            self.sync_error = None
            self.sync_status.setText("Cases synchronized with the account database.")
            if self.active_case_id not in {case["id"] for case in self.cases}:
                self.active_case_id = None
            self._render_cases()
            self._sync_context()
        except AuthenticationError as error:
            self.sync_error = str(error)
            self.sync_status.setText("Case service unavailable: " + self.sync_error)

    def _create_case(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.information(self, "Case name required", "Enter a case or job name first.")
            self.name_input.setFocus()
            return
        case_data = {
            "name": name,
            "category": self.category_input.currentText().strip(),
            "reference": self.reference_input.text().strip(),
            "operator": self.operator_input.text().strip(),
            "scope": self.scope_input.toPlainText().strip(),
        }
        try:
            case = self.main_window.auth_client.create_case(
                self.main_window.session, case_data
            )
        except AuthenticationError as error:
            QMessageBox.critical(self, "Case creation failed", str(error))
            return
        self.cases.insert(0, case)
        self.active_case_id = case["id"]
        self.sync_error = None
        self.sync_status.setText("Case saved to the account database.")
        self.name_input.clear()
        self.reference_input.clear()
        self.scope_input.clear()
        self._render_cases()
        self._sync_context()
        self.main_window.set_active_case(case)

    def _render_cases(self):
        while self.case_list_layout.count():
            item = self.case_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not self.cases:
            empty = QLabel("No cases yet. Create one above to establish a case context.")
            empty.setWordWrap(True)
            empty.setStyleSheet("color:#a7a5ac;padding:12px;border:none;")
            self.case_list_layout.addWidget(empty)
            return
        for case in self.cases:
            row = QFrame()
            row.setStyleSheet("QFrame { background:#202024; border:1px solid #3a3a40; border-radius:6px; }")
            line = QHBoxLayout(row)
            line.setContentsMargins(12, 9, 12, 9)
            info = QVBoxLayout()
            name = QLabel(case.get("name", "Unnamed case"))
            name.setStyleSheet("font-weight:800;font-size:12px;border:none;")
            details = QLabel(" · ".join(x for x in [case.get("category", ""), case.get("reference", ""), f'{len(case.get("devices", []))} source(s)'] if x))
            details.setStyleSheet("font-size:10px;color:#a7a5ac;border:none;")
            details.setWordWrap(True)
            info.addWidget(name)
            info.addWidget(details)
            line.addLayout(info, 1)
            choose = QPushButton("Active" if case.get("id") == self.active_case_id else "Open case")
            choose.clicked.connect(lambda checked=False, cid=case["id"]: self._select_case(cid))
            line.addWidget(choose)
            self.case_list_layout.addWidget(row)

    def _select_case(self, case_id):
        self.active_case_id = case_id
        self._render_cases()
        self._sync_context()
        case = self.active_case()
        self.main_window.set_active_case(case)

    def active_case(self):
        return next((case for case in self.cases if case.get("id") == self.active_case_id), None)

    def _sync_context(self):
        case = self.active_case()
        if not case:
            self.active_title.setText("No case selected")
            self.active_meta.setText("Create or select a case to begin.")
            self.active_scope.setText("")
            self.attach_button.setEnabled(False)
            return
        self.active_title.setText(case.get("name", "Unnamed case"))
        self.active_meta.setText(" · ".join(x for x in [case.get("category", ""), case.get("reference", "No work-order reference"), "Operator: " + (case.get("operator") or "Unassigned"), f'{len(case.get("devices", []))} attached source(s)'] if x))
        self.active_scope.setText(case.get("scope", "No scope notes added."))
        self.attach_button.setEnabled(bool(self.main_window.active_device))

    def _attach_selected_device(self):
        case = self.active_case()
        device = self.main_window.active_device
        if not case or not device:
            QMessageBox.information(self, "Select a case and source", "Create/select a case, then choose a device in Media Explorer.")
            return
        try:
            identity = self.main_window.auth_client.device_fingerprint(device)
        except ValueError as error:
            QMessageBox.warning(self, "Missing source identity", str(error))
            return
        existing = {item.get("identity") for item in case.get("devices", [])}
        if identity not in existing:
            try:
                updated = self.main_window.auth_client.attach_device(
                    self.main_window.session, case["id"], device, identity
                )
            except (AuthenticationError, ValueError) as error:
                QMessageBox.critical(self, "Device attachment failed", str(error))
                return
            self.cases = [
                updated if current["id"] == updated["id"] else current
                for current in self.cases
            ]
            self._render_cases()
            self._sync_context()
            self.main_window.set_active_case(updated)
            QMessageBox.information(self, "Source attached", f"{device.get('name', 'Media')} was attached to {case['name']}.")
        else:
            QMessageBox.information(self, "Already attached", "This source is already attached to the active case.")

    def on_show(self):
        self._refresh_cases()
        if self.active_case_id is None and self.cases:
            self.active_case_id = self.cases[0]["id"]
            self._render_cases()
            self._sync_context()
            self.main_window.set_active_case(self.active_case())
