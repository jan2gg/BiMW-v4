# core/signal/sr_processor.py
import numpy as np
from scipy import signal, stats
from core.signal.signal_filter import apply_filter

NUM_CHANNELS = 7


def compute_sr_signal(
    iup: np.ndarray,
    idown: np.ndarray,
) -> np.ndarray:
    """Compute the normalised SR signal from Iup and Idown.
    Returns values in the range [-100, 100] (percent)."""
    denominator = iup + idown
    # Avoid division by zero
    denominator = np.where(denominator == 0, np.finfo(float).eps, denominator)
    return 100.0 * ((iup - idown) / denominator)


def center_sr_signal(sr: np.ndarray) -> np.ndarray:
    """Remove the DC offset so the signal is centred around zero."""
    return sr - ((np.max(sr) + np.min(sr)) / 2)


def find_zero_crossings_and_peaks(
    sr_period: np.ndarray,
) -> list[list]:
    """Find zero crossings and the adjacent peak index for one SR period.
    Mirrors the inner logic of the old calibration() method.
    Returns a list of [peak_index, zero_cross_index, zero_cross_value]."""
    results = []
    # Find the index of the positive peak
    peak_aux = 0
    for x in signal.find_peaks(sr_period)[0]:
        if sr_period[x] > sr_period[peak_aux]:
            peak_aux = x

    # Walk each zero crossing
    zero_crossings = np.where(np.diff(np.sign(sr_period)))[0]
    for x in zero_crossings:
        if np.abs(sr_period[x]) <= np.abs(sr_period[x + 1]):
            results.append([peak_aux, x, sr_period[x]])
        else:
            results.append([peak_aux, x + 1, sr_period[x + 1]])

    return results


def select_calibration_points(
    index_data: dict,
) -> tuple[dict, dict]:
    values_min_count = {}
    values_max_count = {}

    for i in range(NUM_CHANNELS):
        channel_key = f"index_{i}"
        ind_minimum: list[list] = []

        for second in index_data[channel_key]:
            for period in second:
                if len(period) == 0:
                    continue
                if len(ind_minimum) == 0:
                    minimum_empty = True
                else:
                    minimum_empty = False

                for x_idx, crossing in enumerate(period):
                    if minimum_empty:
                        ind_minimum.append([])
                    if x_idx <= len(ind_minimum) - 1:
                        ind_minimum[x_idx].append(crossing[1])

        if len(ind_minimum) == 0:
            values_min_count[f"valuesMin_{i}"] = []
            values_max_count[f"valuesMax_{i}"] = []
            continue


        min_count = []
        for group in ind_minimum:
            consensus = max(set(group), key=group.count)
            min_count.append(int(consensus))  # one value per n_idx, NOT replicated

        values_min_count[f"valuesMin_{i}"] = min_count

        ind_maximum: list[list] = [[] for _ in ind_minimum]
        for second in index_data[channel_key]:
            for period in second:
                for x_idx, crossing in enumerate(period):
                    if x_idx <= len(ind_minimum) - 1:
                        if crossing[1] == min_count[x_idx]:
                            ind_maximum[x_idx].append(crossing[0])

        max_count = []
        for group in ind_maximum:
            if group:
                consensus_max = max(set(group), key=group.count)
            else:
                consensus_max = 0
            max_count.append(int(consensus_max))

        values_max_count[f"valuesMax_{i}"] = max_count

    return values_min_count, values_max_count


def calculate_phase_unwrapped(
    sr_one_second: dict,
    values_min_count: dict,
    values_max_count: dict,
    freq: float,
    step_time: float,
    sample_rate_read: int,
    b_phase: np.ndarray,
    a_phase: np.ndarray,
) -> tuple[dict, dict, dict, dict]:
    """Compute unwrapped phase for all channels and all calibration points.
    Returns (signal_ind0, signal_ind_pi2, signal_phase, unwrapped_phase)."""
    signal_ind0: dict = {f"signal_{i}": [] for i in range(NUM_CHANNELS)}
    signal_ind_pi2: dict = {f"signal_{i}": [] for i in range(NUM_CHANNELS)}
    signal_phase_out: dict = {f"signal_{i}": [] for i in range(NUM_CHANNELS)}
    unwrapped_phase: dict = {f"unphase_{i}": [] for i in range(NUM_CHANNELS)}

    for i in range(NUM_CHANNELS):
        n_points = len(values_min_count[f"valuesMin_{i}"])
        for _ in range(n_points):
            signal_ind0[f"signal_{i}"].append([])
            signal_ind_pi2[f"signal_{i}"].append([])
            signal_phase_out[f"signal_{i}"].append([])
            unwrapped_phase[f"unphase_{i}"].append([])

        sr = sr_one_second[f"SROneSecond_{i}"]
        samples_per_period = int(sample_rate_read / freq)

        for period_idx in range(int(freq * step_time)):
            start = period_idx * samples_per_period
            end = start + samples_per_period
            sr_period = np.array(sr[start:end].copy())
            sr_period = sr_period - ((np.min(sr_period) + np.max(sr_period)) / 2)

            for n_idx in range(n_points):
                max_idx = int(values_max_count[f"valuesMax_{i}"][n_idx])
                min_idx = int(values_min_count[f"valuesMin_{i}"][n_idx])
                signal_ind0[f"signal_{i}"][n_idx].append(
                    sr_period[max_idx].copy()
                )
                signal_ind_pi2[f"signal_{i}"][n_idx].append(
                    sr_period[min_idx].copy()
                )

        for n_idx in range(n_points):
            window = int(freq * step_time)
            i0 = signal_ind0[f"signal_{i}"][n_idx][-window:]
            i_pi2 = signal_ind_pi2[f"signal_{i}"][n_idx][-window:]

            phases = [
                np.arctan2(pi2, i0_val)
                for pi2, i0_val in zip(i_pi2, i0)
            ]
            signal_phase_out[f"signal_{i}"][n_idx].extend(phases)
            uw = np.unwrap(signal_phase_out[f"signal_{i}"][n_idx].copy())
            uw = apply_filter(b_phase, a_phase, uw)
            unwrapped_phase[f"unphase_{i}"][n_idx] = uw

    return signal_ind0, signal_ind_pi2, signal_phase_out, unwrapped_phase