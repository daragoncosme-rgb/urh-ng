import string

from PyQt6.QtCore import QLocale
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QValidator
from PyQt6.QtWidgets import QDoubleSpinBox


class KillerDoubleSpinBox(QDoubleSpinBox):
    """
    Print values with suffix (G,M,K)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.auto_update_step_size = True

        self.lineEdit().setValidator(None)

        # Can't connect to value changed, as it would delete the number when changing a digit
        # see: https://github.com/jopohl/urh/issues/129
        self.editingFinished.connect(self.adjust_step)

    def setValue(self, value: float):
        super().setValue(value)
        self.adjust_step()

    def adjust_step(self):
        if not self.auto_update_step_size:
            return

        value = abs(self.value())
        if value >= 1e9:
            self.setSingleStep(10 ** (9 - self.decimals()))
        elif value >= 1e6:
            self.setSingleStep(10 ** (6 - self.decimals()))
        elif value >= 1e3:
            self.setSingleStep(10 ** (3 - self.decimals()))
        else:
            self.setSingleStep(10 ** -(self.decimals()))

    def textFromValue(self, value: float):
        if abs(value) >= 10**9:
            result, suffix = super().textFromValue(value / 10**9), "G"
        elif abs(value) >= 10**6:
            result, suffix = super().textFromValue(value / 10**6), "M"
        elif abs(value) >= 10**3:
            result, suffix = super().textFromValue(value / 10**3), "K"
        else:
            result, suffix = super().textFromValue(value), ""

        result = result.rstrip("0")
        if len(result) == 0:
            return result

        if result[-1] not in string.digits:
            result += "0"

        return result + suffix

    @staticmethod
    def parse_number(text: str) -> float:
        """
        Parse a number typed with either "." or "," as decimal separator,
        independent of the system language: with a Spanish or German locale
        "433.92" was not understood and the value silently became the minimum.
        """
        t = text.strip().replace(" ", "")
        if "," in t and "." in t:
            # The last separator is the decimal one, the other groups digits
            decimal = "," if t.rfind(",") > t.rfind(".") else "."
            group = "." if decimal == "," else ","
            t = t.replace(group, "").replace(decimal, ".")
        elif t.count(",") == 1:
            t = t.replace(",", ".")
        elif t.count(",") > 1 or t.count(".") > 1:
            t = t.replace(",", "").replace(".", "")
        return float(t)

    def valueFromText(self, text: str):
        text = text.strip()
        suffix = self.suffix()
        if suffix and text.endswith(suffix):
            text = text[: -len(suffix)]
        factor = 1
        if text[-1:] in ("G", "g"):
            factor, text = 10**9, text[:-1]
        elif text[-1:] in ("M", "m"):
            factor, text = 10**6, text[:-1]
        elif text[-1:] in ("K", "k"):
            factor, text = 10**3, text[:-1]
        try:
            return self.parse_number(text) * factor
        except ValueError:
            value, ok = QLocale().toDouble(text)
            return value * factor if ok else self.value()

    def validate(self, inpt: str, pos: int):
        if self.suffix().upper() in ("", "K", "M", "G"):
            rx = QRegularExpression("^(-?[0-9]+)[.]?[0-9]*[kKmMgG]?$")
        else:
            rx = QRegularExpression("^(-?[0-9]+)[.]?[0-9]*[{}]?$".format(self.suffix()))
        result = (
            QValidator.State.Acceptable
            if rx.match(inpt.replace(",", ".")).hasMatch()
            else QValidator.State.Invalid
        )
        return result, inpt, pos
