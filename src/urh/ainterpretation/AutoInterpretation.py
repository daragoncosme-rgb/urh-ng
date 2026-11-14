import itertools
import math
from collections import Counter

import numpy as np

from urh.ainterpretation import Wavelet
from urh.cythonext import auto_interpretation as c_auto_interpretation
from urh.cythonext import signal_functions
from urh.cythonext import util
from urh.signalprocessing.IQArray import IQArray


def max_without_outliers(data: np.ndarray, z=3):
    if len(data) == 0:
        return None

    return np.max(data[abs(data - np.mean(data)) <= z * np.std(data)])


def min_without_outliers(data: np.ndarray, z=2):
    if len(data) == 0:
        return None

    return np.min(data[abs(data - np.mean(data)) <= z * np.std(data)])


def get_most_frequent_value(values: list):
    """
    Return the most frequent value in list.
    If there is no unique one, return the maximum of the most frequent values

    :param values:
    :return:
    """
    if len(values) == 0:
        return None

    most_common = Counter(values).most_common()
    result, max_count = most_common[0]
    for value, count in most_common:
        if count < max_count:
            return result
        else:
            result = value

    return result


def most_common(values: list):
    """
    Return the most common value in a list. In case of ties, return the value that appears first in list
    :param values:
    :return:
    """
    counter = Counter(values)
    return max(values, key=counter.get)


def detect_noise_level(magnitudes):
    if len(magnitudes) <= 3:
        return 0

    # 1% for best accuracy and performance for large signals
    chunksize_percent = 1
    chunksize = max(1, int(len(magnitudes) * chunksize_percent / 100))

    chunks = [
        magnitudes[i - chunksize : i]
        for i in range(len(magnitudes), 0, -chunksize)
        if i - chunksize >= 0
    ]

    mean_values = np.fromiter(
        (np.mean(chunk) for chunk in chunks), dtype=np.float32, count=len(chunks)
    )
    minimum, maximum = util.minmax(mean_values)
    if maximum == 0 or minimum / maximum > 0.9:
        # Mean values are very close to each other, so there is probably no noise in the signal
        return 0

    # Get all indices for values which are in range of 10% of minimum mean value
    indices = np.nonzero(mean_values <= 1.1 * np.min(mean_values))[0]

    try:
        result = np.max([np.max(chunks[i]) for i in indices if len(chunks[i]) > 0])
    except ValueError:
        return 0

    # Round up to fourth digit
    return math.ceil(result * 10000) / 10000


def smooth_magnitudes(magnitudes: np.ndarray, window: int = 8) -> np.ndarray:
    """Moving average of the magnitudes (float32, same length)."""
    if window <= 1 or len(magnitudes) < 4 * window:
        return magnitudes
    # moving average via cumulative sum: O(n) for any window
    c = np.cumsum(magnitudes, dtype=np.float64)
    c = np.concatenate(([0.0], c))
    avg = ((c[window:] - c[:-window]) / window).astype(np.float32)
    # same length and alignment as the input (pad with the edge values)
    left = window // 2
    right = len(magnitudes) - len(avg) - left
    return np.concatenate(
        (np.full(left, avg[0], np.float32), avg, np.full(right, avg[-1], np.float32))
    )


