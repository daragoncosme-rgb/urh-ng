import time
from collections import OrderedDict

import numpy as np

from multiprocessing.connection import Connection
from urh.dev.native.Device import Device

from urh.dev.native.lib import rtlsdr
from urh.util.Logger import logger


class RTLSDR(Device):
    DEVICE_LIB = rtlsdr
    ASYNCHRONOUS = False
    DEVICE_METHODS = Device.DEVICE_METHODS.copy()
    DEVICE_METHODS.update(
        {
            Device.Command.SET_RF_GAIN.name: "set_tuner_gain",
            Device.Command.SET_RF_GAIN.name + "_get_allowed_values": "get_tuner_gains",
            Device.Command.SET_BANDWIDTH.name: "set_tuner_bandwidth",
            Device.Command.SET_FREQUENCY_CORRECTION.name: "set_freq_correction",
            Device.Command.SET_DIRECT_SAMPLING_MODE.name: "set_direct_sampling",
            Device.Command.SET_BIAS_TEE_ENABLED.name: "set_bias_tee",
        }
    )

    DATA_TYPE = np.int8

    @classmethod
    def get_device_list(cls):
        return rtlsdr.get_device_list()

    @classmethod
    def setup_device(cls, ctrl_connection: Connection, device_identifier):
        # identifier gets set in self.receive_process_arguments
        device_number = int(device_identifier)
        ret = rtlsdr.open(device_number)
        ctrl_connection.send("OPEN (#{}):{}".format(device_number, ret))
        return ret == 0

    _last_frequency = None

    @classmethod
    def process_command(cls, command, ctrl_connection, is_tx: bool):
        result = super().process_command(command, ctrl_connection, is_tx)
        if isinstance(command, tuple):
            tag, value = command
            if tag == cls.Command.SET_FREQUENCY.name:
                cls._last_frequency = value
            elif (
                tag == cls.Command.SET_DIRECT_SAMPLING_MODE.name
                and cls._last_frequency is not None
            ):
                # Changing the direct sampling mode re-initializes the tuner
                super().process_command(
                    (cls.Command.SET_FREQUENCY.name, cls._last_frequency),
                    ctrl_connection,
                    is_tx,
                )
        return result

    @classmethod
    def init_device(
        cls, ctrl_connection: Connection, is_tx: bool, parameters: OrderedDict
    ) -> bool:
        if not super().init_device(ctrl_connection, is_tx, parameters):
            return False

        # Right after opening, the tuner sometimes rejects the first frequency
        # (error -9) and keeps receiving on another frequency: the window then
        # only shows noise. Check the frequency and tune again if needed.
        freq = parameters.get(cls.Command.SET_FREQUENCY.name)
        if freq is not None:
            for _ in range(3):
                try:
                    tuned = rtlsdr.get_center_freq()
                except Exception:
                    break
                if abs(int(tuned) - int(freq)) <= 1:
                    break
                time.sleep(0.05)
                cls.process_command(
                    (cls.Command.SET_FREQUENCY.name, freq), ctrl_connection, is_tx
                )
        return True

    @classmethod
    def prepare_sync_receive(cls, ctrl_connection: Connection):
        ret = rtlsdr.reset_buffer()
        ctrl_connection.send("RESET_BUFFER:" + str(ret))
        return ret

    _empty_reads = 0

    @classmethod
    def receive_sync(cls, data_conn: Connection):
        data = rtlsdr.read_sync()
        if not data:
            # read failed (e.g. device unplugged): do not spin at full CPU
            cls._empty_reads += 1
            if cls._empty_reads == 50:
                logger.warning("RTL-SDR does not deliver samples")
            time.sleep(0.01)
            return
        cls._empty_reads = 0
        data_conn.send_bytes(data)

    @classmethod
    def shutdown_device(cls, ctrl_connection, is_tx: bool):
        logger.debug("RTLSDR: closing device")
        ret = rtlsdr.close()
        ctrl_connection.send("CLOSE:" + str(ret))

    def __init__(
        self, freq, gain, srate, device_number, resume_on_full_receive_buffer=False
    ):
        super().__init__(
            center_freq=freq,
            sample_rate=srate,
            bandwidth=0,
            gain=gain,
            if_gain=1,
            baseband_gain=1,
            resume_on_full_receive_buffer=resume_on_full_receive_buffer,
        )

        self.success = 0
        self.bandwidth_is_adjustable = (
            self.get_bandwidth_is_adjustable()
        )  # e.g. not in Manjaro Linux / Ubuntu 14.04

        self.device_number = device_number

        self.error_codes = {-100: "Method not available in installed driver."}

    @staticmethod
    def get_bandwidth_is_adjustable():
        return rtlsdr.bandwidth_is_adjustable()

    @property
    def device_parameters(self):
        return OrderedDict(
            [
                (self.Command.SET_FREQUENCY.name, self.frequency),
                (self.Command.SET_SAMPLE_RATE.name, self.sample_rate),
                (self.Command.SET_BANDWIDTH.name, self.bandwidth),
                (self.Command.SET_FREQUENCY_CORRECTION.name, self.freq_correction),
                (self.Command.SET_DIRECT_SAMPLING_MODE.name, self.direct_sampling_mode),
                (self.Command.SET_RF_GAIN.name, self.gain),
                (self.Command.SET_BIAS_TEE_ENABLED.name, self.bias_tee_enabled),
                ("identifier", self.device_number),
            ]
        )

    @property
    def has_multi_device_support(self):
        return True

    def set_device_bandwidth(self, bandwidth):
        if self.bandwidth_is_adjustable:
            super().set_device_bandwidth(bandwidth)
        else:
            logger.warning(
                "Setting the bandwidth is not supported by your RTL-SDR driver version."
            )

    @staticmethod
    def bytes_to_iq(buffer):
        # RTL-SDR samples are unsigned bytes centred at 127.5. Reading them as
        # int8 and subtracting 127 wrapped around: a full scale sample (255)
        # became -128 instead of +128, so strong (clipping) signals got spikes.
        samples = np.frombuffer(buffer, dtype=np.uint8).astype(np.int16) - 127
        return np.clip(samples, -128, 127).astype(np.int8).reshape((-1, 2), order="C")
