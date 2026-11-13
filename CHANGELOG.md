# Changelog

All notable changes to URH-NG are documented here.

## [Unreleased]

### Added
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
Thanks to the contributors whose pull requests this release builds on:

- **[@wyattearp](https://github.com/wyattearp)** — `pyproject.toml` build
  modernization and updated `.gitignore` ([#1](https://github.com/PentHertz/urh-ng/pull/1)).
- **[@pd0wm](https://github.com/pd0wm)** — `uv` integration and the isolation-safe
  build import approach ([#2](https://github.com/PentHertz/urh-ng/pull/2)).
- **[@munzzyy](https://github.com/munzzyy)** — the ARM `signed char` int8 fix and
  regression test ([#3](https://github.com/PentHertz/urh-ng/pull/3)).
