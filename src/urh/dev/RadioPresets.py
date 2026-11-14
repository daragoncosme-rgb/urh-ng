"""
Ready-made receiver settings for common remote controls and bands.

A preset sets the center frequency, sample rate and bandwidth. Values the
selected device cannot use are adapted to it (e.g. an RTL-SDR gets at most
2.4 MSps, a HackRF at least 2 MSps).
"""
from collections import namedtuple

Preset = namedtuple("Preset", "group name frequency sample_rate note")

MHz = 1e6

# Highest sample rate that runs without losing samples on these devices
PRACTICAL_MAX_SAMPLE_RATE = {"RTL-SDR": 2.4 * MHz, "RTL-TCP": 2.4 * MHz}

PRESETS = [
    # ---------------------------------------------------------------- Europe
    Preset(
        "Europe",
        "433.92 MHz - Garage/gate remotes, car keys, alarms",
        433.92 * MHz,
        2 * MHz,
        "Most remotes in Europe: gates and garages (CAME, Nice, BFT, FAAC...), "
        "car keys, alarm sensors, doorbells, weather stations, TPMS. "
        "Usually OOK/ASK, some FSK. Shows 432.92 - 434.92 MHz.",
    ),
    Preset(
        "Europe",
        "433.42 MHz - Somfy RTS blinds and awnings",
        433.42 * MHz,
        2 * MHz,
        "Somfy RTS remotes (Telis, Situo...) for blinds, awnings and shutters. OOK.",
    ),
    Preset(
        "Europe",
        "868.3 MHz - HomeMatic, EnOcean, Hormann BiSecur, alarms",
        868.3 * MHz,
        2 * MHz,
        "868 MHz remotes and smart home: HomeMatic (FSK), EnOcean, "
        "Hormann BiSecur garage remotes, alarm systems, LoRa. "
        "Shows 867.3 - 869.3 MHz.",
    ),
    Preset(
        "Europe",
        "869.05 MHz - io-homecontrol (Somfy io, Velux)",
        869.05 * MHz,
        2.4 * MHz,
        "io-homecontrol uses 868.25, 868.95 and 869.85 MHz; this setting shows "
        "all three (needs at least 2 MSps).",
    ),
    Preset(
        "Europe",
        "868.95 MHz - Wireless M-Bus meters (T/C mode)",
        868.95 * MHz,
        2 * MHz,
        "Water, heat and electricity meters (Wireless M-Bus T1/C1). FSK.",
    ),
    Preset(
        "Europe",
        "40.685 MHz - Old gate and garage remotes",
        40.685 * MHz,
        2 * MHz,
        "Older remotes on 40.665 / 40.685 MHz. Needs a receiver that tunes "
        "below 50 MHz (RTL-SDR R820T, HackRF...).",
    ),
    Preset(
        "Europe",
        "27.145 MHz - Old 27 MHz remotes",
        27.145 * MHz,
        2 * MHz,
        "Old 26.995 - 27.255 MHz remotes and toys. Needs a receiver that tunes "
        "this low (HackRF, RTL-SDR with R820T, or direct sampling).",
    ),
    # ---------------------------------------------------------- North America
    Preset(
        "North America",
        "315 MHz - Car keys, garage remotes, TPMS",
        315 * MHz,
        2 * MHz,
        "Most car keys and many garage remotes in the US and Japan, TPMS. "
        "OOK/ASK or FSK.",
    ),
    Preset(
        "North America",
        "390 MHz - Chamberlain/LiftMaster, Genie",
        390 * MHz,
        2 * MHz,
        "Garage door openers (Chamberlain, LiftMaster, Craftsman, Genie). "
        "Security+ 2.0 remotes also use 310 and 315 MHz.",
    ),
    Preset(
        "North America",
        "310 MHz - Garage and gate remotes",
        310 * MHz,
        2 * MHz,
        "LiftMaster Security+ 2.0, Genie, Overhead Door, Linear and other "
        "gate remotes.",
    ),
    Preset(
        "North America",
        "318 MHz - Linear MegaCode gate remotes",
        318 * MHz,
        2 * MHz,
        "Linear MegaCode and DoorKing gate and access remotes.",
    ),
    Preset(
        "North America",
        "300 MHz - Older gate/garage remotes (dip switch)",
        300 * MHz,
        2 * MHz,
        "Older Linear, Stanley, Multi-Code and dip switch remotes.",
    ),
    Preset(
        "North America",
        "303.875 MHz - Ceiling fan remotes",
        303.875 * MHz,
        2 * MHz,
        "Ceiling fan and light remotes (Hampton Bay, Harbor Breeze...).",
    ),
    Preset(
        "North America",
        "345 MHz - Honeywell/2GIG alarm sensors",
        345 * MHz,
        2 * MHz,
        "Wireless alarm door/window sensors and keyfobs (Honeywell 5800, 2GIG).",
    ),
    Preset(
        "North America",
        "915 MHz - ISM sensors, LoRa",
        915 * MHz,
        2 * MHz,
        "902 - 928 MHz ISM band: sensors, meters, LoRa.",
    ),
    # ------------------------------------------------------------ Other
    Preset(
        "Other",
        "418 MHz - Some UK alarms and keyfobs",
        418 * MHz,
        2 * MHz,
        "Some UK alarm systems, keyfobs and car keys.",
    ),
    # ------------------------------------------------- Band scans (search)
    Preset(
        "Band scan (search for signals)",
        "Scan 433 MHz ISM band (433.05 - 434.79 MHz)",
        433.92 * MHz,
        2.4 * MHz,
        "Shows the whole 433 MHz band. Use the Spectrum Analyzer with Peak hold, "
        "press the remote a few times and click the peak to tune to it.",
    ),
    Preset(
        "Band scan (search for signals)",
        "Scan 868 MHz SRD band (863 - 870 MHz)",
        868 * MHz,
        8 * MHz,
        "Whole 868 MHz band with fast receivers (HackRF, Pluto...). "
        "An RTL-SDR shows 866.8 - 869.2 MHz, where most 868 MHz remotes are.",
    ),
    Preset(
        "Band scan (search for signals)",
        "Scan 300 - 320 MHz (US remotes)",
        310 * MHz,
        20 * MHz,
        "300, 303.875, 310, 315 and 318 MHz at once with a HackRF "
        "(20 MSps). An RTL-SDR shows 308.8 - 311.2 MHz.",
    ),
    Preset(
        "Band scan (search for signals)",
        "Scan 902 - 928 MHz ISM band (US)",
        915 * MHz,
        20 * MHz,
        "Most of the US 915 MHz band with a HackRF (20 MSps).",
    ),
]


def _clamp_to(conf_value, value):
    """Fit value into a device range (range object) or list of allowed values."""
    if conf_value is None:
        return value
    if not hasattr(conf_value, "start"):
        allowed = sorted(v for v in conf_value if v)
        if not allowed:
            return value
        lower = [v for v in allowed if v <= value]
        return lower[-1] if lower else allowed[0]
    lo, hi = conf_value.start, conf_value.stop
    return min(max(value, lo), hi)


def adapt_to_device(preset: Preset, device_name: str, device_conf: dict):
    """
    :return: (frequency, sample_rate, bandwidth, supported) for the device.
             supported is False if the device cannot tune to the frequency.
    """
    frequency = preset.frequency
    supported = True
    cf = device_conf.get("center_freq")
    if cf is not None and hasattr(cf, "start"):
        supported = cf.start <= frequency <= cf.stop

    sample_rate = preset.sample_rate
    practical = PRACTICAL_MAX_SAMPLE_RATE.get(device_name)
    if practical:
        sample_rate = min(sample_rate, practical)
    sample_rate = _clamp_to(device_conf.get("sample_rate"), sample_rate)

    bandwidth = _clamp_to(device_conf.get("bandwidth"), sample_rate)
    return frequency, sample_rate, bandwidth, supported
