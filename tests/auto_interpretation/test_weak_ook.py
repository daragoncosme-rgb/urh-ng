import unittest

import numpy as np

from urh.ainterpretation import AutoInterpretation
from urh.signalprocessing.IQArray import IQArray


def weak_ook_signal(sps=500, amplitude=2.0, noise=0.5, seed=3):
    """KeeLoq-like remote recorded with very low gain: int8 samples of 0..3"""
    rng = np.random.default_rng(seed)
    symbols = []
    for _ in range(8):
        symbols += [1, 0] * 11 + [1] + [0] * 10
        for _ in range(66):
            symbols += [1, 1, 0] if rng.random() < 0.5 else [1, 0, 0]
        symbols += [0] * 40
    envelope = np.repeat(np.array(symbols, dtype=np.float32), sps) * amplitude
    phase = rng.uniform(0, 2 * np.pi, len(envelope))
    i = envelope * np.cos(phase) + rng.normal(0, noise, len(envelope))
    q = envelope * np.sin(phase) + rng.normal(0, noise, len(envelope))
    data = np.empty((len(envelope), 2), dtype=np.int8)
    data[:, 0] = np.clip(np.round(i), -128, 127)
    data[:, 1] = np.clip(np.round(q), -128, 127)
    return IQArray(data)


class TestWeakOOK(unittest.TestCase):
    def test_bit_length_of_weak_signal(self):
        result = AutoInterpretation.estimate(weak_ook_signal())
        self.assertIsNotNone(result)
        self.assertEqual(result["modulation_type"], "ASK")
        self.assertAlmostEqual(result["bit_length"], 500, delta=50)

    def test_smooth_keeps_length(self):
        m = np.arange(100, dtype=np.float32)
        s = AutoInterpretation.smooth_magnitudes(m, 8)
        self.assertEqual(len(s), len(m))
        self.assertAlmostEqual(float(s[50]), 49.5, delta=1)


if __name__ == "__main__":
    unittest.main()
