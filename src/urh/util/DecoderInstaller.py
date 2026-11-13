"""
Locate and build the command line of the bundled decoder installer.

The Windows installer of URH-NG sets the decoders up only for the user who
runs it. Other users (and the portable version) can install them from
Help -> Install decoders, which runs the same script for the current user.
"""
import os
import sys


def _source_root() -> str:
    # src/urh/util/DecoderInstaller.py -> repository root
    return os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def get_install_command(
    frozen: bool = None, platform: str = None, base_dir: str = None
):
    """
    Return (program, arguments, decoders_folder) to install the decoders for
    the current user, or (None, None, decoders_folder) if they are not found.

    frozen/platform/base_dir default to the running program and exist for tests.
    """
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    platform = sys.platform if platform is None else platform
    windows = platform.startswith("win")

    if frozen:
        # Packaged program: <program folder>/decoders contains everything
        base = base_dir or os.path.dirname(sys.executable)
        decoders = os.path.join(base, "decoders")
        win_script = os.path.join(decoders, "install-decoders.ps1")
    else:
        base = base_dir or _source_root()
        decoders = os.path.join(base, "data", "decoders")
        win_script = os.path.join(base, "data", "windows", "install-decoders.ps1")
    unix_script = os.path.join(decoders, "install.sh")

    if windows:
        if not os.path.isfile(win_script) or not os.path.isdir(decoders):
            return None, None, decoders
        args = [
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            win_script,
            "-Silent",
            "-SourceDir",
            decoders,
        ]
        return "powershell.exe", args, decoders

    if not os.path.isfile(unix_script):
        return None, None, decoders
    return "sh", [unix_script], decoders
