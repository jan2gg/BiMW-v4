# models/measurement_config.py
from dataclasses import dataclass, field

@dataclass
class MeasurementConfig:
    freq: int = 10                          # Hz
    time_read: float = 4.0                  # seconds per acquisition
    laser_current_set: float = 150.0        # mA
    limit_laser_current: list = field(default_factory=lambda: [130, 170])
    limit_volt_device: list = field(default_factory=lambda: [-10, 10])
    current_laser_controller_max: float = 500.0  # mA
    time_calibration: int = 30              # seconds
    peak_to_filter: int = 10
    frequency_filter_phase: float = 0.05   # Hz
    samples_chart: int = 500
    sample_rate_couple: int = 960
    # Channel mapping constants — NI USB-6361 Dev1
    # ai0–ai13 : photodiode pairs (channels 0–6, each pair is i*2 and i*2+1)
    # ai14      : unused
    # ai15      : laser current feedback
    LASER_CURRENT_CHANNEL = 15
    PHOTODIODE_CHANNELS = 14

    @property
    def sample_rate_read(self) -> int:
        return int(self.freq * 250)

    @property
    def samples_per_channel_read(self) -> int:
        return int(self.sample_rate_read * self.time_read)

    @property
    def conversion_factor_laser(self) -> float:
        return self.limit_volt_device[1] / self.current_laser_controller_max