from unittest import mock

from PyQt6.QtCore import Qt

from tests.QtTestCase import QtTestCase
from urh.controller.dialogs.ExternalToolDialog import ExternalToolDialog
from urh.util import ExternalTool


# PWM bits for a 66-bit KeeLoq code word with a preamble and header, built
# the same way as tests/test_keeloq_pwm.py, so the dialog has valid rows to
# show and check.
def _pwm_bit(bit):
    return "100" if bit == "1" else "110"


def _code_word_bits(encrypted, serial, button, v_low=0, repeat=0):
    # encrypted/serial are transmitted LSB first; button is 4 raw bits in
    # "S3 S0 S1 S2" position order (see KeeLoqPWM.CodeWord.button_text), not
    # a binary number, so build it bit-position by bit-position.
    enc_bits = "".join(str((encrypted >> i) & 1) for i in range(32))
    serial_bits = "".join(str((serial >> i) & 1) for i in range(28))
    button_bits = "".join(str((button >> i) & 1) for i in range(4))
    data = enc_bits + serial_bits + button_bits + str(v_low) + str(repeat)
    assert len(data) == 66
    preamble = "10" * 12
    header = "1" + "0" * 10
    pwm = "".join(_pwm_bit(b) for b in data)
    return preamble + header + pwm


class _FakeMessage:
    def __init__(self, bits):
        self.plain_bits_str = bits


class TestExternalToolDialog(QtTestCase):
    def setUp(self):
        super().setUp()
        # don't let the real saved settings leak into/out of the test
        self._path_patch = mock.patch.object(ExternalTool, "get_executable", return_value="")
        self._params_patch = mock.patch.object(
            ExternalTool, "get_extra_parameters", return_value=""
        )
        # tests build the expected argument list themselves; the real
        # "-b -t91" default would otherwise leak into every assertion
        self._final_params_patch = mock.patch.object(
            ExternalTool, "get_final_parameters", return_value=""
        )
        self._path_patch.start()
        self._params_patch.start()
        self._final_params_patch.start()
        self.addCleanup(self._path_patch.stop)
        self.addCleanup(self._params_patch.stop)
        self.addCleanup(self._final_params_patch.stop)

    def test_only_valid_messages_are_listed(self):
        valid = _FakeMessage(_code_word_bits(0xA1B2C3D4, 0x0FFDAE3, 0b0010))
        invalid = _FakeMessage("101010")
        dialog = ExternalToolDialog([valid, invalid])
        self.assertEqual(dialog.table.rowCount(), 1)
        self.assertEqual(dialog.table.item(0, 2).text(), "A1B2C3D4")
        dialog.close()

    def test_checked_rows_build_the_argument(self):
        valid = _FakeMessage(_code_word_bits(0xA1B2C3D4, 0x0FFDAE3, 0b0010))
        dialog = ExternalToolDialog([valid])
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        args = dialog._build_arguments()
        self.assertEqual(args, ["A1B2C3D4:0FFDAE3:S0"])
        dialog.close()

    def test_extra_parameters_come_before_messages(self):
        valid = _FakeMessage(_code_word_bits(0xA1B2C3D4, 0x0FFDAE3, 0b0010))
        dialog = ExternalToolDialog([valid])
        dialog.edit_params.setText("--mode fast")
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        args = dialog._build_arguments()
        self.assertEqual(args, ["--mode", "fast", "A1B2C3D4:0FFDAE3:S0"])
        dialog.close()

    def test_unchecked_rows_are_not_included(self):
        valid = _FakeMessage(_code_word_bits(0xA1B2C3D4, 0x0FFDAE3, 0b0010))
        dialog = ExternalToolDialog([valid])
        args = dialog._build_arguments()
        self.assertEqual(args, [])
        dialog.close()

    def test_run_disabled_without_saved_path(self):
        valid = _FakeMessage(_code_word_bits(0xA1B2C3D4, 0x0FFDAE3, 0b0010))
        dialog = ExternalToolDialog([valid])
        self.assertFalse(dialog.btn_run.isEnabled())
        dialog.close()

    def test_final_parameters_come_after_messages(self):
        valid = _FakeMessage(_code_word_bits(0xA1B2C3D4, 0x0FFDAE3, 0b0010))
        dialog = ExternalToolDialog([valid])
        dialog.edit_params.setText("--mode fast")
        dialog.edit_final_params.setText("-b -t91")
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        args = dialog._build_arguments()
        self.assertEqual(
            args, ["--mode", "fast", "A1B2C3D4:0FFDAE3:S0", "-b", "-t91"]
        )
        dialog.close()

    def test_bat_script_is_run_through_cmd_exe(self):
        valid = _FakeMessage(_code_word_bits(0xA1B2C3D4, 0x0FFDAE3, 0b0010))
        dialog = ExternalToolDialog([valid])
        dialog.edit_path.setText(__file__.replace(".py", ".bat"))  # any path, need not exist
        dialog.edit_final_params.setText("-b -t91")
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)

        with mock.patch("os.path.isfile", return_value=True), mock.patch.object(
            ExternalToolDialog, "_start_detached", return_value=True
        ) as started:
            dialog._on_run()

        self.assertEqual(started.call_args[0][0], "cmd.exe")
        self.assertEqual(
            started.call_args[0][1][:2], ["/c", dialog.edit_path.text()]
        )
        self.assertIn("A1B2C3D4:0FFDAE3:S0", started.call_args[0][1])
        self.assertEqual(started.call_args[0][1][-2:], ["-b", "-t91"])
        dialog.close()

    def test_exe_is_run_directly(self):
        valid = _FakeMessage(_code_word_bits(0xA1B2C3D4, 0x0FFDAE3, 0b0010))
        dialog = ExternalToolDialog([valid])
        dialog.edit_path.setText(__file__.replace(".py", ".exe"))

        with mock.patch("os.path.isfile", return_value=True), mock.patch.object(
            ExternalToolDialog, "_start_detached", return_value=True
        ) as started:
            dialog._on_run()

        self.assertEqual(started.call_args[0][0], dialog.edit_path.text())
        dialog.close()


class TestExternalToolDefaultFinalParameters(QtTestCase):
    def test_default_before_anything_was_saved(self):
        with mock.patch.object(ExternalTool.settings, "read", return_value=ExternalTool._UNSET):
            self.assertEqual(ExternalTool.get_final_parameters(), "-b -t91")

    def test_empty_string_once_user_clears_and_saves_it(self):
        with mock.patch.object(ExternalTool.settings, "read", return_value=""):
            self.assertEqual(ExternalTool.get_final_parameters(), "")
