import sys
import types
import unittest
from unittest import mock


class FakeConnection(object):
    def __init__(self):
        self.messages = []

    def send(self, msg):
        self.messages.append(msg)


def make_fake_lib(fail_first_tune=True):
    lib = types.ModuleType("rtlsdr")
    state = {"freq": 0, "calls": [], "fail": fail_first_tune}

    def set_center_freq(f):
        state["calls"].append(("freq", f))
        if state["fail"]:
            state["fail"] = False
            state["freq"] = 0
            return -9
        state["freq"] = f
        return 0

    def set_direct_sampling(on):
        state["calls"].append(("ds", on))
        state["freq"] = 0  # tuner re-initialized
        return 0

    lib.open = lambda n: 0
    lib.set_center_freq = set_center_freq
    lib.get_center_freq = lambda: state["freq"]
    lib.set_sample_rate = lambda v: state["calls"].append(("sr", v)) or 0
    lib.set_tuner_bandwidth = lambda v: 0
    lib.set_freq_correction = lambda v: 0
    lib.set_direct_sampling = set_direct_sampling
    lib.set_tuner_gain = lambda v: 0
    lib.get_tuner_gains = lambda: [0, 370, 496]
    lib.set_bias_tee = lambda v: 0
    lib.state = state
    return lib


class TestRTLSDRTuning(unittest.TestCase):
    def setUp(self):
        self.lib = make_fake_lib()
        try:
            from urh.dev.native.RTLSDR import RTLSDR, rtlsdr  # noqa
            import urh.dev.native.RTLSDR as module
        except ImportError:
            # Native library not built: use the fake one
            sys.modules["urh.dev.native.lib.rtlsdr"] = self.lib
            import urh.dev.native.RTLSDR as module
        self.patcher = mock.patch.object(module, "rtlsdr", self.lib)
        self.patcher.start()
        RTLSDR = module.RTLSDR
        self.old_lib = RTLSDR.DEVICE_LIB
        RTLSDR.DEVICE_LIB = self.lib
        RTLSDR._last_frequency = None
        self.RTLSDR = RTLSDR

    def tearDown(self):
        self.RTLSDR.DEVICE_LIB = self.old_lib
        self.patcher.stop()

    def params(self):
        cmd = self.RTLSDR.Command
        from collections import OrderedDict

        return OrderedDict(
            [
                (cmd.SET_FREQUENCY.name, 433920000),
                (cmd.SET_SAMPLE_RATE.name, 2000000),
                (cmd.SET_BANDWIDTH.name, 2000000),
                (cmd.SET_FREQUENCY_CORRECTION.name, 1),
                (cmd.SET_DIRECT_SAMPLING_MODE.name, 0),
                (cmd.SET_RF_GAIN.name, 370),
                ("identifier", 0),
            ]
        )

    def test_failed_first_tune_is_retried(self):
        conn = FakeConnection()
        self.assertTrue(self.RTLSDR.init_device(conn, False, self.params()))
        self.assertEqual(self.lib.state["freq"], 433920000)
        # the last tuning happens after the direct sampling mode re-initialized
        # the tuner
        order = [c[0] for c in self.lib.state["calls"]]
        self.assertGreater(
            len(order) - 1 - order[::-1].index("freq"), order.index("ds")
        )

    def test_direct_sampling_change_retunes(self):
        conn = FakeConnection()
        self.RTLSDR.init_device(conn, False, self.params())
        cmd = self.RTLSDR.Command
        self.RTLSDR.process_command((cmd.SET_DIRECT_SAMPLING_MODE.name, 0), conn, False)
        self.assertEqual(self.lib.state["freq"], 433920000)


if __name__ == "__main__":
    unittest.main()
