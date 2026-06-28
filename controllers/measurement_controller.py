# controllers/measurement_controller.py
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, Qt


from models.measurement_config import MeasurementConfig
from models.calibration_result import CalibrationResult
from models.acquisition_state import AcquisitionState
from services.logger_service import LoggerService
from services.timer_service import TimerService
from controllers.measurement_setup_controller import MeasurementSetupController
from controllers.data_controller import DataController
from core.daq.acquisition import AcquisitionTask
from core.signal.signal_filter import (
    build_iup_idown_filter, build_phase_filter, apply_filter
)
from core.signal.sr_processor import (
    compute_sr_signal, center_sr_signal
)
from views.tab_measure import TabMeasure
from core.daq.device_discovery import RELOAD_DEVICES
from datetime import datetime
import pyqtgraph as pg

NUM_CHANNELS = 7


class MeasurementController(QObject):
    """Drives the Measure tab: reads photodiode data after calibration is done
    and computes + displays the unwrapped phase."""

    # Emitted each acquisition cycle so other components can react
    phase_updated = pyqtSignal()
    request_exit = pyqtSignal()

    def __init__(
        self,
        tab: TabMeasure,
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
        self._phase_offset: dict = {}  # zeroing offset per channel per point
        # Timers
        self._tmr_read = TimerService(config.time_read)

        # Filters (built on Start Laser)
        self._b_signal: np.ndarray | None = None
        self._a_signal: np.ndarray | None = None
        self._b_phase: np.ndarray | None = None
        self._a_phase: np.ndarray | None = None

        # State
        self._state = AcquisitionState()
        self._phase_acc: dict = {}  # signal_phase history, grows each tick
        self._uw_acc: dict = {}  # unwrapped_phase history, grows each tick
        self._processing_tab = None   # set by MainController after construction
        self._btn_start_laser_clicked = False
        self._flip = [False] * NUM_CHANNELS
        self._subtract_sl = [False] * NUM_CHANNELS
        self._point_selected = {f"selected_{i}": -1 for i in range(NUM_CHANNELS)}
        self._elapsed_seconds = 0.0
        tab.btn_reset_time_clicked.connect(self._on_reset_time)

        # Elapsed time QTimer (separate, 1 s tick for LCD display)
        from PyQt6.QtCore import QTimer
        self._clock = QTimer()
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._tick_clock)

        self._populate_ui()
        self._connect_signals()
        self._last_unwrapped = {}
        self._phase_curves = {}
        self._point_curves_i0 = {}
        self._point_curves_ipi2 = {}

    def _reset_accumulators(self):
        self._phase_acc = {
            f"signal_{i}": [[] for _ in range(max(self._cal.n_points(i), 1))]
            for i in range(NUM_CHANNELS)
        }
        self._uw_acc = {
            f"unphase_{i}": [[] for _ in range(max(self._cal.n_points(i), 1))]
            for i in range(NUM_CHANNELS)
        }
        self._last_unwrapped = {
            f"unphase_{i}": [None for _ in range(max(self._cal.n_points(i), 1))]
            for i in range(NUM_CHANNELS)
        }

        self._phase_offset = {}

        self._state.unwrapped_phase_mean = {}
        self._state.unwrapped_phase_chart = {}
        self._state.time_unwrapped_phase_mean = {}
        self._state.point_series_x = {}
        self._state.point_series_y0 = {}
        self._state.point_series_ypi2 = {}

        # Runtime plot items for stable live updates
        self._phase_curves = {}
        self._point_curves_i0 = {}
        self._point_curves_ipi2 = {}

        # Recreate charts once on reset
        self._tab.chart_phase.clear()
        self._tab.chart_point.clear()
        self._tab.chart_point.addLegend(offset=(10, 10))
        self._tab.chart_phase.addLegend(offset=(10, 10))

    def _unwrap_incremental(self, arr: list, last_unwrapped: float | None) -> list:
        if not arr:
            return []
        a = np.asarray(arr, dtype=float)
        if last_unwrapped is None:
            return list(np.unwrap(a))
        seeded = np.concatenate(([last_unwrapped], a))
        unwrapped = np.unwrap(seeded)
        return list(unwrapped[1:])  # ← NO offset, NO np.angle(exp(...))
    # ----------------------------------------------------------- UI population
    def _populate_ui(self):
        for d in self._setup.devices:
            self._tab.cmb_device.addItem(d)
        self._tab.cmb_device.addItem(RELOAD_DEVICES)

        self._tab.spb_filter_phase.setValue(self._config.frequency_filter_phase)
        self._tab.btn_stop.setEnabled(False)
        self._tab.btn_save_current_data.setEnabled(False)

    # --------------------------------------------------------- signal wiring
    def _connect_signals(self):
        self._tab.btn_start_laser_clicked.connect(self._on_start_laser)
        self._tab.btn_stop_clicked.connect(self._on_stop)
        self._tab.btn_clear_clicked.connect(self._on_clear)
        self._tab.btn_save_current_data_clicked.connect(self._on_save_current_data)
        self._tab.btn_exit_clicked.connect(self._on_exit)
        self._tab.spb_filter_phase.valueChanged.connect(self._on_filter_phase_changed)
        self._tmr_read.timeout.connect(self._read_photodiode)
        self._tab.flip_changed.connect(self._on_flip_changed)
        self._tab.cmb_sr_selection_changed.connect(self._on_sr_selection_changed)
        self._tab.point_selection_changed.connect(self._on_point_selection_changed)

    def _on_flip_changed(self, channel: int, flipped: bool):
        self._flip[channel] = flipped
        self._update_charts()

    def _on_point_selection_changed(self, channel: int, selected: int):
        self._point_selected[f"selected_{channel}"] = selected
        self._update_charts()

    def _on_sr_selection_changed(self, index: int):
        self._update_charts()



    # ---------------------------------------------------- parameter changes
    def _on_filter_phase_changed(self, value: float):
        self._config.frequency_filter_phase = value
        if self._b_phase is not None:
            self._b_phase, self._a_phase = build_phase_filter(
                value, self._config.freq, self._config.time_read
            )

    # ---------------------------------------------------- laser start/stop
    def _on_start_laser(self):
        try:
            if not self._cal.is_done:
                self._tab.edt_message_log.setText(
                    "Run calibration first (Calibration tab)"
                )
                return

            self._daq.full_reset()

            self._daq.init_read_task()
            self._daq.init_write_task()
            self._daq.config_channel_read(
                self._setup.device_selected,
                self._config.limit_volt_device,
            )
            self._daq.config_timing_read(
                self._config.sample_rate_read,
                self._config.sample_rate_read * 1000,
            )
            self._daq.config_channel_write(
                self._setup.device_selected,
                self._config.limit_volt_device,
            )
            self._daq.config_timing_write(
                self._config.sample_rate_read,
                self._config.sample_rate_read * 2000,
            )
            self._daq.create_buffer_read(self._config.samples_per_channel_read)
            self._daq.config_stream_reader()
            self._daq.config_stream_writer()

            self._b_signal, self._a_signal = build_iup_idown_filter(
                self._config.peak_to_filter,
                self._config.freq,
                self._config.time_read,
                self._config.sample_rate_read,
            )
            self._b_phase, self._a_phase = build_phase_filter(
                self._config.frequency_filter_phase,
                self._config.freq,
                self._config.time_read,
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            default_name = f"{timestamp}_measurePhase.DAT"
            filepath = self._data.open_save_dialog(default_name)
            if not filepath:
                return
            if not self._data.open_phase_file(filepath):
                return

            self._state = AcquisitionState()
            self._elapsed_seconds = 0
            self._lcd_update(0, 0, 0)
            self._btn_start_laser_clicked = True
            self._reset_accumulators()

            self._tab.btn_start_laser.setEnabled(False)
            self._tab.btn_stop.setEnabled(True)
            self._tab.edt_message_log.setText("OK")

            self._daq.start_read_task()
            self._daq.write_data(self._setup.signal_modulation)
            self._daq.start_write_task()

            self._tmr_read.start()
            self._clock.start()

        except Exception as exc:
            self._log.log_exception("MeasurementController._on_start_laser", exc)
            self._tab.edt_message_log.setText("ERROR")

    def _on_stop(self):
        try:
            self._btn_start_laser_clicked = False
            self._tmr_read.stop()
            self._clock.stop()

            self._daq.full_reset()
            self._data.close_phase_file()

            self._tab.btn_start_laser.setEnabled(True)
            self._tab.btn_stop.setEnabled(False)
            self._tab.btn_save_current_data.setEnabled(False)
            self._tab.edt_message_log.setText("OK")
        except Exception as exc:
            self._log.log_exception("MeasurementController._on_stop", exc)

    def _on_stop_acquisition(self):
        self._state = AcquisitionState()
        self._tab.btn_save_current_data.setEnabled(False)

    def _on_restart(self):
        filepath = self._data.open_save_dialog()
        if not filepath:
            return
        if not self._data.open_phase_file(filepath):
            return
        self._state = AcquisitionState()
        self._reset_accumulators()
        self._elapsed_seconds = 0
        self._lcd_update(0, 0)
        self._tab.edt_message_log.setText("OK")

    def _on_save_current_data(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # includes seconds for snapshots
        default_name = f"{timestamp}_snapshot.DAT"
        self._data.save_current_snapshot(
            self._state.time_unwrapped_phase_mean,
            self._state.unwrapped_phase_chart,
            self._point_selected,
            default_name,
        )

    def _on_exit(self):
        self.request_exit.emit()

    # ---------------------------------------------------- clock display
    def _tick_clock(self):
        # If you have a timer interval in seconds, e.g. 1.0:
        self._elapsed_seconds += 1.0  # or += self._clk_interval
        total = int(self._elapsed_seconds)

        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60

        self._lcd_update(h, m, s)

    def _lcd_update(self, h: int, m: int, s: int):
        # Ensure h, m, s are ints when formatting
        self._tab.lcd_time.display(f"{int(h):02d}:{int(m):02d}:{int(s):02d}")

    # ------------------------------------------------- data acquisition loop
    def _read_photodiode(self):
        try:
            buf = self._daq.read_data()
            coeff = self._setup.coefficient_photodiode

            iup = {}
            idown = {}
            for i in range(NUM_CHANNELS):
                iup[i] = np.array(buf[i * 2]) / coeff
                idown[i] = np.array(buf[i * 2 + 1]) / coeff

            # Filter
            if self._b_signal is not None:
                for i in range(NUM_CHANNELS):
                    iup[i] = apply_filter(self._b_signal, self._a_signal, iup[i])
                    idown[i] = apply_filter(self._b_signal, self._a_signal, idown[i])

            # SR signal
            if self._setup.modulation_active:
                for i in range(NUM_CHANNELS):
                    sr = compute_sr_signal(iup[i], idown[i])
                    sr = center_sr_signal(sr)
                    self._state.signal_sr_one_second[f"SROneSecond_{i}"] = sr
                    self._state.signal_sr_one_second_chart[
                        f"SROneSecondChart_{i}"
                    ] = sr.copy()

            # Accumulate laser chart data
            step = self._config.time_read
            laser_buf = np.array(buf[15]) / self._config.conversion_factor_laser
            self._state.laser_current_chart = laser_buf.copy()
            self._state.time_laser_chart = np.around(
                np.arange(
                    self._state.init_time,
                    self._state.init_time + step,
                    step / max(len(laser_buf), 1),
                ), 6,
            )
            self._state.init_time += step

            # Phase calculation (only when calibration is done)
            if self._cal.is_done and self._b_phase is not None:
                self._compute_phase()

            self._update_charts()
            self.phase_updated.emit()
        except Exception as exc:
            import traceback
            print(f"ERROR _read_photodiode: {exc}")
            traceback.print_exc()  # ← mostra el tipus i línia exacta
            self._tab.edt_message_log.setText(f"ERROR: {exc}")
            self._log.log_exception("MeasurementController._read_photodiode", exc)

    def _compute_phase(self):
        try:
            n0 = self._cal.n_points(0)
            if n0 == 0:
                return

            freq = self._config.freq
            step_time = self._config.time_read
            sample_rate = self._config.sample_rate_read
            samples_per_period = int(sample_rate / freq)
            periods_per_step = int(freq * step_time)
            tick = max(1, int(freq * step_time))

            sig_ind0 = {f"signal_{i}": [] for i in range(NUM_CHANNELS)}
            sig_ind_pi2 = {f"signal_{i}": [] for i in range(NUM_CHANNELS)}

            for i in range(NUM_CHANNELS):
                n_pts = self._cal.n_points(i)
                has_cal = n_pts > 0
                effective_n_pts = n_pts if has_cal else 1
                sr = self._state.signal_sr_one_second.get(f"SROneSecond_{i}")
                if sr is None or len(sr) == 0:
                    continue

                for _ in range(effective_n_pts):
                    sig_ind0[f"signal_{i}"].append([])
                    sig_ind_pi2[f"signal_{i}"].append([])

                for period_idx in range(periods_per_step):
                    start = period_idx * samples_per_period
                    end = start + samples_per_period
                    sr_period = np.array(sr[start:end], dtype=float)
                    if len(sr_period) == 0:
                        continue
                    sr_period = sr_period - ((np.min(sr_period) + np.max(sr_period)) / 2.0)

                    if has_cal:
                        for n_idx in range(n_pts):
                            max_idx = int(self._cal.values_max_count[f"valuesMax_{i}"][n_idx])
                            min_idx = int(self._cal.values_min_count[f"valuesMin_{i}"][n_idx])
                            if max_idx < len(sr_period) and min_idx < len(sr_period):
                                sig_ind0[f"signal_{i}"][n_idx].append(float(sr_period[max_idx]))
                                sig_ind_pi2[f"signal_{i}"][n_idx].append(float(sr_period[min_idx]))
                    else:
                        max_idx = int(np.argmax(sr_period))
                        min_idx = int(np.argmin(sr_period))
                        sig_ind0[f"signal_{i}"][0].append(float(sr_period[max_idx]))
                        sig_ind_pi2[f"signal_{i}"][0].append(float(sr_period[min_idx]))

                for n_idx in range(effective_n_pts):
                    i0_win = sig_ind0[f"signal_{i}"][n_idx]
                    ipi2_win = sig_ind_pi2[f"signal_{i}"][n_idx]
                    if not i0_win or not ipi2_win:
                        continue
                    new_phases = [
                        float(np.arctan2(pi2, i0v))
                        for pi2, i0v in zip(ipi2_win, i0_win)
                    ]
                    self._phase_acc[f"signal_{i}"][n_idx].extend(new_phases)
                    last_uw = self._last_unwrapped[f"unphase_{i}"][n_idx]
                    new_uw = self._unwrap_incremental(new_phases, last_uw)
                    if new_uw:
                        self._uw_acc[f"unphase_{i}"][n_idx].extend(new_uw)
                        self._last_unwrapped[f"unphase_{i}"][n_idx] = new_uw[-1]

            self._state.signal_sr_ind0 = sig_ind0
            self._state.signal_sr_ind_pi2 = sig_ind_pi2

            t_current = self._state.init_time - self._config.time_read

            for i in range(NUM_CHANNELS):
                n_pts = self._cal.n_points(i)
                n_pts_ref = n_pts if n_pts > 0 else self._cal.n_points(0)
                ind0 = sig_ind0.get(f"signal_{i}", [])
                ind_pi2 = sig_ind_pi2.get(f"signal_{i}", [])

                if f"time_{i}" not in self._state.time_unwrapped_phase_mean:
                    self._state.time_unwrapped_phase_mean[f"time_{i}"] = []
                if f"unphase_{i}" not in self._state.unwrapped_phase_mean:
                    self._state.unwrapped_phase_mean[f"unphase_{i}"] = [
                        [] for _ in range(max(n_pts_ref, 1))
                    ]
                    self._state.unwrapped_phase_chart[f"unphase_{i}"] = [
                        [] for _ in range(max(n_pts_ref, 1))
                    ]

                # ← UN sol punt de temps per tick
                self._state.time_unwrapped_phase_mean[f"time_{i}"].append(t_current)

                effective_n_pts = max(n_pts, 1)
                for n_idx in range(effective_n_pts):
                    uw_all = self._uw_acc[f"unphase_{i}"][n_idx]
                    if not uw_all:
                        continue

                    tail = np.asarray(uw_all, dtype=float)
                    if self._b_phase is not None and len(tail) > 10:
                        tail = apply_filter(self._b_phase, self._a_phase, tail)
                    recent = tail[-periods_per_step:]
                    if len(recent) == 0:
                        continue
                    mean_val = float(np.mean(recent))

                    while len(self._state.unwrapped_phase_mean[f"unphase_{i}"]) <= n_idx:
                        self._state.unwrapped_phase_mean[f"unphase_{i}"].append([])
                        self._state.unwrapped_phase_chart[f"unphase_{i}"].append([])

                    # ← UN sol valor per tick (no extend amb 2 iguals)
                    self._state.unwrapped_phase_mean[f"unphase_{i}"][n_idx].append(mean_val)
                    self._state.unwrapped_phase_chart[f"unphase_{i}"][n_idx] = (
                        self._state.unwrapped_phase_mean[f"unphase_{i}"][n_idx].copy()
                    )

                    if n_idx < len(ind0) and ind0[n_idx]:
                        y0 = float(np.mean(ind0[n_idx][-tick:]))
                        ypi2 = float(np.mean(
                            ind_pi2[n_idx][-tick:] if n_idx < len(ind_pi2) and ind_pi2[n_idx] else [0]
                        ))
                        key0 = f"pt0_{i}_{n_idx}"
                        keypi2 = f"ptpi2_{i}_{n_idx}"
                        if key0 not in self._state.point_series_x:
                            self._state.point_series_x[key0] = []
                            self._state.point_series_y0[key0] = []
                        if keypi2 not in self._state.point_series_x:
                            self._state.point_series_x[keypi2] = []
                            self._state.point_series_ypi2[keypi2] = []
                        self._state.point_series_x[key0].append(t_current)
                        self._state.point_series_y0[key0].append(y0)
                        self._state.point_series_x[keypi2].append(t_current)
                        self._state.point_series_ypi2[keypi2].append(ypi2)

            if not self._tab.btn_save_current_data.isEnabled():
                self._tab.btn_save_current_data.setEnabled(True)

            phase_arrays = []
            for i in range(NUM_CHANNELS):
                sel = self._point_selected.get(f"selected_{i}", -1)
                arr_list = self._state.unwrapped_phase_mean.get(f"unphase_{i}", [[]])

                if 0 <= sel < len(arr_list):
                    phase_arrays.append(arr_list[sel])
                else:
                    phase_arrays.append([])  # no point selected → empty

            self._data.write_phase_row(
                self._state.time_unwrapped_phase_mean.get("time_0", []),
                phase_arrays,
            )

        except Exception as exc:
            import traceback
            print(f"ERROR _compute_phase: {exc}")
            traceback.print_exc()  # ← imprimeix la línia exacta que falla
            self._log.log_exception("MeasurementController._compute_phase", exc)

    # ------------------------------------------------------------ chart update
    def _update_charts(self):
        try:
            from views.tab_measure import CHANNEL_COLORS

            # ---------------- SR Signal chart ----------------
            self._tab.chart_sr.clear()
            sel_sr = self._tab.cmb_sr_selection.currentIndex()
            channels_to_plot = range(NUM_CHANNELS) if sel_sr == 0 else [sel_sr - 1]

            for i in channels_to_plot:
                sr = self._state.signal_sr_one_second_chart.get(f"SROneSecondChart_{i}")
                if sr is not None and len(sr) > 0:
                    t = self._state.time_laser_chart
                    if len(t) != len(sr):
                        t = np.linspace(
                            self._state.init_time - self._config.time_read,
                            self._state.init_time,
                            len(sr),
                            endpoint=False,
                        )
                    self._tab.chart_sr.plot(t, sr, pen=CHANNEL_COLORS[i])

            # ---------------- SR Points chart ----------------
            if self._cal.is_done:
                active_point_keys_i0 = set()
                active_point_keys_ipi2 = set()

                sel_sr = self._tab.cmb_sr_selection.currentIndex()
                channels_to_plot = range(NUM_CHANNELS) if sel_sr == 0 else [sel_sr - 1]

                for i in channels_to_plot:
                    n_pts = max(self._cal.n_points(i), 1)
                    sel = self._point_selected.get(f"selected_{i}", -1)

                    # If no point selected or out of range → no curves for this channel
                    if sel < 0 or sel >= n_pts:
                        continue

                    p_idx = sel
                    key0 = f"pt0_{i}_{p_idx}"
                    keypi2 = f"ptpi2_{i}_{p_idx}"

                    xs0 = self._state.point_series_x.get(key0, [])
                    y0s = self._state.point_series_y0.get(key0, [])
                    xsp = self._state.point_series_x.get(keypi2, [])
                    ypi2s = self._state.point_series_ypi2.get(keypi2, [])

                    n0 = min(len(xs0), len(y0s))
                    np2 = min(len(xsp), len(ypi2s))

                    # I0 curve at the selected calibration point
                    if key0 not in self._point_curves_i0:
                        name0 = f"CH {i + 1} P{p_idx + 1}"
                        self._point_curves_i0[key0] = self._tab.chart_point.plot(
                            [], [],
                            pen=pg.mkPen(color=CHANNEL_COLORS[i], width=2),
                            name=name0
                        )
                    self._point_curves_i0[key0].setData(xs0[:n0], y0s[:n0] if n0 > 0 else [])
                    active_point_keys_i0.add(key0)

                    # Iπ/2 curve at the same calibration point (dashed)
                    if keypi2 not in self._point_curves_ipi2:
                        namepi2 = f"CH {i + 1} P{p_idx + 1} (π/2)"
                        self._point_curves_ipi2[keypi2] = self._tab.chart_point.plot(
                            [], [],
                            pen=pg.mkPen(
                                color=CHANNEL_COLORS[i],
                                width=1,
                                style=Qt.PenStyle.DashLine
                            ),
                            name=namepi2
                        )
                    self._point_curves_ipi2[keypi2].setData(xsp[:np2], ypi2s[:np2] if np2 > 0 else [])
                    active_point_keys_ipi2.add(keypi2)

                # Clear curves for channels/points that are no longer selected
                for key, curve in self._point_curves_i0.items():
                    if key not in active_point_keys_i0:
                        curve.setData([], [])

                for key, curve in self._point_curves_ipi2.items():
                    if key not in active_point_keys_ipi2:
                        curve.setData([], [])

            # ---------------- Phase Shift chart ----------------
            if self._cal.is_done:
                active_phase_keys = set()

                sel_sr = self._tab.cmb_sr_selection.currentIndex()
                channels_to_plot = range(NUM_CHANNELS) if sel_sr == 0 else [sel_sr - 1]

                for i in channels_to_plot:
                    t = self._state.time_unwrapped_phase_mean.get(f"time_{i}", [])
                    chart_data = self._state.unwrapped_phase_chart.get(f"unphase_{i}", [[]])
                    sel = self._point_selected.get(f"selected_{i}", -1)

                    if sel < 0 or sel >= len(chart_data):
                        continue  # no point selected for this channel

                    p_idx = sel
                    arr = chart_data[p_idx]
                    n = min(len(t), len(arr))
                    if n < 1:
                        continue

                    t_plot = list(t)[:n]
                    a_plot = list(arr)[:n]

                    offset_key = f"{i}_{p_idx}"
                    if offset_key not in self._phase_offset:
                        self._phase_offset[offset_key] = a_plot[0]
                    offset = self._phase_offset[offset_key]

                    a_zeroed = [v - offset for v in a_plot]
                    data = [-v for v in a_zeroed] if self._flip[i] else a_zeroed

                    phase_key = f"phase_{i}_{p_idx}"
                    if phase_key not in self._phase_curves:
                        label = f"CH {i + 1} P{p_idx + 1}"
                        self._phase_curves[phase_key] = self._tab.chart_phase.plot(
                            [], [],
                            pen=pg.mkPen(color=CHANNEL_COLORS[i], width=2),
                            name=label
                        )

                    self._phase_curves[phase_key].setData(t_plot, data)
                    active_phase_keys.add(phase_key)

                for key, curve in self._phase_curves.items():
                    if key not in active_phase_keys:
                        curve.setData([], [])

        except Exception as exc:
            import traceback
            print(f"ERROR _update_charts: {exc}")
            traceback.print_exc()
            self._log.log_exception("MeasurementController._update_charts", exc)

    def notify_calibration_done(self):
        """Called by MainController after CalibrationController finishes."""
        # Update combos according to calibration (this will default to Point 1)
        self._tab.refresh_point_selectors(self._cal)

        # Sync controller state: select Point 1 for every channel that has points
        for ch in range(NUM_CHANNELS):
            if self._cal.n_points(ch) > 0:
                self._point_selected[f"selected_{ch}"] = 0  # Point 1
            else:
                self._point_selected[f"selected_{ch}"] = -1  # None

        # Redraw charts with the new defaults
        self._update_charts()

        self._tab.edt_message_log.setText("Calibration done — ready to measure")

    def refresh_combos(self):
        """Force device combo to re-render after the window is shown."""
        self._tab.cmb_device.blockSignals(True)
        self._tab.cmb_device.clear()
        for d in self._setup.devices:
            self._tab.cmb_device.addItem(d)
        self._tab.cmb_device.addItem(RELOAD_DEVICES)
        self._tab.cmb_device.setCurrentIndex(0)
        self._tab.cmb_device.blockSignals(False)

    def _on_clear(self):
        try:
            for chart in (self._tab.chart_point,
                          self._tab.chart_sr,
                          self._tab.chart_phase):
                chart.clear()

            self._phase_curves = {}
            self._point_curves_i0 = {}
            self._point_curves_ipi2 = {}
            self._phase_offset = {}

            self._tab.chart_point.addLegend(offset=(10, 10))
            self._tab.chart_phase.addLegend(offset=(10, 10))

            self._tab.edt_message_log.setText("OK")
        except Exception as exc:
            self._log.log_exception("MeasurementController._on_clear", exc)

    def _on_timeout(self):
        self._elapsed_seconds += 1.0
        self._update_time_display()

    def _on_reset_time(self):
        self._elapsed_seconds = 0.0
        self._lcd_update(0, 0, 0)

    def _update_time_display(self):
        # format as HH:MM:SS
        total = int(self._elapsed_seconds)
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        self._tab.lcd_time.display(f"{h:02d}:{m:02d}:{s:02d}")