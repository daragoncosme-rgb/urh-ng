import unittest

from PyQt6.QtCore import QLocale

from tests.QtTestCase import QtTestCase
from urh.ui.KillerDoubleSpinBox import KillerDoubleSpinBox


class TestKillerSpinBoxLocale(QtTestCase):
    def setUp(self):
        super().setUp()
        self.old_locale = QLocale()
        QLocale.setDefault(QLocale(QLocale.Language.Spanish, QLocale.Country.Spain))
        self.spin = KillerDoubleSpinBox()
        self.spin.setDecimals(10)
        self.spin.setRange(100e3, 6e9)
        self.spin.setValue(868e6)

    def tearDown(self):
        QLocale.setDefault(self.old_locale)
        super().tearDown()

    def test_dot_and_comma(self):
        for text, expected in (
            ("433.92M", 433.92e6),
            ("433,92M", 433.92e6),
            ("433.920M", 433.92e6),
            ("2,4M", 2.4e6),
            ("433920000", 433.92e6),
            ("1.234,5K", 1234.5e3),
            ("1,234.5K", 1234.5e3),
            ("0.5G", 0.5e9),
        ):
            self.assertAlmostEqual(self.spin.valueFromText(text), expected, places=0)

    def test_invalid_keeps_value(self):
        self.assertEqual(self.spin.valueFromText("abcM"), 868e6)

    def test_round_trip(self):
        self.spin.setValue(433.92e6)
        self.assertAlmostEqual(
            self.spin.valueFromText(self.spin.textFromValue(433.92e6)), 433.92e6, places=0
        )


if __name__ == "__main__":
    unittest.main()
