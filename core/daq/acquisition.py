# core/daq/acquisition.py
import numpy as np

try:
    import nidaqmx
    import nidaqmx.constants
    import nidaqmx.stream_readers
    import nidaqmx.stream_writers
    NIDAQMX_AVAILABLE = True
except ImportError:
    NIDAQMX_AVAILABLE = False


class AcquisitionTask:
    """Wraps NI-DAQ read and write tasks.
    All public methods are safe to call even without hardware —
    they return empty arrays or silently no-op."""

    def __init__(self):
        self._read_task = None
        self._write_task = None
        self._stream_reader = None
        self._stream_writer = None
        self._buffer_read: np.ndarray | None = None
        self._buffer_couple: np.ndarray | None = None

    # ------------------------------------------------------------------ setup
    def init_read_task(self):
        if not NIDAQMX_AVAILABLE:
            return
        if self._read_task is not None:
            self.close_read_task()
        self._read_task = nidaqmx.Task()

    # In init_write_task — replace the existing method entirely:
    def init_write_task(self):
        if not NIDAQMX_AVAILABLE:
            return
        # Close any existing task first to prevent resource leaks
        if self._write_task is not None:
            self.close_write_task()
        self._write_task = nidaqmx.Task()

    def config_channel_read(self, device: str, volt_limits: list[float]):
        if not self._read_task:
            return
        # ai0–ai13: 7 photodiode pairs (14 channels)
        # ai14:     unused
        # ai15:     laser current feedback
        for i in range(16):
            self._read_task.ai_channels.add_ai_voltage_chan(
                f"{device}/ai{i}",
                terminal_config=nidaqmx.constants.TerminalConfiguration.RSE,
                min_val=volt_limits[0],
                max_val=volt_limits[1],
            )

    def config_channel_write(self, device: str, volt_limits: list[float]):
        if not self._write_task:
            return
        self._write_task.ao_channels.add_ao_voltage_chan(
            f"{device}/ao0",
            min_val=volt_limits[0],
            max_val=volt_limits[1],
        )

    def config_timing_read(self, sample_rate: int, buffer_size: int):
        if not self._read_task:
            return
        self._read_task.timing.cfg_samp_clk_timing(
            rate=sample_rate,
            sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
            samps_per_chan=buffer_size,
        )

    def config_timing_write(self, sample_rate: int, buffer_size: int):
        if not self._write_task:
            return
        self._write_task.timing.cfg_samp_clk_timing(
            rate=sample_rate,
            sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
            samps_per_chan=buffer_size,
        )

    def config_stream_reader(self):
        if not self._read_task:
            return
        self._stream_reader = nidaqmx.stream_readers.AnalogMultiChannelReader(
            self._read_task.in_stream
        )

    def config_stream_writer(self):
        if not self._write_task:
            return
        self._stream_writer = nidaqmx.stream_writers.AnalogSingleChannelWriter(
            self._write_task.out_stream
        )

    def create_buffer_read(self, samples_per_channel: int):
        self._buffer_read = np.zeros((16, samples_per_channel))

    def create_buffer_couple(self, sample_rate_couple: int):
        self._buffer_couple = np.zeros((16, sample_rate_couple))

    # --------------------------------------------------------------- control
    def start_read_task(self):
        if self._read_task:
            self._read_task.start()

    def stop_read_task(self):
        if self._read_task is not None:
            try:
                self._read_task.stop()
            except Exception:
                pass

    def start_write_task(self):
        if self._write_task:
            self._write_task.start()

    def stop_write_task(self):
        if self._write_task is not None:
            try:
                self._write_task.stop()
            except Exception:
                pass

    def close_read_task(self):
        if self._read_task is not None:
            try:
                self._read_task.stop()
            except Exception:
                pass
            try:
                self._read_task.close()
            except Exception:
                pass
            self._read_task = None
            self._stream_reader = None
            self._buffer_read = None

    def close_write_task(self):
        if self._write_task is not None:
            try:
                self._write_task.stop()
            except Exception:
                pass
            try:
                self._write_task.close()
            except Exception:
                pass
            self._write_task = None
            self._stream_writer = None

    def restart_read_task(self):
        self.close_read_task()

    def restart_write_task(self):
        self.close_write_task()

    def full_reset(self):
        """Stop, close, and nullify all tasks. Call between calibration and measurement."""
        self.close_read_task()
        self.close_write_task()
        print("AcquisitionTask: full reset complete")

    # ------------------------------------------------------------------- I/O
    def read_data(self) -> np.ndarray:
        if not self._stream_reader or self._buffer_read is None:
            return np.zeros((16, 1))
        self._stream_reader.read_many_sample(
            self._buffer_read,
            number_of_samples_per_channel=self._buffer_read.shape[1],
        )
        return self._buffer_read

    def read_couple_data(self) -> np.ndarray:
        if not self._stream_reader or self._buffer_couple is None:
            return np.zeros((16, 1))
        self._stream_reader.read_many_sample(
            self._buffer_couple,
            number_of_samples_per_channel=self._buffer_couple.shape[1],
        )
        return self._buffer_couple

    def write_data(self, signal: np.ndarray):
        if self._stream_writer is not None:
            self._stream_writer.write_many_sample(signal)