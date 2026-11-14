# Changelog

All notable changes to URH-NG are documented here.

## [Unreleased]

### Added
- **"Run external tool..." in the *Analyze Protocol* menu.** Lets you run any
  external program or `.bat`/`.cmd` script, passing the messages you check as
  `encrypted:serial:button` arguments (decoded the same way as the KeeLoq
  code word decoder, so only valid code words are listed). The first time,
  it asks where the program is and remembers the path; a "Change..." button
  lets you pick a different one later. "Extra parameters" are added before
  the checked messages' arguments and "Final parameters" (default `-b -t91`)
  after them, both editable and remembered too.
- **KeeLoq code word decoder (PWM)** in the *Analyze Protocol* menu. It decodes
  the messages of the protocol table as KeeLoq code words (HCS200/300/301):
  encrypted portion, serial number, button code (S3/S0/S1/S2), battery and
  repeat flags, plus the measured TE in microseconds, and can send the selected
  rows to the Crypto Toolkit (Encrypted #1/#2 and serial). It works when one
  symbol is not exactly one TE and when the last bit is cut by the pause. Based
  on the PulseView decoder by Andrea Orazi
  (https://github.com/rzondr/KeeLoq_decoder, GPL v2+).
- **Spectrum Analyzer view selector and radio presets.** A dropdown now lets
  you switch the Spectrum Analyzer between "Classic URH" and an "Averaged
  (dB)" view with configurable FFT size, window and averaging, plus waterfall
  sensitivity/contrast controls, so weak signals (e.g. garage/door remotes)
  are easier to see. A preset selector next to the device settings fills in
  frequency, sample rate and bandwidth for common remote-control bands, so you
  no longer have to look up the frequency yourself.
- **Copy a message's "encrypted" field into the Crypto Toolkit.** With the
  Crypto Toolkit (KeeLoq/TEA/AES) open, clicking a message row in the
  Analysis table now copies that message's `encrypted` label into
  "Encrypted #2", so a second capture for KeeLoq key bruteforcing is set just
  by selecting a row.
- **Category filter and better scoring in Auto-identify protocol (PHZ DB).**
  Matches are now classified (remote control, car key, security, sensor,
  meter, TPMS) and a filter dropdown defaults to "Remote controls (gates,
  garages, car keys)", so weather-station and other sensor protocols no
  longer crowd out garage/door remotes. Scoring now also compares measured
  pulse/gap timing against each candidate protocol, and the free bonus for
  merely having a checksum field (which favored sensors) was removed.
- **Autodetect noise and modulation enabled by default** in Interpretation's
  Autodetect parameters dropdown. Noise-level and modulation detection were
  also improved for weak signals: magnitudes are smoothed before segmenting a
  weak signal, pulse trains (many short segments merging into few messages)
  are recognized as OOK instead of being misclassified as FSK per-segment.
- **Remember the last used SDR.** Every device settings panel (Record, Send,
  Spectrum, Sniff and Simulator) opens with the last selected device, also
  after restarting URH-NG; previously the project default (USRP) was shown
  when no project was loaded. The device identifier and antenna last used with
  each device type are restored too. Stored in `urh.ini` under
  `[DeviceSettingsWidget]`.
- **Automatic device detection.** The "Automatically detect" button next to
  *Device Identifier* is pressed when a window opens and whenever the device
  is changed, so connected SDRs are listed without clicking it.
- **Local Windows build** (`data/windows/build.bat` / `build_windows.ps1`):
  installs the tools with winget (optionally on another drive with
  `-DepsDir`), builds the extensions, packages with PyInstaller, runs a
  start-up test and creates the portable `.zip` and the installer.
- **Bundled decoders** (`data/decoders`): HomeMatic and EnOcean external
  decoders for windows-x64, linux-x64, linux-arm64, macos-x64 and macos-arm64,
  and 19 ready-to-use decodings. The Windows installer sets them up in
  `%APPDATA%\urh`; on Linux/macOS run `sh data/decoders/install.sh`.

- **Help -> Install decoders for this user.** The installer sets the bundled
  decoders up only for the Windows user who installs URH-NG; other users of
  the same PC and users of the portable version can install them from this
  menu entry. The decodings are reloaded right away.

### Changed
- **The Windows installer no longer asks for administrator permission (UAC).**
  It installs for the current user in `%LOCALAPPDATA%\Programs\URH-NG` by
  default, with Start menu and desktop shortcuts for that user. An
  administrator can still choose to install for all users in `Program Files`
  (installer dialog, or `/ALLUSERS` on the command line).
- The Windows installer uses its own identity (name "URH-NG", new AppId,
  `Program Files\URH-NG`, `URH-NG-<version>-<arch>.exe`). It previously reused
  the AppId of the original Universal Radio Hacker, so installing or
  uninstalling URH-NG replaced or removed an existing URH installation.

### Fixed
- **Windows build and decoder installation from any path.** The build failed
  when the repository was in a folder with spaces (the PyInstaller command
  was not quoted) and `build.bat` broke with spaces or apostrophes in the
  options; temporary files now stay in the work folder even when the user
  name has spaces or accents. The decoder installers handle user folders
  with spaces (Linux/macOS) and with `, ; '` or non-ASCII characters
  (Windows, using the short 8.3 path).
- **Spectrum Analyzer froze while receiving** and did not react to Stop or to
  clicks on the spectrum/waterfall (Windows showed it as "not responding").
  It refreshed every 1 ms although one refresh (FFT, waterfall, time domain,
  constellation, modulation detection) takes much longer, so the window
  never had time to process user input. It now refreshes every 40 ms, or at
  least twice the duration of the last refresh on slow PCs.
- **Spectrum Analyzer memory kept growing** (2 GB in a long session): every
  refresh added a new waterfall image and none was removed. The waterfall now
  keeps the last 20480 rows. The constellation is drawn as a single item and
  the FFT peak search for modulation detection uses NumPy (35x faster).
- **Crash when stopping reception with RTL-SDR and other synchronous devices.**
  When the GUI closed the data pipe, the device process failed with
  `BrokenPipeError [WinError 109]`, skipped closing the device (which could
  stay busy until it was unplugged) and, in the Windows build, showed a second
  error `'NoneType' object has no attribute 'write'`. The receive loop now
  stops cleanly, device shutdown never fails because of a closed pipe, and
  device subprocesses of frozen `--windowed` builds get dummy stdout/stderr.
- **`AssertionError` in Analyze** after *Auto-identify protocol (PHZ DB)*: its
  "Sync/Gap" label is cut off in shorter messages, so the sync words had
  different lengths. The analysis now keeps the most common sync length.
- **Flipper Zero `.sub` export lost samples** after any run of a single sample
  (e.g. high x2, low x1, high x3, low x2 was exported as `[2, -3]`).
- `vag_decrypt()` raised `NameError` for AUT64 (VAG types 1/3) without an
  explicit S-box/P-box; it now uses the boxes of VAG key set #1.
- The RfCat plugin raised `IndexError` while logging a failed parameter.
- HomeMatic external decoders (`data/decodings`): a hang with messages longer
  than 255 bytes, an out-of-bounds read in the LFSR, a buffer overflow with
  inputs over 8192 bits, writes to `dec[-1]`/`enc[-1]` with inputs shorter than
  16 bits, and a missing NUL terminator at the maximum input size.
- **Analyze Protocol froze permanently around 70%** on signals with many
  messages: an integer overflow in a `uint32` sample-index array (AWRE
  preamble detection) and an O(n²) range-overlap check made the analysis
  effectively never finish. Both are fixed, and a warning dialog now offers
  to cap the analysis at a configurable number of messages (1500 by default)
  on very large captures.
- **Only the Spectrum Analyzer showed a signal; Record, Sniff and other
  spectrum views showed only noise with RTL-SDR.** The device silently
  rejected its first tune command (error -9) and never retried, and changing
  direct-sampling mode re-initialized the tuner without restoring the
  frequency. RTL-SDR now verifies the tuned frequency and retunes on
  mismatch or after a direct-sampling-mode change. Also fixed: the RTL-SDR
  gain was effectively in tenths of dB while shown and defaulted as whole dB
  (the UI now labels and defaults it correctly), an int8/uint8 sample
  conversion wraparound, and a circular-buffer wraparound in the protocol
  sniffer that could read stale data.
- **Spanish (and other comma-decimal) locales could not enter frequencies and
  other parameters** in the numeric spin boxes; they now parse `,` as the
  decimal separator.
- **Switching device while a receive was running** could crash the Record/
  Sniff/Spectrum dialogs; the device selector is now disabled while
  receiving.
- A `NaN`-to-int cast in the waterfall color mapping could raise under some
  signals; it's now clamped with `np.nan_to_num`.

## [0.0.2] - 2026-07-10

### Build system
- Modernized packaging with a `pyproject.toml` (PEP 517) build backend, fixing
  `pip install -e .` which previously failed on the old `from src.urh...`
  imports. `setup.py` is now trimmed to just the Cython/C++ extension build and
  loads its helpers by file path so it works under build isolation.
- Kept `numpy<3.0` (URH-NG runs fine on NumPy 2.x) and kept `cython` /
  `setuptools` as runtime dependencies, since URH compiles SDR device backends
  on the fly at runtime.
- Added a `uv.lock` for reproducible development environments and modernized
  `.gitignore`.

### Fixed
- Fixed wrong int8 magnitude/demodulation on ARM/AArch64 (e.g. Raspberry Pi):
  the `iq` fused type now uses `signed char` instead of a bare `char`, whose
  signedness is platform-dependent (upstream jopohl/urh#1160). Added a
  regression test.

### Chores
- Bumped version to `0.0.2`.
- Applied `black` formatting so CI stays green.

### Credits
The KeeLoq code word decoder (PWM) is based on the PulseView decoder by
**Andrea Orazi** ([@rzondr](https://github.com/rzondr),
[rzondr/KeeLoq_decoder](https://github.com/rzondr/KeeLoq_decoder), GPL v2+).

Thanks to the contributors whose pull requests this release builds on:

- **[@wyattearp](https://github.com/wyattearp)** — `pyproject.toml` build
  modernization and updated `.gitignore` ([#1](https://github.com/PentHertz/urh-ng/pull/1)).
- **[@pd0wm](https://github.com/pd0wm)** — `uv` integration and the isolation-safe
  build import approach ([#2](https://github.com/PentHertz/urh-ng/pull/2)).
- **[@munzzyy](https://github.com/munzzyy)** — the ARM `signed char` int8 fix and
  regression test ([#3](https://github.com/PentHertz/urh-ng/pull/3)).