def estimate_weak_ook(magnitudes: np.ndarray, noise: float, window: int = 32):
    """
    Bit length, center and tolerance of a weak on/off keyed signal.

    The magnitudes are smoothed and turned into on/off with hysteresis, so the
    pulses are not split by samples that dip into the noise. Returns None if
    no clear pulse lengths are found.

    :return: (bit_length, center in magnitude units, tolerance) or None
    """
    smoothed = smooth_magnitudes(magnitudes, window)
    above_noise = smoothed[smoothed > 2 * noise]
    if len(above_noise) < 10 * window:
        return None
    level = float(np.median(above_noise))
    high = noise + 0.5 * (level - noise)
    low = noise + 0.2 * (level - noise)

    # hysteresis: keep the last decided state between the two thresholds
    decided = np.flatnonzero((smoothed > high) | (smoothed < low))
    if len(decided) < 2:
        return None
    # forward fill the last decided state
    last = np.full(len(smoothed), -1, dtype=np.int64)
    last[decided] = decided
    np.maximum.accumulate(last, out=last)
    on = (smoothed[np.maximum(last, 0)] > high) & (last >= 0)

    edges = np.flatnonzero(np.diff(on.astype(np.int8)))
    if len(edges) < 4:
        return None
    runs = np.diff(edges)
    first_is_on = bool(on[edges[0] + 1])
    on_runs = runs[0::2] if first_is_on else runs[1::2]
    off_runs = runs[1::2] if first_is_on else runs[0::2]
    # drop blips; long pauses between messages are not bits either
    typical = np.median(on_runs) if len(on_runs) else 0
    if typical <= 0:
        return None
    lengths = np.concatenate((on_runs, off_runs))
    lengths = lengths[(lengths >= 0.3 * typical) & (lengths <= 12 * typical)]
    if len(lengths) < 8:
        return None

    tolerance = max(1, int(0.08 * np.percentile(lengths, 10)))
    merged = merge_plateau_lengths(lengths.astype(np.uint64), tolerance)
    if len(merged) < 2:
        return None
    bit_length = get_bit_length_from_plateau_lengths(merged)
    if bit_length is None or bit_length <= tolerance:
        return None

    # refine: every run is a whole number of bits, average the bit length
    # over runs of 1-4 bits (the GCD above is rounded down by the tolerance)
    multiples = np.round(lengths / bit_length)
    usable = (multiples >= 1) & (multiples <= 4)
    usable &= np.abs(lengths - multiples * bit_length) <= 0.2 * bit_length
    if np.count_nonzero(usable) >= 8:
        bit_length = int(round(np.median(lengths[usable] / multiples[usable])))
        tolerance = max(tolerance, int(0.05 * bit_length))

    # Per sample, a weak pulse often falls close to the noise: the center must
    # stay just above the noise or the pulses break apart when demodulating
    center = noise + 0.15 * (level - noise)
    return int(bit_length), center, tolerance


def segment_messages_from_magnitudes(magnitudes: np.ndarray, noise_threshold: float):
    """
    Get the list of start, end indices of messages

    :param magnitudes: Magnitudes of samples
    :param noise_threshold: Threshold for noise
    :return:
    """
    return c_auto_interpretation.segment_messages_from_magnitudes(
        magnitudes, noise_threshold
    )


def merge_message_segments_for_ook(segments: list):
    if len(segments) <= 1:
        return segments

    result = []
    # Get a array of pauses for comparison
    pauses = np.fromiter(
        (segments[i + 1][0] - segments[i][1] for i in range(len(segments) - 1)),
        count=len(segments) - 1,
        dtype=np.uint64,
    )

    pulses = np.fromiter(
        (segments[i][1] - segments[i][0] for i in range(len(segments))),
        count=len(segments),
        dtype=np.uint64,
    )

    # Find relatively large pauses, these mark new messages
    min_pulse_length = min_without_outliers(pulses, z=1)
    large_pause_indices = np.nonzero(pauses >= 8 * min_pulse_length)[0]

    # Merge Pulse Lengths between long pauses
    for i in range(0, len(large_pause_indices) + 1):
        if i == 0:
            start, end = 0, large_pause_indices[i] + 1 if len(
                large_pause_indices
            ) >= 1 else len(segments)
        elif i == len(large_pause_indices):
            start, end = large_pause_indices[i - 1] + 1, len(segments)
        else:
            start, end = large_pause_indices[i - 1] + 1, large_pause_indices[i] + 1

        msg_begin = segments[start][0]
        msg_length = sum(segments[j][1] - segments[j][0] for j in range(start, end))
        msg_length += sum(
            segments[j][0] - segments[j - 1][1] for j in range(start + 1, end)
        )

        result.append((msg_begin, msg_begin + msg_length))

    return result


