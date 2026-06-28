from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QDoubleSpinBox, QComboBox,
    QLineEdit, QSizePolicy, QLCDNumber, QGridLayout
)
from PyQt6.QtCore import pyqtSignal
import pyqtgraph as pg

CHANNEL_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2",
    "#59a14f", "#edc948", "#b07aa1",
]
NUM_CHANNELS = 7


class TabMeasure(QWidget):
    btn_start_laser_clicked = pyqtSignal()
    btn_stop_clicked = pyqtSignal()
    btn_clear_clicked = pyqtSignal()
    btn_save_current_data_clicked = pyqtSignal()
    btn_exit_clicked = pyqtSignal()
    btn_reset_time_clicked = pyqtSignal()
    cmb_device_changed = pyqtSignal(int)
    flip_changed = pyqtSignal(int, bool)   # channel index, flipped
    cmb_sr_selection_changed = pyqtSignal(int)
    point_selection_changed = pyqtSignal(int, int)  # channel index, selected point (-1 = all)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(10)
        self.setMinimumSize(1100, 700)

        # ── Left controls ─────────────────────────────────────────────
        controls = QVBoxLayout()
        controls.setSpacing(6)  # was 10
        controls.setContentsMargins(6, 6, 6, 6)

        dev_group = QGroupBox("Device")
        dev_layout = QVBoxLayout(dev_group)
        self.cmb_device = QComboBox()
        self.cmb_device.setMinimumHeight(28)
        self.cmb_device.currentIndexChanged.connect(self.cmb_device_changed)
        dev_layout.addWidget(self.cmb_device)
        controls.addWidget(dev_group)

        time_group = QGroupBox("Elapsed Time")
        time_layout = QVBoxLayout(time_group)
        self.lcd_time = QLCDNumber()
        self.lcd_time.setDigitCount(8)
        self.lcd_time.display("00:00:00")
        self.lcd_time.setFixedHeight(32)
        time_layout.addWidget(self.lcd_time)
        controls.addWidget(time_group)

        filter_group = QGroupBox("Phase Filter")
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.addWidget(QLabel("Cutoff Frequency:"))
        self.spb_filter_phase = QDoubleSpinBox()
        self.spb_filter_phase.setMinimumHeight(28)
        self.spb_filter_phase.setRange(0.001, 10.0)
        self.spb_filter_phase.setValue(0.05)
        self.spb_filter_phase.setSingleStep(0.005)
        self.spb_filter_phase.setSuffix(" Hz")
        filter_layout.addWidget(self.spb_filter_phase)
        controls.addWidget(filter_group)

        analysis_group = QGroupBox("Data Analysis")
        analysis_layout = QVBoxLayout(analysis_group)
        analysis_layout.setSpacing(6)
        analysis_layout.setContentsMargins(4, 4, 4, 4)
        analysis_layout.addWidget(QLabel("Select point per channel:"))

        grid = QGridLayout()
        grid.setSpacing(4)

        self.cmb_point_selection = []
        for i in range(NUM_CHANNELS):
            row = i // 2  # 2 channels per grid row
            col = i % 2

            cell_layout = QHBoxLayout()
            cell_layout.setSpacing(4)
            cell_layout.addWidget(QLabel(f"CH {i + 1}"))

            cmb = QComboBox()
            cmb.setMinimumHeight(26)
            cmb.addItem("None", -1)
            cmb.addItem("Point 1", 0)  # updated after calibration
            cmb.currentIndexChanged.connect(
                lambda _, ch=i, box=cmb: self.point_selection_changed.emit(
                    ch, int(box.currentData())
                )
            )

            self.cmb_point_selection.append(cmb)
            cell_layout.addWidget(cmb)

            grid.addLayout(cell_layout, row, col)

        analysis_layout.addLayout(grid)
        controls.addWidget(analysis_group)

        # Per-channel flip buttons
        flip_group = QGroupBox("Flip Channels")
        flip_layout = QGridLayout(flip_group)
        flip_layout.setSpacing(6)
        # After flip_group, before the action buttons:
        sr_group = QGroupBox("SR Selection")
        sr_layout = QVBoxLayout(sr_group)
        self.cmb_sr_selection = QComboBox()
        self.cmb_sr_selection.setMinimumHeight(28)
        self.cmb_sr_selection.addItem("All SRs")
        for i in range(NUM_CHANNELS):
            self.cmb_sr_selection.addItem(f"SR {i + 1}")
        self.cmb_sr_selection.currentIndexChanged.connect(self.cmb_sr_selection_changed)
        sr_layout.addWidget(self.cmb_sr_selection)
        controls.addWidget(sr_group)
        self.flip_buttons: list[QPushButton] = []
        for i in range(NUM_CHANNELS):
            color = CHANNEL_COLORS[i]
            btn = QPushButton(f"Flip CH {i + 1}")
            btn.setMinimumHeight(26)  # was 30
            btn.setCheckable(True)
            btn.setStyleSheet(
                f"QPushButton {{ border-left: 4px solid {color}; padding-left: 4px; }}"
                f"QPushButton:checked {{ background-color: {color}; color: black; }}"
            )
            idx = i
            btn.toggled.connect(lambda checked, ch=idx: self.flip_changed.emit(ch, checked))
            self.flip_buttons.append(btn)
            row = i // 2  # 2 buttons per row
            col = i % 2
            flip_layout.addWidget(btn, row, col)
        controls.addWidget(flip_group)

        self.btn_start_laser = QPushButton("Start Laser")
        self.btn_start_laser.clicked.connect(self.btn_start_laser_clicked)

        self.btn_stop = QPushButton("Stop Laser")
        self.btn_stop.clicked.connect(self.btn_stop_clicked)
        self.btn_stop.setEnabled(False)

        self.btn_clear = QPushButton("Clear Plot")
        self.btn_clear.clicked.connect(self.btn_clear_clicked)

        self.btn_save_current_data = QPushButton("Save Current Data")
        self.btn_save_current_data.clicked.connect(self.btn_save_current_data_clicked)
        self.btn_save_current_data.setEnabled(False)

        self.btn_reset_time = QPushButton("Reset Time")
        self.btn_reset_time.clicked.connect(self.btn_reset_time_clicked)

        self.btn_exit = QPushButton("Exit")
        self.btn_exit.clicked.connect(self.btn_exit_clicked)

        for btn in [self.btn_start_laser, self.btn_stop, self.btn_clear,
                    self.btn_save_current_data, self.btn_exit]:
            btn.setMinimumHeight(28)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Three rows of buttons
        row_btn1 = QHBoxLayout()
        row_btn1.setSpacing(4)
        row_btn1.addWidget(self.btn_start_laser)
        row_btn1.addWidget(self.btn_stop)

        row_btn2 = QHBoxLayout()
        row_btn2.setSpacing(4)
        row_btn2.addWidget(self.btn_reset_time)
        row_btn2.addWidget(self.btn_clear)

        row_btn3 = QHBoxLayout()
        row_btn3.setSpacing(4)
        row_btn3.addWidget(self.btn_save_current_data)
        row_btn3.addWidget(self.btn_exit)

        controls.addLayout(row_btn1)
        controls.addLayout(row_btn2)
        controls.addLayout(row_btn3)

        self.edt_message_log = QLineEdit("OK")
        self.edt_message_log.setMinimumHeight(28)
        self.edt_message_log.setReadOnly(True)
        controls.addWidget(self.edt_message_log)
        controls.addStretch()

        # ── Right charts ───────────────────────────────────────────────
        charts = QVBoxLayout()
        charts.setSpacing(4)

        # Row 1: SR Points + SR Signal side by side
        row1 = QHBoxLayout()
        self.chart_point = pg.PlotWidget(title="SR Points")
        self.chart_point.setLabel("left", "SR (%)")
        self.chart_point.setLabel("bottom", "Time", units="s")
        self.chart_point.addLegend(offset=(10, 10))
        self.chart_point.showGrid(x=True, y=True, alpha=0.2)
        self.chart_sr = pg.PlotWidget(title="Signal SR")
        self.chart_sr.setLabel("left", "SR (%)")
        self.chart_sr.setLabel("bottom", "Time", units="s")
        self.chart_sr.showGrid(x=True, y=True, alpha=0.2)


        for chart in [self.chart_point, self.chart_sr]:
            chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            row1.addWidget(chart)
        charts.addLayout(row1, stretch=1)

        # Row 2: Phase Shift full width
        self.chart_phase = pg.PlotWidget(title="Phase Shift")
        self.chart_phase.setLabel("left", "Phase Shift", units="rad")
        self.chart_phase.setLabel("bottom", "Time", units="s")
        self.chart_phase.addLegend(offset=(10, 10))
        self.chart_phase.showGrid(x=True, y=True, alpha=0.2)
        self.chart_phase.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        charts.addWidget(self.chart_phase, stretch=1)

        controls_widget = QWidget()
        controls_widget.setLayout(controls)
        controls_widget.setMinimumWidth(340)
        controls_widget.setMaximumWidth(380)

        main_layout.addWidget(controls_widget, stretch=0)
        main_layout.addLayout(charts, stretch=1)

        self.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            margin-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px 0 4px;
        }
        QPushButton, QComboBox, QDoubleSpinBox, QLineEdit {
            font-size: 12px;
        }
        QLCDNumber {
            min-height: 32px;
        }
        """)

    def set_channel_point_count(self, channel: int, n_points: int):
        cmb = self.cmb_point_selection[channel]
        current_value = cmb.currentData()

        cmb.blockSignals(True)
        cmb.clear()

        # First option: no point for this channel
        cmb.addItem("None", -1)

        # Then the available calibration limit points P1..Pn
        n = max(1, n_points)
        for p in range(n):
            cmb.addItem(f"Point {p + 1}", p)

        # Try to keep previous selection if still valid; default to Point 1
        idx = cmb.findData(current_value)
        if idx < 0:
            idx = cmb.findData(0)  # Point 1
        cmb.setCurrentIndex(idx)
        cmb.blockSignals(False)
    def refresh_point_selectors(self, cal):
        for ch in range(NUM_CHANNELS):
            self.set_channel_point_count(ch, cal.n_points(ch))