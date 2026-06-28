# controllers/processing_controller.py
import csv
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from views.tab_processing import TabProcessing
from controllers.data_controller import DataController
from services.logger_service import LoggerService
from Lib.Colors import CHANNEL_COLORS

NUM_CHANNELS = 7


class ProcessingController(QObject):
    request_exit = pyqtSignal()
    def __init__(
        self,
        tab: TabProcessing,
        data_ctrl: DataController,
        logger: LoggerService,
    ):
        super().__init__()
        self._tab = tab
        self._data = data_ctrl
        self._log = logger
        self._time_data: list = []
        self._phase_data: dict = {}    # {channel_idx: np.ndarray}
        self._filter_cutoff: float = 0.05
        self._connect_signals()

    def _connect_signals(self):
        self._tab.btn_load_experiment_clicked.connect(self._on_load)
        self._tab.btn_filter_clicked.connect(self._on_filter)
        self._tab.btn_save_clicked.connect(self._on_save)
        self._tab.btn_exit.clicked.connect(self.request_exit.emit)
        self._tab.spb_filter_cutoff_changed.connect(self._on_cutoff_changed)

    def _on_cutoff_changed(self, value: float):
        self._filter_cutoff = value

    def _on_load(self):
        try:
            from PyQt6.QtWidgets import QFileDialog
            filepath, _ = QFileDialog.getOpenFileName(
                self._tab,
                "Open Experiment File",
                "",
                "Data files (*.DAT *.txt *.csv);;All files (*)"
            )
            if not filepath:
                return

            self._time_data = []
            self._phase_data = {i: [] for i in range(NUM_CHANNELS)}

            with open(filepath, "r") as f:
                reader = csv.reader(f, delimiter="\t")
                next(reader, None)
                for row in reader:
                    if len(row) < 2:
                        continue
                    try:
                        self._time_data.append(float(row[0]))
                        for i in range(NUM_CHANNELS):
                            val = float(row[i + 1]) if (i + 1) < len(row) else 0.0
                            self._phase_data[i].append(val)
                    except ValueError:
                        continue

            for i in range(NUM_CHANNELS):
                self._phase_data[i] = np.array(self._phase_data[i], dtype=float)

            self._tab.lbl_file_path.setText(filepath.split("/")[-1])
            self._tab.btn_filter.setEnabled(True)
            self._tab.btn_save.setEnabled(True)
            self._plot_data(self._time_data, self._phase_data)
            self._log.log("ProcessingController", f"Loaded: {filepath}")

        except Exception as exc:
            self._log.log_exception("ProcessingController._on_load", exc)

    def _on_filter(self):
        try:
            if len(self._time_data) < 3:
                return

            dt = self._time_data[1] - self._time_data[0]
            fs = 1.0 / dt if dt > 0 else 0.0
            nyquist = fs / 2.0

            if nyquist <= 0:
                self._log.log("ProcessingController", "Invalid sampling frequency, skipping filter")
                return

            if self._filter_cutoff >= nyquist:
                self._log.log(
                    "ProcessingController",
                    f"Cutoff {self._filter_cutoff} Hz >= Nyquist {nyquist:.4f} Hz, skipping"
                )
                return

            from scipy.signal import butter, filtfilt

            b, a = butter(2, self._filter_cutoff / nyquist, btype="low", output="ba")
            padlen = 3 * max(len(a), len(b))

            for i in range(NUM_CHANNELS):
                if len(self._phase_data[i]) > padlen:
                    self._phase_data[i] = filtfilt(b, a, self._phase_data[i])
                else:
                    self._log.log(
                        "ProcessingController",
                        f"Channel {i + 1} too short for filtfilt (len={len(self._phase_data[i])}, padlen={padlen}), skipped"
                    )

            self._plot_data(self._time_data, self._phase_data)

        except Exception as exc:
            self._log.log_exception("ProcessingController._on_filter", exc)

    def _on_save(self):
        try:
            filepath = self._data.open_save_dialog("processed_phase.DAT")
            if not filepath:
                return
            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f, delimiter="\t")
                header = ["Time(s)"] + [f"Phase{i+1}(rad)" for i in range(NUM_CHANNELS)]
                writer.writerow(header)
                for row_idx, t in enumerate(self._time_data):
                    row = [round(t, 4)]
                    for i in range(NUM_CHANNELS):
                        val = (
                            float(self._phase_data[i][row_idx])
                            if row_idx < len(self._phase_data[i])
                            else ""
                        )
                        row.append(round(val, 5) if val != "" else "")
                    writer.writerow(row)
            self._log.log("ProcessingController", f"Saved: {filepath}")
        except Exception as exc:
            self._log.log_exception("ProcessingController._on_save", exc)


    def _plot_data(self, time_data: list, phase_data: dict):
        self._tab.chart_phase.clear()
        t = np.array(time_data)
        for i in range(NUM_CHANNELS):
            arr = phase_data.get(i, np.array([]))
            if len(arr) > 0 and len(arr) == len(t):
                self._tab.chart_phase.plot(
                    t, arr,
                    pen=CHANNEL_COLORS[i],
                    name=f"Channel {i + 1}",
                )