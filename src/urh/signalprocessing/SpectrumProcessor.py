"""
Spectrum computation for the Spectrum Analyzer.

The classic URH view draws the magnitude of a single FFT over the whole
receive buffer. A single FFT of noise varies by +-10..20 dB from bin to bin,
so weak signals disappear in the noise band. The averaged view does what
common SDR programs do: a windowed FFT of moderate size, averaged over all
segments of the buffer (Welch) and over time (exponential average), shown in
dB with a range that follows the noise floor.
"""
import numpy as np

WINDOWS = {
    "Hann": np.hanning,
    "Blackman-Harris": lambda n: _blackman_harris(n),
    "Flat top": lambda n: _flat_top(n),
    "Rectangular": np.ones,
}

FFT_SIZES = [256, 512, 1024, 2048, 4096, 8192, 16384, 32768]

# Weight of the newest spectrum in the exponential average
AVERAGING = {
    "Off": 1.0,
    "Low": 0.5,
    "Medium": 0.25,
    "High": 0.1,
    "Very high": 0.04,
}

# Window size and window of the waterfall (Spectrogram defaults)
_WATERFALL_SIZE = 1024


def _blackman_harris(n: int) -> np.ndarray:
    k = np.arange(n) / max(n - 1, 1)
    a = (0.35875, 0.48829, 0.14128, 0.01168)
    return (
        a[0]
        - a[1] * np.cos(2 * np.pi * k)
        + a[2] * np.cos(4 * np.pi * k)
        - a[3] * np.cos(6 * np.pi * k)
    )


def _flat_top(n: int) -> np.ndarray:
    k = np.arange(n) / max(n - 1, 1)
    a = (0.21557895, 0.41663158, 0.277263158, 0.083578947, 0.006947368)
    return (
        a[0]
        - a[1] * np.cos(2 * np.pi * k)
        + a[2] * np.cos(4 * np.pi * k)
        - a[3] * np.cos(6 * np.pi * k)
        + a[4] * np.cos(8 * np.pi * k)
    )


def chronological(buffer: np.ndarray, current_index: int) -> np.ndarray:
    """
    Return the samples of a circular receive buffer, newest last.
    buffer[current_index:] holds older samples of the previous round.
    """
    n = len(buffer)
    if current_index is None or current_index <= 0 or current_index >= n:
        return buffer
    return np.concatenate((buffer[current_index:], buffer[:current_index]))


class SpectrumProcessor(object):
    def __init__(
        self,
        fft_size=4096,
        window="Hann",
        averaging="Medium",
        remove_dc=True,
    ):
        self.fft_size = fft_size
        self.window = window
        self.averaging = averaging
        self.remove_dc = remove_dc
        self.__avg = None  # averaged power spectrum (linear, fft order)
        self.__key = None
        # Display range in dB (auto range state)
        self.range_db = None

    def reset(self):
        self.__avg = None
        self.range_db = None

    @property
    def window_values(self) -> np.ndarray:
        return WINDOWS.get(self.window, np.hanning)(self.fft_size).astype(np.float32)

    def compute(self, samples: np.ndarray, sample_rate: float):
        """
        :param samples: complex samples, oldest first
        :return: (frequencies, power) sorted by frequency; power is linear with
                 a full scale sine at 0 dB, i.e. 10*log10(power) is in dBFS
        """
        samples = np.asarray(samples)
        if len(samples) == 0:
            return None, None
        n = int(self.fft_size)
        if len(samples) < n:
            # Not enough samples for one segment: use the largest power of two
            n = max(16, 1 << (int(len(samples)).bit_length() - 1))
            if len(samples) < n:
                samples = np.append(samples, np.zeros(n - len(samples), samples.dtype))
        samples = samples.astype(np.complex64, copy=False)

        win = WINDOWS.get(self.window, np.hanning)(n).astype(np.float32)
        # 50% overlap, newest segments first so the end of the buffer is used
        hop = n // 2
        num_segments = max(1, (len(samples) - n) // hop + 1)
        start = len(samples) - (n + (num_segments - 1) * hop)
        idx = start + np.arange(num_segments)[:, None] * hop + np.arange(n)[None, :]
        segments = samples[idx]
        if self.remove_dc:
            segments = segments - segments.mean(axis=1, keepdims=True)
        spectrum = np.fft.fft(segments * win, axis=1)
        power = np.mean(
            spectrum.real.astype(np.float64) ** 2
            + spectrum.imag.astype(np.float64) ** 2,
            axis=0,
        ) / (float(np.sum(win)) ** 2)

        key = (n, self.window, float(sample_rate), self.remove_dc)
        alpha = AVERAGING.get(self.averaging, 1.0)
        if self.__avg is None or self.__key != key or len(self.__avg) != n:
            self.__avg = power
        else:
            self.__avg = alpha * power + (1.0 - alpha) * self.__avg
        self.__key = key

        freqs = np.fft.fftfreq(n, 1.0 / sample_rate)
        order = np.argsort(freqs)
        result = np.maximum(self.__avg[order], 1e-20)
        return freqs[order].astype(np.float32), result.astype(np.float32)

    def noise_offset_to_waterfall_db(self) -> float:
        """
        dB to add to this spectrum's noise level to get the noise level of the
        waterfall (Hann window of 1024 samples, normalized by the window size).
        """
        w = WINDOWS.get(self.window, np.hanning)(int(self.fft_size)).astype(np.float64)
        mine = np.sum(w**2) / np.sum(w) ** 2
        h = np.hanning(_WATERFALL_SIZE)
        waterfall = np.sum(h**2) / _WATERFALL_SIZE**2
        return float(10 * np.log10(waterfall / mine))

    def auto_range(self, power_db: np.ndarray, peak_db: np.ndarray = None):
        """
        Display range that follows the noise floor: the floor sits near the
        bottom and the strongest signal near the top. The range grows at once
        and shrinks slowly so the trace does not jump.
        """
        floor = float(np.median(power_db))
        top = float(np.max(power_db))
        if peak_db is not None and len(peak_db) == len(power_db):
            top = max(top, float(np.max(peak_db)))
        lo_t = floor - 10
        hi_t = max(floor + 50, top + 5)
        if self.range_db is None:
            lo, hi = lo_t, hi_t
        else:
            lo, hi = self.range_db
            lo = lo_t if lo_t < lo else lo + 0.05 * (lo_t - lo)
            hi = hi_t if hi_t > hi else hi + 0.05 * (hi_t - hi)
        self.range_db = (lo, hi)
        return floor, lo, hi
