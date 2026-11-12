# Decodings for URH-NG

Ready-to-use decodings: 19 built-in URH decoding chains and 3 compiled
external decoders (HomeMatic and EnOcean) for Windows, Linux and macOS.

The Windows portable version and installer built with
`data/windows/build_windows.ps1` include this folder as `decoders\`.
URH and URH-NG share the same `decodings.txt`, so the decoders show up in both.

## Installation

Close URH before installing.

| System | How |
|---|---|
| Windows 10/11 (x64) | Installed automatically by the URH-NG installer. Portable version: double-click `decoders\install-decoders.bat` |
| Linux (x64 / ARM64) | `sh data/decoders/install.sh` |
| macOS (Intel / Apple Silicon) | `sh data/decoders/install.sh` in Terminal |

The installer:

1. Copies the programs to `%APPDATA%\urh\decoders` (Windows) or
   `~/.config/urh/decoders` (Linux/macOS).
2. Backs up your `decodings.txt` (`decodings.txt.bak.<date>`).
3. Adds the decodings with the correct absolute path, without duplicating the
   ones you already have.

It can be run several times. On Windows it also rewrites existing entries of
these three external decoders that were saved without the `d`/`e` arguments
(URH then called `program <bits>` instead of `program d <bits>`, which fails).

## Contents

**Built-in decodings** (`decodings.txt`, valid on any system): NRZ, NRZ-I,
Manchester I/II, Differential Manchester, NRZ-S, LSB-first variants, CC1101
data whitening, EnOcean WSP, PWM 1/3 (EV1527) normal and inverted, PWM 1/4,
Nexa/HomeEasy, remove redundancy x2/x3 and Morse code.

**External decoders**:

| Name in URH | Program | What it does |
|---|---|---|
| HomeMatic (complete: whitening + CRC) | `homematic_complete` | Finds preamble + sync, removes the data whitening, decrypts and checks/recomputes the CRC |
| HomeMatic (cipher only) | `homematic` | Only the HomeMatic decryption, on data without whitening |
| EnOcean Switch Telegram | `enocean_switchtelegram` | EnOcean switch telegrams |

All of them use the URH interface: `program d <bits>` decodes and
`program e <bits>` encodes.

## Manual installation

Copy the binary for your platform anywhere and, in URH, open
*Edit -> Decoding*, drag **External Program** into the chain and set the
decoder/encoder to:

    /path/to/homematic_complete d
    /path/to/homematic_complete e

On Windows, put the path in double quotes if it contains spaces.

## Source code and changes

The binaries are built from `data/decodings/*.c` in this repository (GPL-3.0)
with `zig cc` 0.17.1 (`-O2`, static on Linux). Testing the original code with
AddressSanitizer found memory errors, which are fixed in `data/decodings`
without changing the output for valid input:

- `homematic_complete.c`: the LFSR read `lfsr_state[-1]`. This is undefined
  behaviour, and clang -O2 produced different results than gcc.
- `homematic_complete.c`: it accepted 65536 bits, but its buffers hold 1024
  bytes (8192 bits). Longer inputs are now rejected, as too short ones already
  were.
- `homematic_complete.c`: the CRC loop counter was 8 bits wide, so messages
  longer than 255 bytes (~2100 bits) **made the program hang forever** and
  froze URH. The original binary has the same problem.
- `homematic.c`: inputs shorter than 16 bits wrote to `dec[-1]` and `enc[-1]`.
- `homematic.c`: the maximum input (2048 bits) had no room for the NUL
  terminator.

Verification: 1800 random inputs of normal size give the same output as the
official Linux binaries and as a gcc build of the fixed sources, and 2400 runs
with AddressSanitizer/UBSan, from 1 to 20000 bits, show no memory errors or
hangs. The Windows and macOS binaries are built from the same code. The
Windows ones have been run on Windows 10 through the installer self-test;
the macOS ones have not been run on macOS yet.

Note: the official test `tests/TestExternalDecodings.py` also fails with the
original binaries in `data/decodings`, so that test is out of date.
