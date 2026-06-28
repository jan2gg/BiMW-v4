# controllers/intensity_controller.py
import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from collections import deque

try:
    import nidaqmx
    import nidaqmx.constants
    NIDAQMX_AVAILABLE = True
except ImportError:
    NIDAQMX_AVAILABLE = False

from views.tab_intensity import TabIntensity, CHANNEL_COLORS, NUM_INTENSITY_CHANNELS
from services.logger_service import LoggerService

SAMPLE_RATE = 10
SAMPLES_PER_READ = 10
UPDATE_INTERVAL_MS = 1000
PLOT_WINDOW_SECONDS = 900
MAX_PLOT_POINTS = SAMPLE_RATE * PLOT_WINDOW_SECONDS
NUM_SUMS = 7  # ch0_UP+ch0_DOWN, ..., ch6_UP+ch6_DOWN


class IntensityController(QObject):
    """Controls the Intensity pre-calibration tab.

    Reads all 14 AI channels at 10 Hz and displays the sum of each UP+DOWN
    pair (7 sums total) as a scrolling plot.
    """
    request_exit = pyqtSignal()

    def __init__(self, tab: TabIntensity, logger: LoggerService, setup=None, parent=None):
        super().__init__(parent)
        self._tab = tab
        self._log = logger
        self._setup = setup

        self._task = None
        self._running = False

        # Rolling buffers for 7 sums
        self._time_data = deque(maxlen=MAX_PLOT_POINTS)
        self._sum_data = [deque(maxlen=MAX_PLOT_POINTS) for _ in range(NUM_SUMS)]
        self._elapsed = 0.0

        self._save_file = None
        self._save_path: str = ""

        self._curves: list = []
        self._init_curves()

        self._timer = QTimer()
        self._timer.setInterval(UPDATE_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)

        self._tab.btn_start_clicked.connect(self._on_start)
        self._tab.btn_stop_clicked.connect(self._on_stop)
        self._tab.btn_clear_clicked.connect(self._on_clear)
        self._tab.btn_exit.clicked.connect(self.request_exit.emit)
        self._cal_ctrl = None

    def _init_curves(self):
        self._tab.chart.clear()
        self._curves = []
        for i in range(NUM_SUMS):
            curve = self._tab.chart.plot(
                [], [],
                pen=CHANNEL_COLORS[i],
                name=f"SR {i + 1}",
            )
            curve.setClipToView(True)
            curve.setDownsampling(auto=True, method="peak")
            self._curves.append(curve)

    def _on_start(self):
        if self._running:
            return
        if not NIDAQMX_AVAILABLE:
            self._tab.lbl_status.setText("nidaqmx not available")
            return
        try:
            if self._cal_ctrl is not None:
                self._cal_ctrl._tmr_couple.stop()
                self._cal_ctrl._daq.full_reset()

            self._task = nidaqmx.Task()
            device = self._setup.device_selected if self._setup is not None else "Dev1"
            for i in range(NUM_INTENSITY_CHANNELS):
                self._task.ai_channels.add_ai_voltage_chan(
                    f"{device}/ai{i}",
                    terminal_config=nidaqmx.constants.TerminalConfiguration.RSE,
                    min_val=-10,
                    max_val=10,
                )
            self._task.timing.cfg_samp_clk_timing(
                rate=SAMPLE_RATE,
                sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
            )
            self._task.in_stream.input_buf_size = 1000
            self._task.start()

            self._running = True
            self._tab.btn_start.setEnabled(False)
            self._tab.btn_stop.setEnabled(True)
            self._tab.lbl_status.setText("Running…")
            self._tab.lbl_status.setStyleSheet("color: #4CAF50;")
            self._timer.start()
        except Exception as exc:
            self._log.log_exception("IntensityController._on_start", exc)
            self._tab.lbl_status.setText(f"Error: {exc}")

    def _on_stop(self):
        if not self._running:
            return
        self._timer.stop()
        self._running = False
        if self._task is not None:
            try:
                self._task.stop()
                self._task.close()
            except Exception:
                pass
            self._task = None
        if self._save_file is not None:
            try:
                self._save_file.close()
            except Exception:
                pass
            self._save_file = None

        self._tab.btn_start.setEnabled(True)
        self._tab.btn_stop.setEnabled(False)
        self._tab.lbl_status.setText("Stopped")
        self._tab.lbl_status.setStyleSheet("color: gray;")

        if self._cal_ctrl is not None:
            try:
                self._cal_ctrl._daq.init_read_task()
                self._cal_ctrl._daq.init_write_task()
                self._cal_ctrl._add_channels()
                self._cal_ctrl._daq.start_read_task()
                self._cal_ctrl.start_couple_timer()
            except Exception as exc:
                self._log.log_exception("IntensityController._on_stop restore", exc)

    def _on_clear(self):
        self._time_data.clear()
        for ch_data in self._sum_data:
            ch_data.clear()
        self._elapsed = 0.0

        for curve in self._curves:
            curve.setData([], [])

        for lbl in self._tab.channel_value_labels.values():
            lbl.setText("—")

    def _on_tick(self):
        if not self._running or self._task is None:
            return
        try:
            raw = self._task.read(number_of_samples_per_channel=SAMPLES_PER_READ)
            channels = (np.array(raw).T) * -1  # shape: (samples, 14)

            dt = 1.0 / SAMPLE_RATE

            for sample_idx in range(len(channels)):
                t = (self._time_data[-1] + dt) if self._time_data else 0.0
                self._time_data.append(t)

                for i in range(NUM_SUMS):
                    up   = float(channels[sample_idx, i * 2])
                    down = float(channels[sample_idx, i * 2 + 1])
                    self._sum_data[i].append(up + down)

            time_arr = np.fromiter(self._time_data, dtype=float)
            for i, curve in enumerate(self._curves):
                sum_arr = np.fromiter(self._sum_data[i], dtype=float)
                curve.setData(time_arr, sum_arr)

            # Update labels with latest sum value
            latest = channels[-1]
            for i, lbl in self._tab.channel_value_labels.items():
                up   = latest[i * 2]
                down = latest[i * 2 + 1]
                lbl.setText(f"{up + down:.4f} mA")

            # Save to file if open
            if self._save_file is not None:
                t = self._time_data[-1]
                sums = [
                    float(channels[-1, i * 2]) + float(channels[-1, i * 2 + 1])
                    for i in range(NUM_SUMS)
                ]
                row = f"{t:.4f}\t" + "\t".join(f"{v:.6f}" for v in sums)
                self._save_file.write(row + "\n")
                self._save_file.flush()

        except Exception as exc:
            self._log.log_exception("IntensityController._on_tick", exc)
            self._tab.lbl_status.setText("Read error — check DAQ connection")