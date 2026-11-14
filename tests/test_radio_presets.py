import unittest

from urh.dev import config, RadioPresets


class TestRadioPresets(unittest.TestCase):
    def adapt(self, name, device):
        preset = next(p for p in RadioPresets.PRESETS if p.name.startswith(name))
        return RadioPresets.adapt_to_device(
            preset, device, config.DEVICE_CONFIG[device]
        )

    def test_rtl_sdr_is_limited_to_practical_rate(self):
        freq, sr, bw, ok = self.adapt("Scan 868", "RTL-SDR")
        self.assertTrue(ok)
        self.assertEqual(freq, 868e6)
        self.assertEqual(sr, 2.4e6)
        self.assertEqual(bw, 2.4e6)

    def test_hackrf_keeps_wide_scan_and_minimum_rate(self):
        self.assertEqual(self.adapt("Scan 300", "HackRF")[1], 20e6)
        self.assertEqual(self.adapt("433.92", "HackRF")[1], 2e6)

    def test_unsupported_frequency(self):
        # PlutoSDR tunes from 70 MHz
        self.assertFalse(self.adapt("40.685", "PlutoSDR")[3])
        self.assertTrue(self.adapt("40.685", "RTL-SDR")[3])

    def test_discrete_sample_rates(self):
        freq, sr, bw, ok = self.adapt("433.92", "AirSpy Mini")
        self.assertEqual(sr, 6e6)

    def test_all_presets_valid(self):
        for p in RadioPresets.PRESETS:
            self.assertGreater(p.frequency, 1e6)
            self.assertGreaterEqual(p.sample_rate, 1e6)
            self.assertTrue(p.note)


if __name__ == "__main__":
    unittest.main()
