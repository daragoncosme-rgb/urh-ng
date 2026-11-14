from tests.QtTestCase import QtTestCase
from urh.controller.dialogs.KeeLoqCodeWordDialog import KeeLoqCodeWordDialog
from urh.signalprocessing.Message import Message
from urh.signalprocessing.MessageType import MessageType
from urh.util import KeeLoqPWM


def lsb_first(value: int, nbits: int) -> str:
    return "{0:0{1}b}".format(value, nbits)[::-1]


def code_word_bits(encrypted, serial, button="0100", vlow=0, rpt=0) -> str:
    """The 66 KeeLoq bits in transmission order."""
    return (
        lsb_first(encrypted, 32) + lsb_first(serial, 28) + button + str(vlow) + str(rpt)
    )


def pwm(bits: str, symbols_per_te=1) -> str:
    out = ""
    for b in bits:
        out += "100" if b == "1" else "110"
    if symbols_per_te > 1:
        out = "".join(c * symbols_per_te for c in out)
    return out


PREAMBLE = "10" * 11 + "1"  # 23 TE alternating
HEADER = "0" * 10

ENC = 0xA1B2C3D4
SER = 0x0ABCDEF


class TestKeeLoqPWM(QtTestCase):
    def check(self, word, vlow=False, rpt=False):
        self.assertTrue(word.ok, word.status)
        self.assertEqual(word.encrypted, ENC)
        self.assertEqual(word.serial, SER)
        self.assertEqual(word.encrypted_hex, "A1B2C3D4")
        self.assertEqual(word.serial_hex, "0ABCDEF")
        self.assertEqual(word.button, "0100")
        self.assertEqual(word.button_text, "S0")
        self.assertEqual(word.v_low, vlow)
        self.assertEqual(word.repeat, rpt)

    def test_data_only_message(self):
        # URH splits preamble and data at the header: data message alone
        data = pwm(code_word_bits(ENC, SER))
        # the final low merges with the pause, so URH cuts it
        self.check(KeeLoqPWM.decode_message(data.rstrip("0") + ""))

    def test_last_bit_cut_by_the_pause(self):
        # real captures end with the last high only: "...1" for bit 1
        for rpt, tail in ((1, "1"), (0, "11")):
            data = pwm(code_word_bits(ENC, SER, rpt=rpt))
            cut = data[:-3] + tail
            word = KeeLoqPWM.decode_message(cut)
            self.check(word, rpt=bool(rpt))

    def test_complete_with_preamble_and_header(self):
        data = pwm(code_word_bits(ENC, SER, vlow=1, rpt=1))
        word = KeeLoqPWM.decode_message(PREAMBLE + HEADER + data)
        self.check(word, vlow=True, rpt=True)
        self.assertTrue(word.has_preamble and word.has_header)

    def test_double_symbols_per_te(self):
        data = pwm(code_word_bits(ENC, SER), symbols_per_te=2)
        self.check(KeeLoqPWM.decode_message(data))

    def test_preamble_only(self):
        word = KeeLoqPWM.decode_message(PREAMBLE)
        self.assertFalse(word.ok)
        self.assertEqual(word.status, "Preamble only")

    def test_incomplete_and_invalid(self):
        data = pwm(code_word_bits(ENC, SER))
        word = KeeLoqPWM.decode_message(data[:90])
        self.assertFalse(word.ok)
        self.assertTrue(word.status.startswith("Incomplete"))

        broken = data[:30] + "000" + data[33:]
        word = KeeLoqPWM.decode_message(broken)
        self.assertFalse(word.ok)
        self.assertEqual(word.error_bit, 10)

    def test_empty(self):
        self.assertFalse(KeeLoqPWM.decode_message("").ok)

    def test_te_microseconds(self):
        word = KeeLoqPWM.decode_message(pwm(code_word_bits(ENC, SER), 2))
        self.assertAlmostEqual(
            KeeLoqPWM.te_microseconds(word, 400, 2e6), 400.0, places=3
        )
        self.assertIsNone(KeeLoqPWM.te_microseconds(word, 400, None))

    def test_dialog(self):
        def msg(bits):
            return Message([int(b) for b in bits], 0, MessageType("t"))

        messages = [
            msg(PREAMBLE),
            msg(pwm(code_word_bits(ENC, SER))),
            msg(pwm(code_word_bits(0x11223344, SER))),
        ]
        dialog = KeeLoqCodeWordDialog(messages, sample_rate=1e6)
        self.assertEqual(dialog.table.rowCount(), 2)  # only valid ones

        got = []
        dialog.send_to_toolkit.connect(lambda *a: got.append(a))
        dialog.table.selectAll()
        dialog._on_send_to_toolkit()
        self.assertEqual(got, [(ENC, SER, 0x11223344)])

        dialog.chk_only_ok.setChecked(False)
        self.assertEqual(dialog.table.rowCount(), 3)
        dialog.close()