def detect_modulation(data: np.ndarray, wavelet_scale=4, median_filter_order=11) -> str:
    """
    Detect modulation type from complex IQ samples.

    Uses the same multi-feature approach proven in the live spectrum
    analyzer, adapted for recorded signal analysis:

    1. Amplitude analysis: OOK/ASK have varying amplitude, FSK/PSK constant
    2. FFT multi-peak: FSK has 2+ spectral peaks (most reliable FSK indicator)
    3. Instantaneous frequency histogram: FSK shows 2+ distinct frequency levels
    4. Phase second-derivative: PSK has sharp discontinuities, FSK has smooth ramps
    5. Constellation shape: FSK/PSK don't pass through origin, OOK does

    Returns: "OOK", "ASK", "FSK", or "PSK"
    """
    # Convert IQArray to complex64 if needed
    if hasattr(data, "as_complex64"):
        data = data.as_complex64()
    elif not np.iscomplexobj(data):
        if hasattr(data, "ndim") and data.ndim == 2:
            data = data[:, 0].astype(np.float32) + 1j * data[:, 1].astype(np.float32)
        else:
            data = np.asarray(data, dtype=np.complex64)

    n_data = len(data)
    if n_data < 4:
        return None

    # ── Step 1: Amplitude analysis ─────────────────────────
    magnitudes = np.abs(data)
    max_mag = float(np.max(magnitudes))
    if max_mag < 1e-10:
        return None

    mag_norm = magnitudes / max_mag
    zero_ratio = float(np.sum(mag_norm < 0.1)) / n_data

    if zero_ratio > 0.15:
        return "OOK"

    amp_mean = float(np.mean(mag_norm))
    amp_cv = float(np.std(mag_norm)) / amp_mean if amp_mean > 0 else 0

    # ── Step 2: FFT multi-peak (FSK indicator) ─────────────
    fft_len = 2 ** int(np.log2(max(n_data, 16)))
    fft_mag = np.abs(np.fft.fftshift(np.fft.fft(data[:fft_len])))
    fft_db = 20.0 * np.log10(np.maximum(fft_mag, 1e-20))
    fft_max_db = float(np.max(fft_db))

    peak_thr = fft_max_db - 30
    min_peak_dist = max(fft_len // 50, 2)
    fft_peaks = []
    for i in range(1, len(fft_db) - 1):
        if (
            float(fft_db[i]) > float(fft_db[i - 1])
            and float(fft_db[i]) > float(fft_db[i + 1])
            and float(fft_db[i]) > peak_thr
        ):
            if all(abs(i - p) >= min_peak_dist for p in fft_peaks):
                fft_peaks.append(i)
    n_fft_peaks = len(fft_peaks)

    # ── Step 3: Instantaneous frequency histogram ──────────
    phase_diff = np.diff(np.unwrap(np.angle(data)))
    freq_peaks = 0
    if len(phase_diff) > 4:
        pd_std = float(np.std(phase_diff))
        if pd_std > 1e-6:
            n_bins = min(64, max(8, n_data // 50))
            hist, _ = np.histogram(phase_diff, bins=n_bins)
            kernel = np.array([1, 2, 3, 2, 1], dtype=float)
            kernel /= kernel.sum()
            if len(hist) > len(kernel):
                hist_smooth = np.convolve(hist, kernel, mode="same")
            else:
                hist_smooth = hist.astype(float)

            peak_threshold = float(np.max(hist_smooth)) * 0.12
            for i in range(1, len(hist_smooth) - 1):
                if (
                    float(hist_smooth[i]) > float(hist_smooth[i - 1])
                    and float(hist_smooth[i]) > float(hist_smooth[i + 1])
                    and float(hist_smooth[i]) > peak_threshold
                ):
                    freq_peaks += 1

    # ── Step 4: Phase second-derivative (PSK vs FSK) ───────
    psk_jump_ratio = 0.0
    if len(phase_diff) > 4:
        phase_diff2 = np.diff(phase_diff)
        n_sharp = int(np.sum(np.abs(phase_diff2) > 1.5))
        psk_jump_ratio = n_sharp / max(len(phase_diff2), 1)

    # ── Step 5: Constellation shape ────────────────────────
    passes_origin = float(np.sum(mag_norm < 0.15)) / n_data

    # ── Classification ─────────────────────────────────────

    # High amplitude variation → ASK or OOK
    if amp_cv > 0.25:
        if float(np.sum(mag_norm < 0.3)) > n_data * 0.10:
            return "OOK"
        return "ASK"

    # Constant envelope → FSK or PSK

    # FSK: two or more spectral peaks OR two frequency histogram levels
    if n_fft_peaks >= 2 or freq_peaks >= 2:
        return "FSK"

    # PSK: sharp phase discontinuities (second-derivative spikes)
    if psk_jump_ratio > 0.02:
        return "PSK"

    # ── Fallback: wavelet for ambiguous cases ──────────────
    try:
        data_norm = data / max_mag
        mag_wavlt = np.abs(Wavelet.cwt_haar(data_norm, scale=wavelet_scale))
        if len(mag_wavlt) > 0:
            norm_mag_wavlt = np.abs(
                Wavelet.cwt_haar(data_norm / np.abs(data_norm), scale=wavelet_scale)
            )
            var_mag = float(np.var(mag_wavlt))
            var_norm_mag = float(np.var(norm_mag_wavlt))
            var_filtered_mag = float(
                np.var(
                    c_auto_interpretation.median_filter(
                        mag_wavlt, k=median_filter_order
                    )
                )
            )

            if var_mag > 1.5 * var_norm_mag:
                return "ASK"
            if var_mag > 10 * var_filtered_mag:
                return "PSK"
    except Exception:
        pass

    return "OOK"


def is_pulse_train(message_indices: list) -> bool:
    """
    True if the segments are short pulses grouped into messages (on/off
    keying): many segments merge into few messages. Each OOK pulse alone is
    a constant carrier, so the per-segment detection below took the pulses
    of remote controls for FSK.
    """
    if len(message_indices) < 8:
        return False
    merged = merge_message_segments_for_ook(message_indices)
    return len(message_indices) >= 4 * max(len(merged), 1)


def detect_modulation_for_messages(signal: IQArray, message_indices: list) -> str:
    if is_pulse_train(message_indices):
        return "OOK"

    max_messages = 100

    modulations_for_messages = []
    complex = signal.as_complex64()
    for start, end in message_indices[0:max_messages]:
        mod = detect_modulation(complex[start:end])
        if mod is not None:
            modulations_for_messages.append(mod)

    if len(modulations_for_messages) == 0:
        return None

    return most_common(modulations_for_messages)


def detect_center(rectangular_signal: np.ndarray, max_size=None):
    rect = rectangular_signal[rectangular_signal > -4]  # do not consider noise

    # Ignore the first and last 5% of samples,
    # because there tends to be an overshoot at start/end of rectangular signal
    rect = rect[int(0.05 * len(rect)) : int(0.95 * len(rect))]

    if max_size is not None and len(rect) > max_size:
        rect = rect[0:max_size]

    hist_min, hist_max = util.minmax(rect)

    # The step size of histogram is set to variance of the rectangular signal
    # If a signal has low variance we need to be more accurate at center detection
    hist_step = float(np.var(rect))

    try:
        y, x = np.histogram(
            rect, bins=np.arange(hist_min, hist_max + hist_step, hist_step)
        )
    except (ZeroDivisionError, ValueError):
        # For a segment with zero variance (constant line) it is not possible to find a center
        return None

    num_values = 2
    most_common_levels = []

    window_size = max(2, int(0.05 * len(y)) + 1)

    def get_elem(arr, index: int, default):
        if 0 <= index < len(arr):
            return arr[index]
        else:
            return default

    for index in np.argsort(y)[::-1]:
        # check if we have a local maximum in histogram, if yes, append the value
        if all(
            y[index] > get_elem(y, index + i, 0)
            and y[index] > get_elem(y, index - i, 0)
            for i in range(1, window_size)
        ):
            most_common_levels.append(x[index])

        if len(most_common_levels) == num_values:
            break

    if len(most_common_levels) == 0:
        return None

    # todo if num values greater two return more centers
    return np.mean(most_common_levels)


def estimate_tolerance_from_plateau_lengths(plateau_lengths, relative_max=0.05) -> int:
    if len(plateau_lengths) <= 1:
        return None

    unique = np.unique(plateau_lengths)
    maximum = max_without_outliers(unique, z=2)

    limit = relative_max * maximum
    # limit = np.mean(plateau_lengths) - 1 * np.std(plateau_lengths)
    if unique[0] > 1 and unique[0] >= limit:
        return 0

    result = 0
    for value in unique:
        if value > 1 and value >= limit:
            break
        result = value

    return result


def merge_plateau_lengths(plateau_lengths, tolerance=None) -> list:
    if tolerance is None:
        tolerance = estimate_tolerance_from_plateau_lengths(plateau_lengths)

    if tolerance == 0 or tolerance is None:
        return plateau_lengths

    return c_auto_interpretation.merge_plateaus(
        plateau_lengths, tolerance, max_count=10000
    )


def round_plateau_lengths(plateau_lengths: list):
    """
    Round plateau lengths to next divisible number of digit count e.g. 99 -> 100, 293 -> 300

    :param plateau_lengths:
    :return:
    """
    # round to n_digits of most common value
    digit_counts = [len(str(p)) for p in plateau_lengths]
    n_digits = min(3, int(np.percentile(digit_counts, 50)))
    f = 10 ** (n_digits - 1)

    for i, plateau_len in enumerate(plateau_lengths):
        plateau_lengths[i] = int(round(plateau_len / f)) * f


def get_tolerant_greatest_common_divisor(numbers):
    """
    Get the greatest common divisor of the numbers in a tolerant manner:
    Calculate each gcd of each pair of numbers and return the most common one

    """
    gcd = math.gcd

    gcds = [gcd(x, y) for x, y in itertools.combinations(numbers, 2) if gcd(x, y) != 1]
    if len(gcds) == 0:
        return 1

    return get_most_frequent_value(gcds)


def get_bit_length_from_plateau_lengths(merged_plateau_lengths) -> int:
    if len(merged_plateau_lengths) == 0:
        return 0

    if len(merged_plateau_lengths) == 1:
        return int(merged_plateau_lengths[0])

    round_plateau_lengths(merged_plateau_lengths)
    histogram = c_auto_interpretation.get_threshold_divisor_histogram(
        merged_plateau_lengths
    )

    if len(histogram) == 0:
        return 0
    else:
        # Can't return simply argmax, since this could be a multiple of result (e.g. 2 1s are transmitted often)
        sorted_indices = np.argsort(histogram)[::-1]
        max_count = histogram[sorted_indices[0]]
        result = sorted_indices[0]

        for i in range(1, len(sorted_indices)):
            if histogram[sorted_indices[i]] < 0.25 * max_count:
                break
            if sorted_indices[i] <= 0.5 * result:
                result = sorted_indices[i]

        return int(result)


def estimate(iq_array: IQArray, noise: float = None, modulation: str = None) -> dict:
    if isinstance(iq_array, np.ndarray):
        iq_array = IQArray(iq_array)

    magnitudes = iq_array.magnitudes
    # Smooth the magnitudes a little before finding the noise level and the
    # messages: with weak signals (e.g. RTL-SDR at low gain, values of a few
    # ADC steps) single noise samples are as high as the signal, the noise
    # threshold came out above the signal and messages fell apart into
    # hundreds of fragments (wrong samples/symbol of 3 or 10).
    smoothed = smooth_magnitudes(magnitudes)

    weak_signal = False
    # find noise threshold
    if noise is None:
        noise = detect_noise_level(magnitudes)
        noise_smoothed = detect_noise_level(smoothed)
        above = smoothed[smoothed > noise_smoothed]
        signal_level = float(np.median(above)) if len(above) else 0.0
        if signal_level > 0 and noise > 0.6 * signal_level:
            # Noise peaks reach the signal: the raw threshold would cut the
            # signal into pieces, use the threshold of the smoothed magnitudes
            noise = noise_smoothed
            segment_magnitudes = smoothed
            weak_signal = True
        else:
            segment_magnitudes = magnitudes
    else:
        segment_magnitudes = (
            smoothed if noise < float(np.max(magnitudes)) else magnitudes
        )

    # segment messages
    message_indices = segment_messages_from_magnitudes(
        segment_magnitudes, noise_threshold=noise
    )

    # detect modulation
    modulation_detected = modulation is None
    modulation = (
        detect_modulation_for_messages(iq_array, message_indices)
        if modulation is None
        else modulation
    )
    if modulation is None:
        return None

    if weak_signal and len(message_indices) > 2:
        # drop noise blips that cross the low threshold for a few samples,
        # otherwise they define the "shortest pulse" and nothing gets merged
        lengths = np.array([e - s for s, e in message_indices])
        typical = np.median(lengths[lengths > 8]) if np.any(lengths > 8) else 0
        min_len = max(4, int(0.1 * typical))
        message_indices = [(s, e) for s, e in message_indices if e - s >= min_len]

    if modulation in ("OOK", "ASK"):
        # Pulses of on/off keyed remotes are separate segments: merge the
        # segments between long pauses into messages. ASK signals that never
        # go silent inside a message are already one segment per message.
        message_indices = merge_message_segments_for_ook(message_indices)

    # The modulation detection is unreliable on weak signals (it said FSK for
    # an OOK remote at low gain): if on/off pulses are clearly found, use ASK
    if weak_signal and (modulation in ("OOK", "ASK") or modulation_detected):
        weak = estimate_weak_ook(magnitudes, noise)
        if weak is not None:
            bit_length, center_raw, tolerance = weak
            scale = float(np.max(magnitudes)) / max(
                float(np.max(np.abs(iq_array.as_complex64()))), 1e-12
            )
            return {
                "modulation_type": "ASK",
                "bit_length": bit_length,
                "center": center_raw / scale,
                "tolerance": int(tolerance),
                "noise": noise,
            }

    if (modulation == "OOK" or modulation == "ASK") and weak_signal:
        # Demodulate the smoothed magnitudes: per sample, a weak signal jumps
        # between 0 and a few ADC steps and the plateaus (and the bit length)
        # came out a few samples long
        normalized = np.abs(iq_array.as_complex64()).astype(np.float32)
        scale = float(np.max(magnitudes)) / max(float(np.max(normalized)), 1e-12)
        normalized = smooth_magnitudes(normalized)
        data = np.where(normalized >= noise / scale, normalized, 0).astype(np.float32)
    elif modulation == "OOK" or modulation == "ASK":
        data = signal_functions.afp_demod(iq_array.data, noise, "ASK", 2)
    elif modulation == "FSK":
        data = signal_functions.afp_demod(iq_array.data, noise, "FSK", 2)
    elif modulation == "PSK":
        data = signal_functions.afp_demod(iq_array.data, noise, "PSK", 2)
    else:
        raise ValueError("Unsupported Modulation")

    centers = []
    bit_lengths = []
    tolerances = []
    for start, end in message_indices:
        msg_rect_data = data[start:end]

        center = detect_center(msg_rect_data)
        if center is None:
            continue

        plateau_lengths = c_auto_interpretation.get_plateau_lengths(
            msg_rect_data, center, percentage=25
        )
        tolerance = estimate_tolerance_from_plateau_lengths(plateau_lengths)
        if tolerance is None:
            tolerance = 0
        else:
            tolerances.append(tolerance)

        merged_lengths = merge_plateau_lengths(plateau_lengths, tolerance=tolerance)
        if len(merged_lengths) < 2:
            continue

        bit_length = get_bit_length_from_plateau_lengths(merged_lengths)

        min_bit_length = tolerance + 1

        if bit_length > min_bit_length:
            # only add to score if found bit length surpasses minimum bit length
            centers.append(center)
            bit_lengths.append(bit_length)

    # Since we cannot have different centers per message (yet) we need to combine them to return a common center
    if modulation == "OOK" or modulation == "ASK":
        # for ask modulations the center tends to be the minimum of all found centers
        center = min_without_outliers(np.array(centers), z=2)
        if center is None:
            # did not find any centers at all so we cannot return a valid estimation
            return None
    elif len(centers) > 0:
        # for other modulations it is a better strategy to take the mean of found centers
        center = np.mean(centers)
    else:
        # did not find any centers at all so we cannot return a valid estimation
        return None

    bit_length = get_most_frequent_value(bit_lengths)

    try:
        tolerance = np.percentile(tolerances, 50)
    except IndexError:
        tolerance = None

    if bit_length is None:
        return None
    if tolerance is None:
        # no tolerances found, default to 5% of bit length
        tolerance = max(1, int(0.05 * bit_length))

    result = {
        "modulation_type": "ASK" if modulation == "OOK" else modulation,
        "bit_length": bit_length,
        "center": center,
        "tolerance": int(tolerance),
        "noise": noise,
    }

    return result
