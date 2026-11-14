import unittest

import numpy as np

from urh.signalprocessing.SpectrumProcessor import SpectrumProcessor, chronological


class TestSpectrumProcessor(unittest.TestCase):
    def test_weak_signal_stands_out_and_dc_removed(self):
        rng = np.random.default_rng(1)
        fs, n = 2e6, 2**15
        t = np.arange(n) / fs
        noise = (rng.normal(size=n) + 1j * rng.normal(size=n)) * 0.01
        tone = 0.003 * np.exp(2j * np.pi * 400e3 * t)  # about 10 dB above noise per bin
        x = (noise + tone + 0.05).astype(np.complex64)
        proc = SpectrumProcessor(fft_size=4096, averaging="Off", remove_dc=True)
        freqs, power = proc.compute(x, fs)
        db = 10 * np.log10(power)
        floor = np.median(db)
        tone_bin = np.argmin(np.abs(freqs - 400e3))
        dc_bin = np.argmin(np.abs(freqs))
        self.assertGreater(db[tone_bin] - floor, 10)
        self.assertLess(db[dc_bin] - floor, 6)
        # Noise is smooth after averaging the segments
        self.assertLess(np.std(np.delete(db, [tone_bin, dc_bin])), 2.5)

    def test_full_scale_tone_is_0_dbfs(self):
        fs, n = 1e6, 8192
        x = np.exp(2j * np.pi * 125e3 * np.arange(n) / fs).astype(np.complex64)
        proc = SpectrumProcessor(fft_size=1024, averaging="Off", remove_dc=False)
        freqs, power = proc.compute(x, fs)
        self.assertAlmostEqual(10 * np.log10(power.max()), 0, delta=0.5)

    def test_short_input_and_chronological(self):
        proc = SpectrumProcessor(fft_size=4096)
        freqs, power = proc.compute(np.ones(100, dtype=np.complex64), 1e6)
        self.assertEqual(len(freqs), 64)
        buf = np.arange(10)
        self.assertEqual(list(chronological(buf, 3)), [3, 4, 5, 6, 7, 8, 9, 0, 1, 2])

    def test_auto_range_follows_floor(self):
        proc = SpectrumProcessor()
        db = np.full(1000, -90.0)
        db[500] = -40
        floor, lo, hi = proc.auto_range(db)
        self.assertEqual(floor, -90)
        self.assertLessEqual(lo, -95)
        self.assertGreaterEqual(hi, -35)


if __name__ == "__main__":
    unittest.main()
