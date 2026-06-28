# views/dialogs.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class CalibrationDoneDialog(QDialog):
    """Modal notification shown when calibration completes automatically."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration Complete")
        self.setMinimumWidth(420)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # Icon + title row
        title = QLabel("✓  Calibration complete")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #4CAF50;")
        layout.addWidget(title)

        # Body text
        body = QLabel(
            "The laser has been stopped.\n\n"
            "Switch to the <b>Measure</b> tab and click <b>Start Laser</b> "
            "to begin acquiring phase data."
        )
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body_font = QFont()
        body_font.setPointSize(10)
        body.setFont(body_font)
        layout.addWidget(body)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_ok = QPushButton("OK — go to Measure tab")
        self.btn_ok.setMinimumWidth(180)
        self.btn_ok.setMinimumHeight(36)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_ok)
        layout.addLayout(btn_row)