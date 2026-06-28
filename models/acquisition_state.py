# models/acquisition_state.py
from dataclasses import dataclass, field
import numpy as np

NUM_CHANNELS = 7


def _empty_channel_dict(suffix: str) -> dict:
    return {f"{suffix}_{i}": [] for i in range(NUM_CHANNELS)}


@dataclass
class AcquisitionState:
    """All live data buffers for one acquisition session.
    Reset by replacing the instance: self._state = AcquisitionState()"""

    init_time: float = 0.0
    btn_stop_clicked: int = 0
    btn_stop_acquisition_clicked: int = 0

    point_series_x: dict = field(default_factory=dict)
    point_series_y0: dict = field(default_factory=dict)
    point_series_ypi2: dict = field(default_factory=dict)

    # Chart display buffers
    data_iup_chart: dict = field(
        default_factory=lambda: _empty_channel_dict("iUPChart")
    )
    data_idown_chart: dict = field(
        default_factory=lambda: _empty_channel_dict("iDOWNChart")
    )
    time_photodiode_chart: np.ndarray = field(
        default_factory=lambda: np.array([])
    )
    time_laser_chart: np.ndarray = field(
        default_factory=lambda: np.array([])
    )
    laser_current_chart: np.ndarray = field(
        default_factory=lambda: np.array([])
    )

    # SR signal (one acquisition window)
    signal_sr_one_second: dict = field(
        default_factory=lambda: _empty_channel_dict("SROneSecond")
    )
    signal_sr_one_second_chart: dict = field(
        default_factory=lambda: _empty_channel_dict("SROneSecondChart")
    )

    # Phase data (populated after calibration)
    signal_sr_ind0: dict = field(default_factory=dict)
    signal_sr_ind_pi2: dict = field(default_factory=dict)
    signal_phase: dict = field(default_factory=dict)
    unwrapped_phase: dict = field(default_factory=dict)
    unwrapped_phase_mean: dict = field(default_factory=dict)
    unwrapped_phase_chart: dict = field(default_factory=dict)
    time_unwrapped_phase: dict = field(
        default_factory=lambda: {f"time_{i}": [] for i in range(NUM_CHANNELS)}
    )
    time_unwrapped_phase_mean: dict = field(
        default_factory=lambda: {f"time_{i}": [] for i in range(NUM_CHANNELS)}
    )