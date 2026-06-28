# models/calibration_result.py
from dataclasses import dataclass, field
import numpy as np

NUM_CHANNELS = 7


@dataclass
class CalibrationResult:
    """Stores the output of a completed calibration run.
    Passed from CalibrationController to MeasurementController."""

    # Consensus zero-crossing (quadrature) indices per channel per point
    values_min_count: dict = field(default_factory=dict)
    # Consensus peak indices per channel per point
    values_max_count: dict = field(default_factory=dict)
    # Which chart point slots were found per channel
    point_selected_array: dict = field(default_factory=dict)
    # Whether calibration has been completed at least once
    is_done: bool = False

    def n_points(self, channel: int) -> int:
        """How many calibration points were found for a given channel."""
        return len(self.values_min_count.get(f"valuesMin_{channel}", []))

    def reset(self):
        self.values_min_count = {}
        self.values_max_count = {}
        self.point_selected_array = {}
        self.is_done = False