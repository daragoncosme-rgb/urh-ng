import unittest

from urh.awre.ProtocolMatcher import (
    ProtocolMatcher,
    protocol_category,
    _is_preamble_only,
)
from urh.awre.protocol_db import PROTOCOL_DATABASE
from urh.signalprocessing.Message import Message
from urh.signalprocessing.MessageType import MessageType


def entry(name):
    return next(p for p in PROTOCOL_DATABASE if p["name"].startswith(name))


class TestProtocolMatcherCategories(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(protocol_category(entry("CAME gate remote")), "remote")
        self.assertEqual(protocol_category(entry("Microchip HCS200")), "remote")
        self.assertEqual(protocol_category(entry("Security+ 2.0 (Keyfob)")), "remote")
        self.assertEqual(protocol_category(entry("Subaru car key")), "car key")
        self.assertEqual(protocol_category(entry("Ford TPMS")), "tpms")
        self.assertEqual(
            protocol_category(entry("Fine Offset Electronics WH1080")), "sensor"
        )
        self.assertEqual(protocol_category(entry("Clipsal CMR113")), "meter")

    def test_preamble_only(self):
        self.assertTrue(_is_preamble_only("10101010101010101010101"))
        self.assertFalse(_is_preamble_only("110100110110100100110"))

    def keeloq_messages(self):
        """KeeLoq-like capture: separate preamble message + 66 bit PWM frame"""
        mt = MessageType("test")
        import random

        rnd = random.Random(1)
        msgs = []
        for _ in range(6):
            msgs.append(Message([1, 0] * 11 + [1], 0, mt, samples_per_symbol=760))
            data = "".join("110" if rnd.random() < 0.5 else "100" for _ in range(66))
            msgs.append(Message([int(b) for b in data], 0, mt, samples_per_symbol=760))
        return msgs

    def test_keeloq_remote_ranked_above_sensors(self):
        matcher = ProtocolMatcher(self.keeloq_messages(), [], sample_rate=1e6)
        matches = matcher.find_matches(max_results=10)
        self.assertTrue(matches)
        top = matches[:5]
        self.assertTrue(all(m.category in ("remote", "car key") for m in top), top)
        self.assertTrue(any("KeeLoq" in m.name for m in top), top)
        self.assertIn("timing", matches[0].details)

    def test_frames_skip_preamble_messages(self):
        frames = ProtocolMatcher._select_frames(self.keeloq_messages())
        self.assertEqual(len(frames), 6)
        self.assertTrue(all(len(f) == 198 for f in frames))


if __name__ == "__main__":
    unittest.main()
