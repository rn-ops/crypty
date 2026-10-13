from __future__ import annotations

import hashlib
from pathlib import Path    

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

"""
__init__                  Initialize page state and build the UI.
_build_ui                 Construct the recovery workspace and its widgets.
_label                    Create a styled label with an object name.
_get_selected_device      Retrieve the currently selected media device.
refresh_device_context    Update device information and reset page state.
_populate                 Populate the evidence table with scan results.
_filter                   Filter evidence by filename, type, and status.
_select_row               Display details for the selected evidence item.
_scan_evidence            Scan the selected device for filesystem evidence.
_recover_selected         Validate and recover the selected evidence item.
_update_action_state      Update action availability based on device and selection.
_load_hex                 Read and display raw bytes from the selected device.
_format_hex               Format bytes into hexadecimal and ASCII output.
"""

class RecoveryPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.results = []
        self.selected_result = None
        self._visible_results = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.breadcrumb = QLabel()
        self.breadcrumb.setObjectName("breadcrumb")
        layout.addWidget(self.breadcrumb)

        self.workspace = QSplitter(Qt.Horizontal)
        self.workspace.setChildrenCollapsible(False)
        self.workspace.setHandleWidth(6)

        main = QSplitter(Qt.Vertical)
        main.setChildrenCollapsible(False)
        main.setHandleWidth(6)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        header = QHBoxLayout()

        title_col = QVBoxLayout()
        title_col.addWidget(
            self._label("File System", "workspaceTitle")
        )
        title_col.addWidget(
            self._label(
                "Files and evidence traces discovered on the selected media.",
                "workspaceSubtitle",
            )
        )

        header.addLayout(title_col)
        header.addStretch(1)

        self.scan = QPushButton("Scan evidence")
        self.scan.setProperty("class", "primary")
        self.scan.clicked.connect(self._scan_evidence)
        header.addWidget(self.scan)

        top_layout.addLayout(header)

        controls = QHBoxLayout()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search files and evidence traces")
        self.search.textChanged.connect(self._filter)
        controls.addWidget(self.search, 1)

        self.filter = QComboBox()
        self.filter.addItems(
            ["All File Types", "Documents", "Images", "Media"]
        )
        self.filter.currentTextChanged.connect(self._filter)
        controls.addWidget(self.filter)

        self.status_filter = QComboBox()
        self.status_filter.addItems(
            ["All Status", "Existing", "Traced"]
        )
        self.status_filter.currentTextChanged.connect(self._filter)
        controls.addWidget(self.status_filter)

        top_layout.addLayout(controls)

        self.table = QTableWidget(0, 9)

        self.table.setHorizontalHeaderLabels(
            [
                "Status",
                "Name",
                "Type",
                "Size",
                "Modified",
                "Created",
                "Accessed",
                "Method",
                "Confidence",
            ]
        )

        self.table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.table.setSelectionMode(
            QAbstractItemView.SingleSelection
        )

        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            QHeaderView.Interactive
        )
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(45)

        self.table.itemSelectionChanged.connect(
            self._select_row
        )

        for column, width in enumerate(
            (
                75,    # Status
                260,   # Name
                70,    # Type
                95,    # Size
                150,   # Modified
                150,   # Created
                150,   # Accessed
                180,   # Method
                95,    # Confidence
            )
        ):
            self.table.setColumnWidth(column, width)

        top_layout.addWidget(self.table, 1)

        self.count = self._label("0 files", "muted")
        top_layout.addWidget(self.count)

        main.addWidget(top)

        hex_panel = QWidget()
        hex_layout = QVBoxLayout(hex_panel)
        hex_layout.setContentsMargins(0, 0, 0, 0)
        hex_layout.setSpacing(6)

        hex_controls = QHBoxLayout()

        hex_controls.addWidget(QLabel("Media offset"))

        self.hex_offset = QLineEdit("0x00000000")
        self.hex_offset.setMaximumWidth(150)
        hex_controls.addWidget(self.hex_offset)

        load = QPushButton("Load 10 KiB")
        load.clicked.connect(self._load_hex)
        hex_controls.addWidget(load)

        hex_controls.addStretch(1)
        hex_layout.addLayout(hex_controls)

        tabs = QTabWidget()

        self.hex_view = QTextEdit(
            "Load a read-only page from the selected media."
        )
        self.hex_view.setReadOnly(True)
        self.hex_view.setObjectName("hexView")
        tabs.addTab(self.hex_view, "Hex Viewer")

        text = QTextEdit(
            "Select an item to inspect its available text."
        )
        text.setReadOnly(True)
        tabs.addTab(text, "Text View")

        hex_layout.addWidget(tabs, 1)

        main.addWidget(hex_panel)
        main.setStretchFactor(0, 3)
        main.setStretchFactor(1, 2)
        main.setSizes([430, 300])

        self.workspace.addWidget(main)

        details = QFrame()
        details.setObjectName("inspectionPanel")

        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(12, 12, 12, 12)

        details_layout.addWidget(
            self._label("FILE INSPECTOR", "panelEyebrow")
        )

        self.preview = self._label(
            "Select an item",
            "previewName",
        )
        details_layout.addWidget(self.preview)

        self.info = QTextEdit()
        self.info.setReadOnly(True)
        self.info.setObjectName("detailText")
        # --- UI BLENDING OVERRIDES ---
        self.info.setFrameStyle(QFrame.NoFrame) # Wipes out blocky legacy text input borders
        self.info.setStyleSheet("""
            QTextEdit#detailText {
                background-color: transparent;
                padding: 4px 0px;
            }
        """)
        # -----------------------------
        
        details_layout.addWidget(self.info, 1)
        details_layout.addWidget(self.info, 1)

        details_layout.addWidget(
            self._label(
                "Hashes are shown for material that can be read without altering evidence.",
                "muted",
            )
        )

        details_layout.addSpacing(8)

        details_layout.addWidget(
            self._label(
                "Output directory",
                "panelEyebrow",
            )
        )

        self.output_directory = QLineEdit(
            str(Path.home() / "Desktop" / "Crypty_Saves" / "Recovered")
        )
        self.output_directory.setPlaceholderText(
            "~/Desktop/Crypty_Saves/Recovered/"
        )
        details_layout.addWidget(self.output_directory)

        details_layout.addSpacing(6)

        self.recover = QPushButton("Recover Selected")
        self.recover.setProperty("class", "primary")
        self.recover.setEnabled(False)
        self.recover.setToolTip("Select a traced file with recoverable data")
        self.recover.clicked.connect(self._recover_selected)
        details_layout.addWidget(self.recover)

        self.workspace.addWidget(details)

        self.workspace.setStretchFactor(0, 4)
        self.workspace.setStretchFactor(1, 1)
        self.workspace.setSizes([980, 260])

        layout.addWidget(self.workspace, 1)

        self.ready_state = QLabel("Ready")
        self.device_state = QLabel()
        self.event_state = QLabel("No active operation")

        self.refresh_device_context()

    @staticmethod
    def _label(text, name):
        widget = QLabel(text)
        widget.setObjectName(name)
        return widget

    def _get_selected_device(self):
        return self.main_window.device_manager.get_selected_device()

    def refresh_device_context(self):
        device = self._get_selected_device()

        self.breadcrumb.setText(
            f"Media / {device['name']} / "
            f"{device['filesystem']} / File System"
        )

        self.results = []
        self.selected_result = None
        self._populate(self.results)

        self.preview.setText("Select an item")
        self.info.clear()
        self._update_action_state()

        self.device_state.setText(
            f"{device['name']} | {device['capacity']} | "
            f"{device['filesystem']} | Read-only | SHA: pending"
        )

        self.event_state.setText(
            "Ready to scan evidence"
        )

    def _populate(self, rows):
        self._visible_results = list(rows)
        self.selected_result = None

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        for row, item in enumerate(rows):
            is_traced = bool(item.get("deleted", False))
            status = "Traced" if is_traced else "Existing"

            confidence = item.get("confidence")

            values = (
                status,
                item.get("path") or item.get("file", ""),
                item.get("type", ""),
                item.get("size", ""),
                item.get("modified", "Unknown"),
                item.get("created", "Unknown"),
                item.get("accessed", "Unknown"),
                item.get("method", "Filesystem"),
                (
                    f"{confidence}%"
                    if confidence is not None
                    else "—"
                ),
            )

            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))

                # Preserve the original result index in the row so
                # filtering/sorting never makes recovery target the
                # wrong evidence item.
                if column == 0:
                    cell.setData(Qt.UserRole, row)

                self.table.setItem(row, column, cell)

        self.count.setText(
            f"{len(rows):,} files"
        )

    def _filter(self, *_):
        query = self.search.text().strip().lower()
        file_type = self.filter.currentText()
        status_filter = self.status_filter.currentText()

        filtered = []

        for item in self.results:
            name = str(item.get("file", "")).lower()
            item_type = str(item.get("type", "")).upper()
            is_traced = bool(item.get("deleted", False))
            status = "Traced" if is_traced else "Existing"

            if query and query not in name:
                continue

            if status_filter != "All Status" and status != status_filter:
                continue

            if file_type != "All File Types":
                if file_type == "Documents":
                    allowed = {"PDF", "DOC", "DOCX", "TXT", "RTF", "XLS", "XLSX", "PPT", "PPTX"}
                elif file_type == "Images":
                    allowed = {"JPG", "JPEG", "PNG", "GIF", "BMP", "WEBP", "TIFF", "TIF"}
                else:
                    allowed = {"MP3", "WAV", "FLAC", "MP4", "AVI", "MKV", "MOV", "WMV"}

                if item_type not in allowed:
                    continue

            filtered.append(item)

        self._populate(filtered)

    def _select_row(self):
        print("========== ROW SELECTED ==========")

        row = self.table.currentRow()
        print("row:", row)
        print("visible results:", len(self._visible_results))

        if row < 0 or row >= len(self._visible_results):
            print("NO VALID ROW")
            self.selected_result = None
            self.recover.setEnabled(False)
            return

        item = self._visible_results[row]

        print("file:", item.get("file"))
        print("deleted:", item.get("deleted"))
        print("recoverable:", item.get("recoverable"))
        print("native_index:", item.get("native_index"))

        self.selected_result = item
        row = self.table.currentRow()

        if row < 0 or row >= len(self._visible_results):
            self.selected_result = None
            self.recover.setEnabled(False)
            return

        item = self._visible_results[row]
        self.selected_result = item

        is_traced = bool(item.get("deleted", False))

        self.preview.setText(
            item.get("file", "Unknown")
        )

                # Determine human-readable file metric constraints
        status_text = 'Traced' if is_traced else 'Existing'
        status_color = '#38bdf8' if is_traced else '#64748b'  # Bright blue accent highlight for newly recovered data
        
        # Build out clean structured HTML layout blocks
        html_content = f"""
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #cbd5e1; font-size: 12px; line-height: 1.5; }}
            .section {{ margin-bottom: 12px; }}
            .header {{ font-size: 9px; font-weight: bold; color: #64748b; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 4px; border-bottom: 1px solid #1e292b; padding-bottom: 2px; }}
            .row {{ display: table; width: 100%; margin-bottom: 2px; }}
            .label {{ display: table-cell; width: 100px; color: #64748b; font-weight: 500; }}
            .value {{ display: table-cell; color: #f1f5f9; }}
            .highlight {{ color: {status_color}; font-weight: bold; }}
            .hash {{ font-family: monospace; color: #94a3b8; font-size: 11px; word-break: break-all; }}
        </style>
        
        <div class="section">
            <div class="header">Recovery Status</div>
            <div class="row"><div class="label">Status</div><div class="value class="highlight"">{status_text}</div></div>
            <div class="row"><div class="label">Recoverable</div><div class="value">{item.get('recoverable', 0):,} B</div></div>
            <div class="row"><div class="label">Confidence</div><div class="value">{item.get('confidence', '—')}%</div></div>
        </div>

        <div class="section">
            <div class="header">Identity</div>
            <div class="row"><div class="label">Name</div><div class="value" style="font-weight: bold; color: #38bdf8;">{item.get('file', '')}</div></div>
            <div class="row"><div class="label">Path</div><div class="value">{item.get('path', '\\')}</div></div>
            <div class="row"><div class="label">Type</div><div class="value">{item.get('type', '')}</div></div>
            <div class="row"><div class="label">Size</div><div class="value">{item.get('size', 'Unknown')}</div></div>
        </div>

        <div class="section">
            <div class="header">Timeline</div>
            <div class="row"><div class="label">Modified</div><div class="value">{item.get('modified', 'Unknown')}</div></div>
            <div class="row"><div class="label">Created</div><div class="value">{item.get('created', 'Unknown')}</div></div>
            <div class="row"><div class="label">Accessed</div><div class="value">{item.get('accessed', 'Unknown')}</div></div>
        </div>

        <div class="section">
            <div class="header">Recovery Metadata</div>
            <div class="row"><div class="label">Method</div><div class="value">{item.get('method', 'Filesystem')}</div></div>
            <div class="row"><div class="label">Native Index</div><div class="value">{item.get('native_index', '—')}</div></div>
        </div>

        <div class="section">
            <div class="header">Integrity Check</div>
            <div class="row"><div class="label">SHA-256</div><div class="value class="hash"">Not calculated</div></div>
        </div>
        """
        
        # Apply the structured styling directly into the browser viewport frame
        self.info.setHtml(html_content)


        is_recoverable = (
            is_traced
            and item.get("recoverable", 0) > 0
        )

        self.ready_state.setText("Entry selected")

        if is_recoverable:
            self.event_state.setText(
                "Traced evidence available for recovery"
            )
        elif is_traced:
            self.event_state.setText(
                "Traced entry selected; no recoverable data is currently available"
            )
        else:
            self.event_state.setText(
                "Existing filesystem entry selected"
            )

        self._update_action_state()

    def _scan_evidence(self):
        self.ready_state.setText("Scanning")

        device = self._get_selected_device()

        filesystem = device.get("filesystem", "").upper()

        scanners = {
            "FAT32": self.main_window.backend.scan_fat32_deleted_files,
            "NTFS": self.main_window.backend.scan_ntfs_files,
            "EXFAT": self.main_window.backend.scan_exfat_deleted_files,
        }

        scanner = next(
            (
                function
                for name, function in scanners.items()
                if name in filesystem
            ),
            None,
        )

        if scanner is None:
            self.ready_state.setText("Unsupported")
            self.event_state.setText(
                f"Filesystem scanning does not support "
                f"{device['filesystem']} yet"
            )
            return

        self.event_state.setText(
            f"Scanning {device['filesystem']} filesystem evidence"
        )

        self.scan.setEnabled(False)
    
        try:
            self.results = scanner(device)

            self._populate(self.results)

            self.ready_state.setText("Ready")
            self.event_state.setText(
                f"Scan complete: "
                f"{len(self.results)} filesystem entries"
            )

        except Exception as error:
            self.ready_state.setText("Error")
            self.event_state.setText(
                f"Scan failed: {error}"
            )

        finally:
            self.scan.setEnabled(True)

    def _recover_selected(self):
        print("========== RECOVER CLICKED ==========")
        print("selected_result:", self.selected_result)

        if not self.selected_result:
            self.event_state.setText("No evidence item selected")
            return

        item = self.selected_result

        print("native_index:", item.get("native_index"))
        print("file:", item.get("file"))
        print("deleted:", item.get("deleted"))
        print("recoverable:", item.get("recoverable"))

        if not item.get("deleted", False):
            self.event_state.setText(
                "Only traced/deleted evidence can be recovered"
            )
            return

        index = item.get("native_index")

        if index is None:
            self.event_state.setText(
                "Recovery failed: native evidence index unavailable"
            )
            return

        output_directory = self.output_directory.text().strip()

        if not output_directory:
            self.event_state.setText(
                "Recovery failed: output directory is empty"
            )
            return

        output_directory = str(
            Path(output_directory).expanduser()
        )

        try:
            Path(output_directory).mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as error:
            self.event_state.setText(
                f"Cannot create output directory: {error}"
            )
            return

        filename = item.get("file", "recovered_file")

        destination = str(
            Path(output_directory) / filename
        )

        self.recover.setEnabled(False)
        self.scan.setEnabled(False)

        self.ready_state.setText("Recovering")
        self.event_state.setText(
            f"Recovering {filename}..."
        )

        try:
            bytes_recovered, complete = (
                self.main_window.backend.recover_ntfs_file(
                    index,
                    destination,
                )
            )

            if complete:
                self.ready_state.setText("Recovered")
                self.event_state.setText(
                    f"Recovery complete — "
                    f"{bytes_recovered:,} bytes written to "
                    f"{destination}"
                )

                self.info.append(
                    "\nRecovery result: COMPLETE"
                    f"\nRecovered bytes: {bytes_recovered:,}"
                    f"\nOutput: {destination}"
                )

            else:
                self.ready_state.setText("Partial")
                self.event_state.setText(
                    f"Partial recovery — "
                    f"{bytes_recovered:,} bytes written"
                )

                self.info.append(
                    "\nRecovery result: PARTIAL"
                    f"\nRecovered bytes: {bytes_recovered:,}"
                    f"\nOutput: {destination}"
                )

        except Exception as error:
            self.ready_state.setText("Error")
            self.event_state.setText(
                f"Recovery failed: {error}"
            )

            print("RECOVERY ERROR:", repr(error))

        finally:
            self._update_action_state()

    def _update_action_state(self):
        device = self._get_selected_device()

        has_device = device is not None

        filesystem = (
            str(device.get("filesystem", "")).upper()
            if device
            else ""
        )

        supported = any(
            name in filesystem
            for name in ("NTFS", "FAT32", "EXFAT")
        )

        self.scan.setEnabled(
            has_device and supported
        )

        item = self.selected_result

        can_recover = bool(
            has_device
            and item
            and item.get("deleted", False)
            and item.get("recoverable", 0) > 0
        )

        self.recover.setEnabled(can_recover)

        if not has_device:
            self.scan.setToolTip(
                "Select a media device first"
            )
        elif not supported:
            self.scan.setToolTip(
                f"Filesystem {device.get('filesystem', 'unknown')} "
                "is not supported"
            )
        else:
            self.scan.setToolTip(
                f"Scan {device['name']} for filesystem evidence"
            )

        if can_recover:
            self.recover.setToolTip(
                f"Recover {item.get('file', 'selected evidence')}"
            )
        elif item and not item.get("deleted", False):
            self.recover.setToolTip(
                "Select a traced/deleted evidence item"
            )
        elif item:
            self.recover.setToolTip(
                "Selected traced item has no recoverable data"
            )
        else:
            self.recover.setToolTip(
                "Select a traced file with recoverable data"
            )

    def _load_hex(self):
        try:
            offset = int(
                self.hex_offset.text().strip(),
                0,
            )

            data = (
                self.main_window.backend.read_media(
                    self._get_selected_device(),
                    offset,
                    10240,
                )
            )

        except (ValueError, OSError) as error:
            self.hex_view.setPlainText(
                f"Unable to read evidence: {error}"
            )
            return

        if not data:
            self.hex_view.setPlainText(
                "No bytes read. Raw-volume access may "
                "require an elevated read-only session."
            )
            return

        self.hex_view.setPlainText(
            self._format_hex(offset, data)
        )

        self.main_window.report_evidence_page(
            hashlib.sha256(data).hexdigest(),
            f"Loaded {len(data):,} bytes "
            f"at 0x{offset:08X}",
        )

    @staticmethod
    def _format_hex(offset, data):
        lines = []

        for i in range(0, len(data), 16):
            chunk = data[i:i + 16]

            addr = f"{offset + i:08X}\t"

            hex_bytes = " ".join(
                f"{b:02X}" for b in chunk
            ).ljust(47)

            ascii_chars = "".join(
                chr(b) if 32 <= b <= 126 else "."
                for b in chunk
            )

            lines.append(
                f"{addr}{hex_bytes}\t\t|{ascii_chars}|"
            )

        return "\n".join(lines)