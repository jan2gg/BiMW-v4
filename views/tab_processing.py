# views/tab_processing.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QDoubleSpinBox, QSizePolicy,
    QGridLayout, QFrame
)
from PyQt6.QtCore import pyqtSignal
import pyqtgraph as pg

# After the imports, before class TabProcessing:
LEGEND_COLORS = [
    "#ffffff",   # Ch 1 — white
    "#00bfff",   # Ch 2 — deep sky blue
    "#00ff7f",   # Ch 3 — spring green
    "#ff6347",   # Ch 4 — tomato red
    "#ffd700",   # Ch 5 — gold
    "#da70d6",   # Ch 6 — orchid purple
    "#40e0d0",   # Ch 7 — turquoise
]

class TabProcessing(QWidget):
    btn_load_experiment_clicked = pyqtSignal()
    btn_filter_clicked = pyqtSignal()
    btn_save_clicked = pyqtSignal()
    btn_exit_clicked = pyqtSignal()
    spb_filter_cutoff_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)

        # --- Left controls ---
        controls = QVBoxLayout()
        controls.setSpacing(8)

        load_group = QGroupBox("Experiment File")
        load_layout = QVBoxLayout(load_group)
        self.lbl_file_path = QLabel("No file loaded")
        self.lbl_file_path.setWordWrap(True)
        self.btn_load_experiment = QPushButton("Load Experiment (.DAT)")
        self.btn_load_experiment.clicked.connect(self.btn_load_experiment_clicked)
        load_layout.addWidget(self.lbl_file_path)
        load_layout.addWidget(self.btn_load_experiment)
        controls.addWidget(load_group)

        filter_group = QGroupBox("Phase Filter")
        filter_layout = QVBoxLayout(filter_group)
        self.spb_filter_cutoff = QDoubleSpinBox()
        self.spb_filter_cutoff.setDecimals(3)
        self.spb_filter_cutoff.setRange(0.001, 10.0)
        self.spb_filter_cutoff.setValue(0.05)
        self.spb_filter_cutoff.setSingleStep(0.001)
        self.spb_filter_cutoff.setSuffix(" Hz")
        self.spb_filter_cutoff.valueChanged.connect(self.spb_filter_cutoff_changed)
        self.btn_filter = QPushButton("Apply Filter")
        self.btn_filter.clicked.connect(self.btn_filter_clicked)
        self.btn_filter.setEnabled(False)
        filter_layout.addWidget(QLabel("Cutoff Frequency:"))
        filter_layout.addWidget(self.spb_filter_cutoff)
        filter_layout.addWidget(self.btn_filter)
        controls.addWidget(filter_group)

        # --- Channel legend ---
        legend_group = QGroupBox("Channels")
        legend_grid = QGridLayout(legend_group)
        legend_grid.setSpacing(4)
        legend_grid.setContentsMargins(6, 8, 6, 8)

        self.legend_labels: dict[int, QLabel] = {}

        for i in range(7):
            swatch = QFrame()
            swatch.setFixedSize(12, 12)
            swatch.setStyleSheet(
                f"background-color: {LEGEND_COLORS[i]}; border-radius: 2px;"
            )
            ch_label = QLabel(f"Ch {i + 1}")
            ch_label.setFixedWidth(32)
            val_label = QLabel("—")
            val_label.setStyleSheet(f"color: {LEGEND_COLORS[i]};")
            self.legend_labels[i] = val_label

            legend_grid.addWidget(swatch, i, 0)
            legend_grid.addWidget(ch_label, i, 1)
            legend_grid.addWidget(val_label, i, 2)

        legend_grid.setColumnStretch(2, 1)
        controls.addWidget(legend_group)

        self.btn_save = QPushButton("Save Processed Data")
        self.btn_save.clicked.connect(self.btn_save_clicked)
        self.btn_save.setEnabled(False)
        self.btn_exit = QPushButton("Exit")
        self.btn_exit.clicked.connect(self.btn_exit_clicked)
        controls.addWidget(self.btn_save)
        controls.addWidget(self.btn_exit)
        controls.addStretch()

        # --- Right chart ---
        chart_layout = QVBoxLayout()
        self.chart_phase = pg.PlotWidget(title="Loaded Phase Data")
        self.chart_phase.setLabel("left", "Phase", units="rad")
        self.chart_phase.setLabel("bottom", "Time", units="s")
        self.chart_phase.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        chart_layout.addWidget(self.chart_phase)

        main_layout.addLayout(controls, stretch=1)
        main_layout.addLayout(chart_layout, stretch=4)