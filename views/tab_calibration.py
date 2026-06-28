# views/tab_calibration.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox,
    QComboBox, QLineEdit, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal
import pyqtgraph as pg

SR_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2",
    "#59a14f", "#edc948", "#b07aa1",
]
NUM_SR_CHANNELS = 7


class TabCalibration(QWidget):
    btn_start_laser_clicked = pyqtSignal()
    btn_stop_clicked = pyqtSignal()
    btn_clear_clicked = pyqtSignal()
    btn_calibration_clicked = pyqtSignal()
    btn_exit_clicked = pyqtSignal()
    btn_park_clicked = pyqtSignal()
    cmb_device_changed = pyqtSignal(int)
    cmb_signal_modulation_changed = pyqtSignal(int)
    cmb_current_range_changed = pyqtSignal(int)
    cmb_sr_selection_changed = pyqtSignal(int)
    spb_freq_changed = pyqtSignal(int)
    spb_laser_current_set_changed = pyqtSignal(float)
    spb_calibration_time_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)

        # ── Left control panel ────────────────────────────────────────
        controls = QVBoxLayout()
        controls.setSpacing(6)

        dev_group = QGroupBox("Device")
        dev_layout = QVBoxLayout(dev_group)
        self.cmb_device = QComboBox()
        self.cmb_device.currentIndexChanged.connect(self.cmb_device_changed)
        dev_layout.addWidget(self.cmb_device)
        controls.addWidget(dev_group)

        sig_group = QGroupBox("Signal Parameters")
        sig_layout = QVBoxLayout(sig_group)
        sig_layout.addWidget(QLabel("Modulation:"))
        self.cmb_signal_modulation = QComboBox()
        self.cmb_signal_modulation.currentIndexChanged.connect(self.cmb_signal_modulation_changed)
        sig_layout.addWidget(self.cmb_signal_modulation)
        sig_layout.addWidget(QLabel("Frequency:"))
        self.spb_freq = QSpinBox()
        self.spb_freq.setRange(10, 1000)
        self.spb_freq.setValue(10)
        self.spb_freq.setSuffix(" Hz")
        self.spb_freq.valueChanged.connect(self.spb_freq_changed)
        sig_layout.addWidget(self.spb_freq)
        sig_layout.addWidget(QLabel("Laser Current Set:"))
        self.spb_laser_current_set = QDoubleSpinBox()
        self.spb_laser_current_set.setRange(0, 500)
        self.spb_laser_current_set.setValue(150)
        self.spb_laser_current_set.setSuffix(" mA")
        self.spb_laser_current_set.valueChanged.connect(self.spb_laser_current_set_changed)
        sig_layout.addWidget(self.spb_laser_current_set)
        sig_layout.addWidget(QLabel("Current Range:"))
        self.cmb_current_range = QComboBox()
        self.cmb_current_range.currentIndexChanged.connect(self.cmb_current_range_changed)
        sig_layout.addWidget(self.cmb_current_range)
        controls.addWidget(sig_group)

        cal_group = QGroupBox("Calibration")
        cal_layout = QVBoxLayout(cal_group)
        cal_layout.setContentsMargins(4, 4, 4, 4)
        cal_layout.setSpacing(2)
        cal_layout.addWidget(QLabel("Calibration Time:"))
        self.spb_calibration_time = QSpinBox()
        self.spb_calibration_time.setRange(5, 300)
        self.spb_calibration_time.setValue(30)
        self.spb_calibration_time.setSuffix(" s")
        self.spb_calibration_time.valueChanged.connect(self.spb_calibration_time_changed)
        cal_layout.addWidget(self.spb_calibration_time)
        controls.addWidget(cal_group)

        # Center SR info (like old controller)
        center_sr_group = QGroupBox("Filter / SR Info")
        center_sr_layout = QVBoxLayout(center_sr_group)
        center_sr_layout.addWidget(QLabel("Center SR Signal (ch 3):"))
        self.edt_center_sr_signal = QLineEdit("---")
        self.edt_center_sr_signal.setReadOnly(True)
        center_sr_layout.addWidget(self.edt_center_sr_signal)
        controls.addWidget(center_sr_group)

        # SR selection dropdown
        sr_group = QGroupBox("SR Selection")
        sr_layout = QVBoxLayout(sr_group)
        sr_layout.setContentsMargins(4, 4, 4, 4)
        sr_layout.setSpacing(2)
        self.cmb_sr_selection = QComboBox()
        self.cmb_sr_selection.addItem("All SRs")
        for i in range(NUM_SR_CHANNELS):
            self.cmb_sr_selection.addItem(f"SR {i + 1}")
        self.cmb_sr_selection.currentIndexChanged.connect(self.cmb_sr_selection_changed)
        sr_layout.addWidget(self.cmb_sr_selection)
        controls.addWidget(sr_group)

        couple_group = QGroupBox("Coupling")
        couple_layout = QVBoxLayout(couple_group)
        couple_layout.setContentsMargins(4, 4, 4, 4)
        couple_layout.setSpacing(2)
        self.lbl_iup = QLabel("I UP: ---")
        self.lbl_idown = QLabel("I DOWN: ---")
        self.lbl_iup7 = QLabel("I UP 7: ---")
        self.lbl_idown7 = QLabel("I DOWN 7: ---")
        for lbl in [self.lbl_iup, self.lbl_idown, self.lbl_iup7, self.lbl_idown7]:
            couple_layout.addWidget(lbl)
        controls.addWidget(couple_group)

        self.btn_start_laser = QPushButton("Start Laser")
        self.btn_start_laser.clicked.connect(self.btn_start_laser_clicked)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.clicked.connect(self.btn_stop_clicked)
        self.btn_stop.setEnabled(False)

        self.btn_clear = QPushButton("Clear Plot")
        self.btn_clear.clicked.connect(self.btn_clear_clicked)

        self.btn_calibration = QPushButton("Start Calibration")
        self.btn_calibration.clicked.connect(self.btn_calibration_clicked)

        self.btn_park = QPushButton("Park Laser at 150 mA")
        self.btn_park.clicked.connect(self.btn_park_clicked)
        self.btn_park.setEnabled(True)

        self.btn_exit = QPushButton("Exit")
        self.btn_exit.clicked.connect(self.btn_exit_clicked)

        for btn in [self.btn_start_laser, self.btn_stop,
                    self.btn_clear, self.btn_calibration, self.btn_exit]:
            btn.setMinimumHeight(28)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Organize into rows so they are not cramped vertically
        row_btn1 = QHBoxLayout()
        row_btn1.setSpacing(4)
        row_btn1.addWidget(self.btn_start_laser)
        row_btn1.addWidget(self.btn_stop)

        row_btn2 = QHBoxLayout()
        row_btn2.setSpacing(4)
        row_btn2.addWidget(self.btn_clear)
        row_btn2.addWidget(self.btn_calibration)

        row_btn3 = QHBoxLayout()
        row_btn3.setSpacing(4)
        row_btn3.addWidget(self.btn_exit)

        controls.addLayout(row_btn1)
        controls.addLayout(row_btn2)
        controls.addLayout(row_btn3)

        self.edt_message_log = QLineEdit("OK")
        self.edt_message_log.setReadOnly(True)
        controls.addWidget(self.edt_message_log)
        controls.addStretch()

        # ── Right chart area: 2-row layout matching old software ──────
        charts = QVBoxLayout()
        charts.setSpacing(4)

        # Row 1: Laser Current + SR Signal side by side
        row1 = QHBoxLayout()
        self.chart_laser = pg.PlotWidget(title="Laser Current")
        self.chart_laser.setLabel("left", "Laser Current", units="mA")
        self.chart_laser.setLabel("bottom", "Time", units="s")
        self.chart_sr = pg.PlotWidget(title="SR Signal")
        self.chart_sr.setLabel("left", "SR (%)")
        self.chart_sr.setLabel("bottom", "Time", units="s")
        self.chart_sr.addLegend(offset=(10, 10))
        self.chart_sr.showGrid(x=True, y=True, alpha=0.2)
        for chart in [self.chart_laser, self.chart_sr]:
            chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            row1.addWidget(chart)
        charts.addLayout(row1, stretch=1)

        # Row 2: Readout Photodiode full width
        self.chart_photodiode = pg.PlotWidget(title="Readout Photodiode")
        self.chart_photodiode.setLabel("left", "Current", units="µA")
        self.chart_photodiode.setLabel("bottom", "Time", units="s")
        self.chart_photodiode.addLegend(offset=(10, 10))
        self.chart_photodiode.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.chart_photodiode.showGrid(x=True, y=True, alpha=0.2)
        charts.addWidget(self.chart_photodiode, stretch=1)

        main_layout.addLayout(controls, stretch=1)
        main_layout.addLayout(charts, stretch=4)