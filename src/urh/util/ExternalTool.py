"""
Settings for the "Run external tool" feature of the Analyze Protocol menu.

Remembers the path of the external program the user chose (there is no way
to auto-detect it, unlike URH Signal Studio) and the extra command-line
parameters typed in the dialog, so both survive across URH restarts.
"""
from urh import settings

PATH_KEY = "ExternalTool/executable"
PARAMS_KEY = "ExternalTool/extra_parameters"
FINAL_PARAMS_KEY = "ExternalTool/final_parameters"

# Shown the first time, before the user has set their own. Not force-written,
# so clearing the field and running still runs with no final parameters.
DEFAULT_FINAL_PARAMETERS = "-b -t91"

# Distinguishes "never saved" (-> use the default above) from "saved as empty"
# (-> the user cleared it on purpose, keep it empty), since settings.read()
# can't tell those apart by the stored value alone.
_UNSET = "\x00__external_tool_final_parameters_unset__\x00"


def get_executable() -> str:
    """Return the saved program path, or "" if none has been chosen yet."""
    return settings.read(PATH_KEY, "", str)


def set_executable(path: str):
    settings.write(PATH_KEY, path or "")


def get_extra_parameters() -> str:
    """Extra parameters placed before the encrypted:serial:button arguments."""
    return settings.read(PARAMS_KEY, "", str)


def set_extra_parameters(params: str):
    settings.write(PARAMS_KEY, params or "")


def get_final_parameters() -> str:
    """
    Final parameters placed after the encrypted:serial:button arguments
    (e.g. flags the program needs at the end of its command line).
    """
    val = settings.read(FINAL_PARAMS_KEY, _UNSET, str)
    return DEFAULT_FINAL_PARAMETERS if val == _UNSET else val


def set_final_parameters(params: str):
    settings.write(FINAL_PARAMS_KEY, params if params is not None else "")
