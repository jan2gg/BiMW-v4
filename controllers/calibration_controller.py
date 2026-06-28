# controllers/calibration_controller.py
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from models.measurement_config import MeasurementConfig
from services.logger_service import LoggerService
from services.timer_service import TimerService
from controllers.measurement_setup_controller import (
    MeasurementSetupController, CURRENT_RANGES,
    SIGNAL_SINE, SIGNAL_SAWTOOTH, SIGNAL_NONE,
)
from controllers.data_controller import DataController
from core.daq.acquisition import AcquisitionTask
from core.signal.signal_filter import build_iup_idown_filter, apply_filter
from core.signal.sr_processor import (
    compute_sr_signal, center_sr_signal,
    find_zero_crossings_and_peaks, select_calibration_points,
)
from core.daq.device_discovery import RELOAD_DEVICES
from views.tab_calibration import TabCalibration
from models.calibration_result import CalibrationResult

NUM_CHANNELS = 7


class CalibrationController(QObject):
    calibration_finished = pyqtSignal()
    switch_to_measure = pyqtSignal()
    request_exit = pyqtSignal()

    def __init__(
        self,
        tab: TabCalibration,
        config: MeasurementConfig,
        setup: MeasurementSetupController,
        daq: AcquisitionTask,
        calibration_result: CalibrationResult,
        data_ctrl: DataController,
        logger: LoggerService,
    ):
        super().__init__()
        self._tab = tab
        self._config = config
        self._setup = setup
        self._daq = daq
        self._cal = calibration_result
        self._data = data_ctrl
        self._log = logger

        # Timers
        self._tmr_read = TimerService(config.time_read)
        self._tmr_calibration = TimerService(config.time_calibration)
        self._tmr_couple = TimerService(config.time_read / 10)

        # State
        self._doing_calibration = False
        self._calibration_done = False
        self._no_first_calibration = False
        self._btn_start_laser_clicked = False
        self._btn_stop_clicked = 0
        self._count_time_calibration = 0
        self._b_signal: np.ndarray | None = None
        self._a_signal: np.ndarray | None = None

        # Data buffers
        self._data_iup_chart: dict = {}
        self._data_idown_chart: dict = {}
        self._time_photodiode_chart: np.ndarray = np.array([])
        self._time_laser_chart: np.ndarray = np.array([])
        self._laser_current_chart: np.ndarray = np.array([])
        self._signal_sr_one_second: dict = {}
        self._signal_sr_one_second_chart: dict = {}
        self._index: dict = {}
        self._values_min_count: dict = {}
        self._values_max_count: dict = {}
        self._init_time: float = 0.0

        self._populate_ui()
        self._connect_signals()
        self._intensity_ctrl = None

    # ----------------------------------------------------------- UI population
    def _populate_ui(self):
        for d in self._setup.devices:
            self._tab.cmb_device.addItem(d)
        self._tab.cmb_device.addItem(RELOAD_DEVICES)

        for item in [SIGNAL_SAWTOOTH, SIGNAL_SINE, SIGNAL_NONE]:
            self._tab.cmb_signal_modulation.addItem(item)
        self._tab.cmb_signal_modulation.setCurrentIndex(1)

        for item in CURRENT_RANGES:
            self._tab.cmb_current_range.addItem(item)
        self._tab.cmb_current_range.setCurrentIndex(3)

        self._tab.spb_freq.setValue(self._config.freq)
        self._tab.spb_laser_current_set.setValue(self._config.laser_current_set)
        self._tab.spb_calibration_time.setValue(self._config.time_calibration)
        self._tab.btn_calibration.setEnabled(False)
        self._tab.btn_stop.setEnabled(False)

    # --------------------------------------------------------- signal wiring
    def _connect_signals(self):
        self._tab.cmb_device_changed.connect(self._on_device_changed)
        self._tab.cmb_signal_modulation_changed.connect(self._setup.set_modulation_type)
        self._tab.cmb_current_range_changed.connect(self._setup.set_current_range)
        self._tab.spb_freq_changed.connect(self._setup.set_frequency)
        self._tab.spb_laser_current_set_changed.connect(self._setup.set_laser_current)
        self._tab.spb_calibration_time_changed.connect(self._on_calibration_time_changed)
        self._tab.btn_start_laser_clicked.connect(self._on_start_laser)
        self._tab.btn_stop_clicked.connect(lambda: self._on_stop(btn_exit=False))
        self._tab.btn_calibration_clicked.connect(self._on_calibration)
        self._tab.btn_clear_clicked.connect(self._on_clear)
        self._tab.btn_exit_clicked.connect(self._on_exit)
        self._tmr_couple.timeout.connect(self._update_couple_display)
        self._tmr_calibration.timeout.connect(self._on_calibration_finished)
        self._tab.cmb_sr_selection_changed.connect(self._on_sr_selection_changed)
        # NOTE: _tmr_read is connected fresh on each Start Laser click

    def _on_sr_selection_changed(self, index: int):
        self._update_charts()

    # --------------------------------------------------------- device handling
    def _on_device_changed(self, index: int):
        try:
            if index == len(self._setup.devices):
                devices = self._setup.reload_devices()
                self._tab.cmb_device.blockSignals(True)
                self._tab.cmb_device.clear()
                for d in devices:
                    self._tab.cmb_device.addItem(d)
                self._tab.cmb_device.addItem(RELOAD_DEVICES)
                self._tab.cmb_device.blockSignals(False)
            else:
                self._setup.select_device(index)
                self._daq.restart_read_task()
                self._daq.restart_write_task()
                self._daq.init_read_task()
                self._daq.init_write_task()
                if self._setup.device_selected != "No Device":
                    self._add_channels()
        except Exception as exc:
            self._log.log_exception("CalibrationController._on_device_changed", exc)

    def _add_channels(self):
        try:
            self._daq.config_channel_read(
                self._setup.device_selected, self._config.limit_volt_device
            )
            self._daq.config_timing_read(
                self._config.sample_rate_read,
                self._config.sample_rate_read * 1000,
            )
            self._daq.config_channel_write(
                self._setup.device_selected, self._config.limit_volt_device
            )
            self._daq.config_timing_write(
                self._config.sample_rate_read,
                self._config.sample_rate_read * 2000,
            )
            self._daq.create_buffer_read(self._config.samples_per_channel_read)
            self._daq.create_buffer_couple(self._config.sample_rate_couple)
            self._daq.config_stream_reader()
            self._daq.config_stream_writer()
        except Exception as exc:
            self._log.log_exception("CalibrationController._add_channels", exc)

    # ---------------------------------------------------- parameter changes
    def _on_calibration_time_changed(self, value: int):
        self._config.time_calibration = value
        self._tmr_calibration.set_interval(value)

    # ------------------------------------------------------ couple display
    def _update_couple_display(self):
        try:
            buf = self._daq.read_couple_data()
            coeff = self._setup.coefficient_photodiode
            iup   = np.array(buf[0])  / coeff
            idown = np.array(buf[1])  / coeff
            iup7  = np.array(buf[12]) / coeff
            idown7= np.array(buf[13]) / coeff
            self._tab.lbl_iup.setText(  f"I UP: {np.mean(iup)   * 1e6:.3f} µA")
            self._tab.lbl_idown.setText(f"I DOWN: {np.mean(idown) * 1e6:.3f} µA")
            self._tab.lbl_iup7.setText( f"I UP 7: {np.mean(iup7) * 1e6:.3f} µA")
            self._tab.lbl_idown7.setText(f"I DOWN 7: {np.mean(idown7) * 1e6:.3f} µA")
        except Exception as exc:
            self._log.log_exception("CalibrationController._update_couple_display", exc)

    # ---------------------------------------------------- laser start/stop
    def _on_start_laser(self):
        try:
            # Guard: intensity check must be stopped before calibration can start
            if self._intensity_ctrl is not None and self._intensity_ctrl._running:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self._tab,
                    "Intensity Check Running",
                    "Stop the Intensity Check acquisition before starting calibration.",
                )
                return

            self._tmr_couple.stop()
            self._daq.stop_read_task()

            self._b_signal, self._a_signal = build_iup_idown_filter(
                self._config.peak_to_filter,
                self._config.freq,
                self._config.time_read,
                self._config.sample_rate_read,
            )

            self._reset_acquisition_buffers()
            self._calibration_done = False
            self._btn_stop_clicked = 0
            self._init_time = 0.0

            self._tab.btn_start_laser.setEnabled(False)
            self._tab.btn_stop.setEnabled(True)
            self._tab.btn_calibration.setEnabled(self._setup.modulation_active)

            self._daq.start_read_task()
            self._daq.write_data(self._setup.signal_modulation)
            self._daq.start_write_task()

            # Connect timer fresh, guard against duplicate connections
            try:
                self._tmr_read.timeout.disconnect()
            except (RuntimeError, TypeError):
                pass

            # Simple, old-style behavior: just start reading photodiode + laser
            self._tmr_read.timeout.connect(self._read_photodiode)
            self._tmr_read.start()

            self._btn_start_laser_clicked = True
            self._tab.edt_message_log.setText("OK")

        except Exception as exc:
            self._log.log_exception("CalibrationController._on_start_laser", exc)
            self._tab.edt_message_log.setText("ERROR")

    def _on_stop(self, btn_exit: bool = False):
        try:
            self._btn_start_laser_clicked = False
            self._tmr_read.stop()
            self._tmr_calibration.stop()
            try:
                self._tmr_read.timeout.disconnect()
            except (RuntimeError, TypeError):
                pass

            # Full release — stop AND close so measurement gets clean hardware
            self._daq.full_reset()
            # Re-initialize tasks so Start Laser can be used again
            try:
                self._daq.init_read_task()
                self._daq.init_write_task()
                self._add_channels()
            except Exception as exc:
                self._log.log_exception("CalibrationController._on_stop (reinit)", exc)

            self._data.close_phase_file()
            self._no_first_calibration = False
            self._btn_stop_clicked = 1

            self._tab.btn_start_laser.setEnabled(True)
            self._tab.btn_stop.setEnabled(False)
            self._tab.btn_calibration.setEnabled(False)
            self._tab.edt_message_log.setText("OK")


        except Exception as exc:
            self._log.log_exception("CalibrationController._on_stop", exc)

    def _on_stop_acquisition(self):
        self._reset_acquisition_buffers()
        self._calibration_done = False
        self._no_first_calibration = False

    def _on_restart(self):
        self._reset_acquisition_buffers()
        self._tab.edt_message_log.setText("OK")

    def _on_exit(self):
        self.request_exit.emit()

    # ------------------------------------------------- calibration workflow
    def _on_calibration(self):
        try:
            self._tmr_calibration.start()
            self._doing_calibration = True
            self._calibration_done = False
            self._count_time_calibration = 0
            self._values_min_count = {}
            self._values_max_count = {}

            for i in range(NUM_CHANNELS):
                self._index[f"index_{i}"] = []
                for _ in range(int(self._config.time_calibration / 2)):
                    self._index[f"index_{i}"].append([])
                    for _ in range(int(self._config.freq * self._config.time_read)):
                        self._index[f"index_{i}"][-1].append([])

            self._tab.btn_calibration.setEnabled(False)
            self._tab.edt_message_log.setText("Calibrating...")
        except Exception as exc:
            self._log.log_exception("CalibrationController._on_calibration", exc)

    def _on_calibration_finished(self):
        try:
            self._tmr_calibration.stop()
            self._doing_calibration = False
            self._values_min_count, self._values_max_count = (
                select_calibration_points(self._index)
            )
            self._no_first_calibration = True
            self._calibration_done = True
            self._reset_post_calibration_buffers()

            self._tab.btn_calibration.setEnabled(True)
            self._tab.edt_message_log.setText("Calibration done")
            self._cal.values_min_count = self._values_min_count
            self._cal.values_max_count = self._values_max_count
            self._cal.is_done = True
            self.calibration_finished.emit()
            self._on_stop()
            from views.dialogs import CalibrationDoneDialog
            dlg = CalibrationDoneDialog(parent=self._tab)
            dlg.exec()
            self.switch_to_measure.emit()
            self._tab.edt_message_log.setText("Calibration done — laser stopped. Go to Measure tab.")
        except Exception as exc:
            self._log.log_exception("CalibrationController._on_calibration_finished", exc)

    # ------------------------------------------------- data acquisition loop
    def _read_photodiode(self):
        try:
            buf = self._daq.read_data()
            self._process_buffer(buf)
            self._update_couple_display_from_buf(buf)
        except Exception as exc:
            self._tab.edt_message_log.setText("ERROR")
            self._log.log_exception("CalibrationController._read_photodiode", exc)

    def _update_couple_display_from_buf(self, buf):
        try:
            coeff = self._setup.coefficient_photodiode
            iup = np.mean(np.array(buf[0]) / coeff) * 1e6
            idown = np.mean(np.array(buf[1]) / coeff) * 1e6
            iup7 = np.mean(np.array(buf[12]) / coeff) * 1e6
            idown7 = np.mean(np.array(buf[13]) / coeff) * 1e6
            self._tab.lbl_iup.setText(f"I UP: {iup:.3f} µA")
            self._tab.lbl_idown.setText(f"I DOWN: {idown:.3f} µA")
            self._tab.lbl_iup7.setText(f"I UP 7: {iup7:.3f} µA")
            self._tab.lbl_idown7.setText(f"I DOWN 7: {idown7:.3f} µA")
        except Exception as exc:
            self._log.log_exception(
                "CalibrationController._update_couple_display_from_buf", exc
            )

    def _process_buffer(self, buf):
        coeff = self._setup.coefficient_photodiode
        iup = {}
        idown = {}
        for i in range(NUM_CHANNELS):
            iup[i]   = np.array(buf[i * 2])     / coeff
            idown[i] = np.array(buf[i * 2 + 1]) / coeff

        if self._b_signal is not None:
            for i in range(NUM_CHANNELS):
                iup[i]   = apply_filter(self._b_signal, self._a_signal, iup[i])
                idown[i] = apply_filter(self._b_signal, self._a_signal, idown[i])

        if self._setup.modulation_active:
            for i in range(NUM_CHANNELS):
                sr = compute_sr_signal(iup[i], idown[i])
                sr = center_sr_signal(sr)
                self._signal_sr_one_second[f"SROneSecond_{i}"] = sr

        nfc = max(1, int(self._config.samples_per_channel_read / self._config.samples_chart))
        for i in range(NUM_CHANNELS):
            key_up = f"iUPChart_{i}"
            key_dn = f"iDOWNChart_{i}"
            if key_up not in self._data_iup_chart:
                self._data_iup_chart[key_up]  = np.array([])
                self._data_idown_chart[key_dn] = np.array([])
            self._data_iup_chart[key_up]  = np.append(
                self._data_iup_chart[key_up],  iup[i][::nfc]   * 1e6)
            self._data_idown_chart[key_dn] = np.append(
                self._data_idown_chart[key_dn], idown[i][::nfc] * 1e6)

        step = self._config.time_read
        self._time_photodiode_chart = np.append(
            self._time_photodiode_chart,
            np.around(np.arange(
                self._init_time,
                self._init_time + step,
                step / self._config.samples_chart,
            ), 6),
        )

        laser_buf = np.array(buf[15]) / self._config.conversion_factor_laser
        self._laser_current_chart = laser_buf.copy()
        self._time_laser_chart = np.around(np.arange(
            self._init_time,
            self._init_time + step,
            step / max(len(laser_buf), 1),
        ), 6)
        self._init_time += step

        if self._doing_calibration:
            self._run_calibration_step()

        self._update_charts()

    def _run_calibration_step(self):
        if self._count_time_calibration >= int(self._config.time_calibration / 2):
            return
        try:
            samples_per_period = int(self._config.sample_rate_read / self._config.freq)
            for i in range(NUM_CHANNELS):
                sr = self._signal_sr_one_second.get(f"SROneSecond_{i}")
                if sr is None:
                    continue
                for k in range(int(self._config.freq * self._config.time_read)):
                    start = k * samples_per_period
                    end   = start + samples_per_period
                    sr_period = center_sr_signal(np.array(sr[start:end].copy()))
                    crossings = find_zero_crossings_and_peaks(sr_period)
                    self._index[f"index_{i}"][self._count_time_calibration][k] = crossings
            self._count_time_calibration += 1
        except Exception as exc:
            self._log.log_exception("CalibrationController._run_calibration_step", exc)

    # ------------------------------------------------------------ chart update
    def _update_charts(self):
        try:
            t = self._time_photodiode_chart
            if self._data_iup_chart.get("iUPChart_0") is not None and len(t) > 0:
                self._tab.chart_photodiode.clear()
                self._tab.chart_photodiode.plot(
                    t, self._data_iup_chart["iUPChart_0"],
                    pen="orange", name="I UP 1")
                self._tab.chart_photodiode.plot(
                    t, self._data_idown_chart["iDOWNChart_0"],
                    pen="cyan", name="I DOWN 1")
                self._tab.chart_photodiode.plot(
                    t, self._data_iup_chart["iUPChart_6"],
                    pen="#59a14f", name="I UP 7")
                self._tab.chart_photodiode.plot(
                    t, self._data_idown_chart["iDOWNChart_6"],
                    pen="#e15759", name="I DOWN 7")

            if len(self._time_laser_chart) > 0:
                self._tab.chart_laser.clear()
                self._tab.chart_laser.plot(
                    self._time_laser_chart, self._laser_current_chart, pen="red")

            # SR chart — respects dropdown selection
            sel = self._tab.cmb_sr_selection.currentIndex()  # 0=All, 1-7=specific
            self._tab.chart_sr.clear()
            if sel == 0:
                # All SRs overlaid with distinct colours
                for i in range(NUM_CHANNELS):
                    sr = self._signal_sr_one_second.get(f"SROneSecond_{i}")
                    if sr is not None and len(self._time_laser_chart) > 0:
                        from views.tab_calibration import SR_COLORS
                        self._tab.chart_sr.plot(
                            self._time_laser_chart, sr,
                            pen=SR_COLORS[i], name=f"SR {i + 1}")
            else:
                i = sel - 1  # convert dropdown index to channel index
                sr = self._signal_sr_one_second.get(f"SROneSecond_{i}")
                if sr is not None and len(self._time_laser_chart) > 0:
                    from views.tab_calibration import SR_COLORS
                    self._tab.chart_sr.plot(
                        self._time_laser_chart, sr,
                        pen=SR_COLORS[i], name=f"SR {i + 1}")
        except Exception as exc:
            self._log.log_exception("CalibrationController._update_charts", exc)

    # ------------------------------------------------------------ buffer resets
    def _reset_acquisition_buffers(self):
        self._data_iup_chart  = {}
        self._data_idown_chart = {}
        self._time_photodiode_chart = np.array([])
        self._time_laser_chart      = np.array([])
        self._laser_current_chart   = np.array([])
        self._signal_sr_one_second  = {}
        self._signal_sr_one_second_chart = {}
        self._init_time = 0.0
        self._btn_stop_clicked = 0

    def _reset_post_calibration_buffers(self):
        self._reset_acquisition_buffers()
        self._index = {}

    def start_couple_timer(self):
        self._tmr_couple.start()

    def refresh_combos(self):
        self._tab.cmb_device.blockSignals(True)
        self._tab.cmb_device.clear()
        for d in self._setup.devices:
            self._tab.cmb_device.addItem(d)
        self._tab.cmb_device.addItem(RELOAD_DEVICES)
        self._tab.cmb_device.setCurrentIndex(0)
        self._tab.cmb_device.blockSignals(False)

        self._tab.cmb_signal_modulation.blockSignals(True)
        self._tab.cmb_signal_modulation.clear()
        for item in [SIGNAL_SAWTOOTH, SIGNAL_SINE, SIGNAL_NONE]:
            self._tab.cmb_signal_modulation.addItem(item)
        self._tab.cmb_signal_modulation.setCurrentIndex(1)
        self._tab.cmb_signal_modulation.blockSignals(False)

        self._tab.cmb_current_range.blockSignals(True)
        self._tab.cmb_current_range.clear()
        for item in CURRENT_RANGES:
            self._tab.cmb_current_range.addItem(item)
        self._tab.cmb_current_range.setCurrentIndex(3)
        self._tab.cmb_current_range.blockSignals(False)

    def _on_clear(self):
        self._reset_acquisition_buffers()
        for chart in (self._tab.chart_photodiode, self._tab.chart_laser, self._tab.chart_sr):
            chart.clear()
        self._tab.edt_message_log.setText("OK")

    def _read_laser_and_correct(self):
        try:
            self._tmr_read.stop()
            try:
                self._tmr_read.timeout.disconnect()
            except (RuntimeError, TypeError):
                pass

            buf = self._daq.read_data()
            laser_buf = np.array(buf[15]) / self._config.conversion_factor_laser
            actual_current = float(np.abs(laser_buf[-1]))

            self._config.laser_current_set = actual_current
            self._setup.set_laser_current(actual_current)

            # Stop write task, flush old buffer, write corrected signal, restart
            self._daq.stop_write_task()
            self._daq.write_data(self._setup.signal_modulation)
            self._daq.start_write_task()

            self._tab.spb_laser_current_set.blockSignals(True)
            self._tab.spb_laser_current_set.setValue(actual_current)
            self._tab.spb_laser_current_set.blockSignals(False)

            self._log.log("CalibrationController",
                          f"Laser current corrected: {actual_current:.2f} mA")

            self._tmr_read.timeout.connect(self._read_photodiode)
            self._tmr_read.start()

        except Exception as exc:
            self._log.log_exception("CalibrationController._read_laser_and_correct", exc)
            try:
                self._tmr_read.timeout.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._tmr_read.timeout.connect(self._read_photodiode)
            self._tmr_read.start()