# controllers/measurement_setup_controller.py
from models.measurement_config import MeasurementConfig
from core.daq.device_discovery import get_available_devices, NO_DEVICE
from core.signal.signal_generation import generate_sine, generate_sawtooth, generate_none, laser_volt_limits
from services.logger_service import LoggerService
import numpy as np

SIGNAL_SINE = "Sine"
SIGNAL_SAWTOOTH = "Sawtooth"
SIGNAL_NONE = "None"

CURRENT_RANGES = ["10 mA", "1 mA", "100 uA", "10 uA", "1 uA", "100 nA"]
CONVERSION_COEFFICIENTS = [
    -10000,       # 10 mA   → R ≈ 1e4 Ω
    -100000,      # 1 mA    → R ≈ 1e5 Ω
    -1000000,     # 100 uA  → R ≈ 1e6 Ω
    -10000000,    # 10 uA   → R ≈ 1e7 Ω  ← matches hardware measurement
    -100000000,   # 1 uA    → R ≈ 1e8 Ω
    -1000000000,  # 100 nA  → R ≈ 1e9 Ω
]


class MeasurementSetupController:
    """Manages device selection, parameter spinboxes, and modulation
    signal recalculation. Shared between calibration and measure tabs."""

    def __init__(self, config: MeasurementConfig, logger: LoggerService):
        self.config = config
        self._log = logger
        self.devices: list[str] = []
        self.device_selected: str = NO_DEVICE
        self.signal_modulation: np.ndarray = np.array([])
        self.modulation_active: bool = False
        self.index_signal_mod_selected: int = 1   # default: Sine
        self.coefficient_photodiode: float = CONVERSION_COEFFICIENTS[3]

        # Volt limits (derived from config)
        self._volt_min: float = 0.0
        self._volt_max: float = 0.0
        self._recalculate_volt_limits()
        self._rebuild_signal()
        self.reload_devices()

    # ------------------------------------------------------------ device setup
    def reload_devices(self) -> list[str]:
        try:
            self.devices = get_available_devices()
            if self.devices:
                self.device_selected = self.devices[0]
            else:
                self.device_selected = NO_DEVICE
            return self.devices
        except Exception as exc:
            self.device_selected = NO_DEVICE
            self.devices = []
            self._log.log_exception("MeasurementSetupController.reload_devices", exc)
            return []

    def select_device(self, index: int):
        try:
            if index < len(self.devices):
                self.device_selected = self.devices[index]
        except Exception as exc:
            self._log.log_exception("MeasurementSetupController.select_device", exc)

    # ---------------------------------------------------- parameter setters
    def set_frequency(self, freq: int):
        try:
            if freq >= 10:
                self.config.freq = freq
                self._rebuild_signal()
        except Exception as exc:
            self._log.log_exception("MeasurementSetupController.set_frequency", exc)

    def set_laser_current(self, value: float):
        try:
            self.config.laser_current_set = value
            self._recalculate_volt_limits()
            self._rebuild_signal()
        except Exception as exc:
            self._log.log_exception("MeasurementSetupController.set_laser_current", exc)

    def set_laser_current_min(self, value: float):
        try:
            self.config.limit_laser_current[0] = value
            self._recalculate_volt_limits()
            self._rebuild_signal()
        except Exception as exc:
            self._log.log_exception("MeasurementSetupController.set_laser_current_min", exc)

    def set_laser_current_max(self, value: float):
        try:
            self.config.limit_laser_current[1] = value
            self._recalculate_volt_limits()
            self._rebuild_signal()
        except Exception as exc:
            self._log.log_exception("MeasurementSetupController.set_laser_current_max", exc)

    def set_modulation_type(self, index: int):
        try:
            if index in (0, 1, 2):
                self.index_signal_mod_selected = index
                self._rebuild_signal()
        except Exception as exc:
            self._log.log_exception("MeasurementSetupController.set_modulation_type", exc)

    def set_current_range(self, index: int):
        try:
            if 0 <= index < len(CONVERSION_COEFFICIENTS):
                self.coefficient_photodiode = CONVERSION_COEFFICIENTS[index]
        except Exception as exc:
            self._log.log_exception("MeasurementSetupController.set_current_range", exc)

    # --------------------------------------------------- internal helpers
    def _recalculate_volt_limits(self):
        self._volt_min, self._volt_max = laser_volt_limits(
            self.config.limit_laser_current,
            self.config.laser_current_set,
            self.config.conversion_factor_laser,
        )

    def _rebuild_signal(self):
        sr = self.config.sample_rate_read
        if self.index_signal_mod_selected == 0:   # Sawtooth
            self.signal_modulation = generate_sawtooth(
                sr, self.config.freq, self._volt_min, self._volt_max
            )
            self.modulation_active = True
        elif self.index_signal_mod_selected == 1:  # Sine
            self.signal_modulation = generate_sine(
                sr, self.config.freq, self._volt_min, self._volt_max
            )
            self.modulation_active = True
        else:                                       # None
            self.signal_modulation = generate_none(sr)
            self.modulation_active = False