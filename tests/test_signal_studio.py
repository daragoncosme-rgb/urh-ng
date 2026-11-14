import os
import tempfile
import unittest

from urh.signalprocessing.Message import Message
from urh.signalprocessing.ProtocolAnalyzer import ProtocolAnalyzer
from urh.util import SignalStudio


class TestSignalStudio(unittest.TestCase):
    def test_search_prefers_release(self):
        with tempfile.TemporaryDirectory() as root:
            base = os.path.join(root, "UrhSignalStudio_v2.2", "UrhSignalStudio")
            debug = os.path.join(base, "bin", "Debug", "net8.0-windows")
            release = os.path.join(base, "bin", "Release", "net8.0-windows")
            obj = os.path.join(base, "obj", "Debug")
            for d in (debug, release, obj):
                os.makedirs(d)
                open(os.path.join(d, SignalStudio.EXE_NAME), "w").close()
            os.makedirs(os.path.join(root, "Other"))
            found = SignalStudio.search_executable([root])
            self.assertEqual(found, os.path.join(release, SignalStudio.EXE_NAME))

    def test_search_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(SignalStudio.search_executable([root]))

    def test_export_protocol(self):
        pa = ProtocolAnalyzer(None)
        pa.messages = [
            Message([1, 0, 1, 1, 0], 0, pa.default_message_type),
            Message([1, 1, 1, 0, 0, 0], 0, pa.default_message_type),
        ]
        with tempfile.TemporaryDirectory() as folder:
            filename = SignalStudio.export_protocol(
                pa, [], [], name="Rodas A/garage:1", folder=folder
            )
            self.assertTrue(filename.endswith(".proto.xml"))
            self.assertEqual(os.path.dirname(filename), folder)
            with open(filename) as f:
                content = f.read()
            self.assertIn('bits="10110"', content)
            self.assertIn('bits="111000"', content)


if __name__ == "__main__":
    unittest.main()
