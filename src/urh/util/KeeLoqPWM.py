"""
KeeLoq code word decoder for demodulated (TE-level) bits.

Adapted from the PulseView/sigrok "KeeLoq CodeWord Decoder" by Andrea Orazi
(https://github.com/rzondr/KeeLoq_decoder, GPL v2 or later). The original works
on a logic analyzer trace; here it works on the bits URH already demodulated.

A KeeLoq transmission (HCS200/300/301...) is PWM keyed:

    Preamble : 23 TE alternating high/low
    Header   : 10 TE low
    Data     : 66 bits, each one 3 TE long, LSB first
                 bit 1 = 1 TE high + 2 TE low   ("100")
                 bit 0 = 2 TE high + 1 TE low   ("110")

    bits  0..31 Encrypted portion
    bits 32..59 Serial number
    bits 60..63 Button code (S3, S0, S1, S2)
    bit  64     V-Low (battery low)
    bit  65     RPT (button held, repeated word)

URH usually splits a transmission into a preamble message and a data message
(the header is the pause between them), so both layouts are handled. When one
URH bit is not exactly one TE, the run lengths are normalized first.
"""

from collections import Counter

DATA_BITS = 66
TE_PER_BIT = 3
MIN_PREAMBLE_RUNS = 10  # alternating runs needed to call it a preamble
MIN_HEADER_TE = 6  # nominal 10 TE low; shorter lows are data

# Nominal TE range from the datasheets (seconds), used only to flag odd timing
TE_MIN_US = 280
TE_MAX_US = 580


class CodeWord:
    """Result of decoding one message."""

    __slots__ = (
        "status",
        "ok",
        "bits",
        "encrypted",
        "serial",
        "button",
        "v_low",
        "repeat",
        "te_symbols",
        "has_preamble",
        "has_header",
        "error_bit",
    )

    def __init__(self):
        self.status = ""
        self.ok = False
        self.bits = ""  # the 66 decoded KeeLoq bits, in transmission order
        self.encrypted = None
        self.serial = None
        self.button = None  # "S3 S0 S1 S2" bits as a string, e.g. "0100"
        self.v_low = None
        self.repeat = None
        self.te_symbols = 1.0  # URH symbols per TE
        self.has_preamble = False
        self.has_header = False
        self.error_bit = None

    @property
    def encrypted_hex(self) -> str:
        return "" if self.encrypted is None else "{0:08X}".format(self.encrypted)

    @property
    def serial_hex(self) -> str:
        return "" if self.serial is None else "{0:07X}".format(self.serial)

    @property
    def button_text(self) -> str:
        """Pressed buttons, e.g. 'S0' or 'S0+S1' (S3 S0 S1 S2 order of the bits)."""
        if self.button is None:
            return ""
        names = ("S3", "S0", "S1", "S2")
        pressed = [n for n, b in zip(names, self.button) if b == "1"]
        return "+".join(pressed) if pressed else "none"


def _runs(bits: str):
    runs = []
    for b in bits:
        if runs and runs[-1][0] == b:
            runs[-1][1] += 1
        else:
            runs.append([b, 1])
    return runs


def estimate_te(bits: str) -> float:
    """
    Number of URH symbols per TE. It is the shortest run length that occurs
    several times (the last run is ignored, it is cut by the pause).
    """
    runs = _runs(bits)[:-1]
    if not runs:
        return 1.0
    counts = Counter(length for _, length in runs)
    for length in sorted(counts):
        if counts[length] >= 3:
            return float(length)
    return float(min(counts))


def normalize(bits: str, te: float) -> str:
    """Rebuild the bit string with exactly one character per TE."""
    out = []
    for value, length in _runs(bits):
        out.append(value * max(1, int(round(length / te))))
    return "".join(out)


def _is_preamble_only(runs) -> bool:
    return len(runs) >= MIN_PREAMBLE_RUNS and all(length == 1 for _, length in runs)


def decode_message(bits: str) -> CodeWord:
    """
    Decode the bits of one URH message (a string of '0' and '1', one char per
    URH symbol) as a KeeLoq code word.
    """
    word = CodeWord()
    bits = "".join(c for c in bits if c in "01")
    if not bits:
        word.status = "Empty message"
        return word

    te = estimate_te(bits)
    word.te_symbols = te
    s = normalize(bits, te)
    runs = _runs(s)

    # Preamble only (23 TE alternating) -> nothing to decode
    if _is_preamble_only(runs):
        word.has_preamble = True
        word.status = "Preamble only"
        return word

    # Optional preamble + header in front of the data
    start = 0
    if len(runs) > 2 and all(l == 1 for _, l in runs[:MIN_PREAMBLE_RUNS]):
        word.has_preamble = True
    pos = 0
    for value, length in runs:
        pos += length
        if value == "0" and length >= MIN_HEADER_TE:
            start = pos
            word.has_header = True
            break
    if word.has_preamble and not word.has_header:
        word.status = "Preamble without header"
        return word

    data = s[start:]
    decoded = []
    i = 0
    while len(decoded) < DATA_BITS and i < len(data):
        chunk = data[i : i + TE_PER_BIT]
        if chunk == "100":
            decoded.append("1")
        elif chunk == "110":
            decoded.append("0")
        elif len(chunk) < TE_PER_BIT and len(decoded) == DATA_BITS - 1:
            # last bit: the trailing low merges with the pause, so it may
            # arrive as "1" / "10" (bit 1) or "11" (bit 0)
            if chunk in ("1", "10"):
                decoded.append("1")
            elif chunk == "11":
                decoded.append("0")
            else:
                word.error_bit = len(decoded)
                break
        else:
            word.error_bit = len(decoded)
            break
        i += TE_PER_BIT

    word.bits = "".join(decoded)
    if word.error_bit is not None:
        word.status = "Invalid PWM at bit {0}".format(word.error_bit)
        return word
    if len(decoded) < DATA_BITS:
        word.status = "Incomplete ({0}/{1} bits)".format(len(decoded), DATA_BITS)
        return word

    # LSB is transmitted first, so the first bit is the least significant one
    word.encrypted = int(word.bits[0:32][::-1], 2)
    word.serial = int(word.bits[32:60][::-1], 2)
    word.button = word.bits[60:64]
    word.v_low = word.bits[64] == "1"
    word.repeat = word.bits[65] == "1"
    word.ok = True
    word.status = "OK"
    return word


def decode_messages(messages_bits) -> list:
    """Decode an iterable of message bit strings."""
    return [decode_message(b) for b in messages_bits]


def te_microseconds(word: CodeWord, samples_per_symbol, sample_rate):
    """TE duration in microseconds, or None when it is not known."""
    if not samples_per_symbol or not sample_rate:
        return None
    return word.te_symbols * samples_per_symbol / sample_rate * 1e6
