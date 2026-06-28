# core/signal/signal_generation.py
import numpy as np
from scipy import signal


def generate_sine(
    sample_rate: int,
    freq: float,
    volt_min: float,
    volt_max: float,
) -> np.ndarray:
    """Generate one period of a sine wave scaled between volt_min and volt_max."""
    amp = abs(volt_min - volt_max) / 2
    offset = volt_max - ((volt_max - volt_min) / 2)
    t = np.arange(start=0, stop=1, step=1 / sample_rate)
    sine = np.sin(t * freq * 2 * np.pi)
    return offset + (sine * amp)


def generate_sawtooth(
    sample_rate: int,
    freq: float,
    volt_min: float,
    volt_max: float,
) -> np.ndarray:
    """Generate one period of a sawtooth wave scaled between volt_min and volt_max."""
    amp = abs(volt_min - volt_max) / 2
    offset = volt_max - ((volt_max - volt_min) / 2)
    t = np.arange(start=0, stop=1, step=1 / sample_rate)
    saw = signal.sawtooth(t * freq * 2 * np.pi)
    return offset + (saw * amp)


def generate_none(sample_rate: int) -> np.ndarray:
    """Return a flat zero signal (laser off)."""
    return np.zeros(sample_rate)


def laser_volt_limits(
    limit_laser_current: list[float],
    laser_current_set: float,
    conversion_factor: float,
    offset_correction: float = 0.0,   # mA correction measured at runtime
) -> tuple[float, float]:
    volt_min = (limit_laser_current[0] - laser_current_set - offset_correction) * conversion_factor
    volt_max = (limit_laser_current[1] - laser_current_set - offset_correction) * conversion_factor

    return volt_min, volt_max

def generate_constant(
    sample_rate: int,
    laser_current_set: float,
    conversion_factor: float,
) -> np.ndarray:
    """Return a flat signal corresponding to laser_current_set mA."""
    volt = laser_current_set * conversion_factor
    return np.full(sample_rate, volt)