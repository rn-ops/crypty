from PySide6.QtCore import Qt

from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel


def create_workspace_header():

    header = QFrame()
    header.setFixedHeight(58)
    header.setObjectName("pageHeader")
    header.setStyleSheet(
        "QFrame#pageHeader { background: #11191d; border-bottom: 1px solid #2a383e; }"
    )

    layout = QHBoxLayout(header)
    layout.setContentsMargins(18, 5, 18, 5)
    layout.setSpacing(14)

    # Brand block
    brand_layout = QVBoxLayout()
    brand_layout.setSpacing(0)
    brand_layout.setContentsMargins(0, 0, 0, 0)

    brand = QLabel("◇  CRYPTY")
    brand.setStyleSheet(
        "color: #e8f4f1; font-size: 17px; font-weight: 700; "
        "letter-spacing: .14em;"
    )
    brand_layout.addWidget(brand)

    caption = QLabel("Digital forensics and sanitization workstation")
    caption.setStyleSheet(
        "color: #91a5a6; font-size: 9px; letter-spacing: .08em;"
    )
    brand_layout.addWidget(caption)

    layout.addLayout(brand_layout)
    layout.addStretch(1)

    case = QLabel("Case  CRYPTY-001")
    case.setStyleSheet(
        "background: #172228; border: 1px solid #314148; "
        "padding: 7px 10px; font-size: 11px;"
    )
    layout.addWidget(case)

    readonly = QLabel("Read-Only Mode")
    readonly.setStyleSheet(
        "color: #77ded5; background: #123034; "
        "border: 1px solid #245b5d; padding: 7px 10px; font-size: 11px;"
    )
    readonly.setAlignment(Qt.AlignCenter)
    layout.addWidget(readonly)

    return header