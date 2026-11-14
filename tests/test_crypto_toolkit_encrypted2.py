from tests.QtTestCase import QtTestCase
from urh.controller.CompareFrameController import CompareFrameController
from urh.controller.dialogs.KeeLoqDialog import KeeLoqDialog
from urh.signalprocessing.Message import Message
from urh.signalprocessing.MessageType import MessageType


def _message_with_encrypted(value: int) -> Message:
    """A message whose bits 10..41 are an 'Encrypted' label holding value."""
    mt = MessageType("keeloq")
    # 32 encrypted bits LSB first, because the extractor reverses them
    enc_bits = "{0:032b}".format(value)[::-1]
    bits = "1010101010" + enc_bits + "0000"
    msg = Message([int(b) for b in bits], 0, mt)
    msg.message_type.add_protocol_label(10, 41, name="Encrypted")
    return msg


class TestCryptoToolkitEncrypted2(QtTestCase):
    def test_extract_encrypted(self):
        msg = _message_with_encrypted(0x1234ABCD)
        self.assertEqual(
            CompareFrameController._encrypted_from_message(msg), 0x1234ABCD
        )

    def test_extract_none_without_label(self):
        msg = Message([1, 0, 1, 0], 0, MessageType("t"))
        self.assertIsNone(CompareFrameController._encrypted_from_message(msg))

    def test_set_encrypted2_formats_hex_and_shows_tab(self):
        dialog = KeeLoqDialog(encrypted=0xAABBCCDD)
        dialog._tabs.setCurrentIndex(2)
        dialog.set_encrypted2(0x0012AB34)
        self.assertEqual(dialog.edit_encrypted2.text(), "0012AB34")
        self.assertEqual(dialog._tabs.currentIndex(), 0)
        # Encrypted #1 is left untouched
        self.assertEqual(dialog.edit_encrypted.text(), "AABBCCDD")
        dialog.close()

    def test_row_selection_fills_open_dialog(self):
        self.add_signal_to_form("esaver.complex16s")
        cfc = self.form.compare_frame_controller

        msg2 = _message_with_encrypted(0x33334444)

        dialog = KeeLoqDialog(parent=cfc, encrypted=0x11112222)
        cfc._show_modeless(dialog)
        self.assertIn(dialog, cfc._modeless_dialogs)

        # Selecting a message row copies its encrypted field to #2
        cfc._CompareFrameController__fill_crypto_toolkit_encrypted2(msg2)
        self.assertEqual(dialog.edit_encrypted2.text(), "33334444")

        # A message without an encrypted label leaves the field unchanged
        cfc._CompareFrameController__fill_crypto_toolkit_encrypted2(
            Message([1, 0, 1, 0], 0, MessageType("t"))
        )
        self.assertEqual(dialog.edit_encrypted2.text(), "33334444")
        dialog.close()
