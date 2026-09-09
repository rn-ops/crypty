from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel


def create_workspace_header():
    header = QFrame()
    header.setFixedHeight(29)
    header.setObjectName("pageHeader")
    header.setStyleSheet(
        "QFrame#pageHeader { background: #141a1d; border-bottom: 1px solid #2b363d; }"
    )

    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(16, 4, 16, 4)
    header_layout.setSpacing(8)

    title = QLabel("CRYPTY")
    title.setStyleSheet("font-size: 15px; font-weight: 700; letter-spacing: 0.08em;")
    header_layout.addWidget(title)

    separator = QLabel("/")
    separator.setStyleSheet("color: #56615e; font-size: 11px;")
    header_layout.addWidget(separator)

    workspace = QLabel("Evidence handling workspace")
    workspace.setStyleSheet("color: #9aa5a1; font-size: 10px; letter-spacing: 0.04em;")
    header_layout.addWidget(workspace)

    context = QLabel("Case CRYPTY-001  ·  Investigator session")
    context.setStyleSheet("color: #9da9a4; font-size: 10px;")
    context.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    header_layout.addStretch(1)
    header_layout.addWidget(context)

    return header
