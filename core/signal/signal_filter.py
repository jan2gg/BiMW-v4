# core/signal/signal_filter.py
import numpy as np
from scipy import signal


def build_iup_idown_filter(
    peak_to_filter: int,
    freq: float,
    step_time: float,
    sample_rate_read: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Butterworth low-pass filter for Iup/Idown photodiode signals.
    Returns (b, a) coefficients."""
    wn = (peak_to_filter * (freq * step_time)) + 2
    b, a = signal.butter(
        N=10,
        Wn=wn,
        btype="low",
        analog=False,
        output="ba",
        fs=(sample_rate_read * step_time),
    )
    return b, a


def build_phase_filter(
    frequency_filter_phase: float,
    freq: float,
    step_time: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Butterworth low-pass filter for the unwrapped phase signal.
    Returns (b, a) coefficients."""
    b, a = signal.butter(
        N=1,
        Wn=frequency_filter_phase,
        btype="low",
        analog=False,
        output="ba",
        fs=(freq * step_time),
    )
    return b, a


def apply_filter(
    b: np.ndarray,
    a: np.ndarray,
    data: np.ndarray,
) -> np.ndarray:
    """Apply a zero-phase forward-backward filter (filtfilt) to data."""
    return signal.filtfilt(b, a, data.copy())