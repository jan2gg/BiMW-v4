# views/tab_intensity.py
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QLabel, QPushButton, QSizePolicy, QGridLayout, QFrame
)
from PyQt6.QtCore import pyqtSignal
import pyqtgraph as pg

CHANNEL_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2",
    "#59a14f", "#edc948", "#b07aa1",
]

NUM_INTENSITY_CHANNELS = 14  # kept for DAQ task creation (still reads 14 channels)
NUM_SUMS = 7


class TabIntensity(QWidget):
    """Intensity pre-calibration tab — displays sum of each UP+DOWN channel pair."""

    btn_start_clicked = pyqtSignal()
    btn_stop_clicked = pyqtSignal()
    btn_clear_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(8)

        # ── Left panel ────────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(8)

        ctrl_group = QGroupBox("Acquisition")
        ctrl_layout = QVBoxLayout(ctrl_group)

        self.btn_start = QPushButton("Start")
        self.btn_stop  = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_clear = QPushButton("Clear Plot")
        self.btn_exit  = QPushButton("Exit")

        for btn in (self.btn_start, self.btn_stop, self.btn_clear, self.btn_exit):
            ctrl_layout.addWidget(btn)

        self.btn_start.clicked.connect(self.btn_start_clicked)
        self.btn_stop.clicked.connect(self.btn_stop_clicked)
        self.btn_clear.clicked.connect(self.btn_clear_clicked)

        left.addWidget(ctrl_group)

        # Sum value readouts — one row per SR pair
        values_group = QGroupBox("Current Sum Values (mA)")
        values_grid = QGridLayout(values_group)
        values_grid.setSpacing(3)
        values_grid.setContentsMargins(6, 8, 6, 8)

        self.channel_value_labels: dict[int, QLabel] = {}
        for i in range(NUM_SUMS):
            swatch = QFrame()
            swatch.setFixedSize(10, 10)
            swatch.setStyleSheet(
                f"background-color: {CHANNEL_COLORS[i]}; border-radius: 2px;"
            )
            name_lbl = QLabel(f"SR {i + 1}")
            name_lbl.setFixedWidth(36)
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet(f"color: {CHANNEL_COLORS[i]};")
            self.channel_value_labels[i] = val_lbl
            values_grid.addWidget(swatch,   i, 0)
            values_grid.addWidget(name_lbl, i, 1)
            values_grid.addWidget(val_lbl,  i, 2)

        values_grid.setColumnStretch(2, 1)
        left.addWidget(values_group)

        self.lbl_status = QLabel("Stopped")
        self.lbl_status.setStyleSheet("color: gray;")
        left.addWidget(self.lbl_status)
        left.addStretch()

        # ── Right panel — chart ────────────────────────────────────────
        right = QVBoxLayout()
        self.chart = pg.PlotWidget(title="Intensity — SR Channel Sums (UP + DOWN)")
        self.chart.setLabel("left", "Intensity", units="mA")
        self.chart.setLabel("bottom", "Time", units="s")
        self.chart.addLegend(offset=(10, 10))
        self.chart.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right.addWidget(self.chart)

        main_layout.addLayout(left, stretch=1)
        main_layout.addLayout(right, stretch=4)