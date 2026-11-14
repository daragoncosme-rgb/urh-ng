"""
Open the protocol of the Analysis tab in URH Signal Studio.

URH Signal Studio is a separate Windows program that loads the protocol XML of
URH (messages, decodings, labels, modulators) and decodes common remote
control protocols. URH writes the current protocol to a temporary
.proto.xml file and starts Signal Studio with it.
"""
import os
import re
import tempfile

from urh import settings

SETTINGS_KEY = "SignalStudio/executable"
EXE_NAME = "UrhSignalStudio.exe"

# Folders that never contain the program (build intermediates, VS caches)
_SKIP_DIRS = {"obj", ".vs", ".git", "node_modules", "ref", "refint", "__pycache__"}


def _candidate_roots():
    home = os.path.expanduser("~")
    roots = []
    for name in (
        "Desktop",
        "Escritorio",
        "Documents",
        "Documentos",
        "Downloads",
        "Descargas",
    ):
        roots.append(os.path.join(home, name))
        roots.append(os.path.join(home, "OneDrive", name))
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        if os.environ.get(env):
            roots.append(os.environ[env])
    return [r for r in dict.fromkeys(roots) if os.path.isdir(r)]


def search_executable(roots=None, max_depth=6):
    """
    Look for UrhSignalStudio.exe in folders whose name contains "SignalStudio".
    Release builds are preferred over Debug builds, then the newest one.
    """
    found = []
    for root in roots if roots is not None else _candidate_roots():
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for entry in entries:
            top = os.path.join(root, entry)
            if "signalstudio" not in entry.lower().replace(" ", ""):
                continue
            if os.path.isfile(top) and entry.lower() == EXE_NAME.lower():
                found.append(top)
                continue
            if not os.path.isdir(top):
                continue
            base_depth = top.rstrip(os.sep).count(os.sep)
            for dirpath, dirnames, filenames in os.walk(top):
                depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
                dirnames[:] = [
                    d
                    for d in dirnames
                    if d.lower() not in _SKIP_DIRS and depth < max_depth
                ]
                for f in filenames:
                    if f.lower() == EXE_NAME.lower():
                        found.append(os.path.join(dirpath, f))

    def rank(path):
        p = path.lower()
        release = 1 if (os.sep + "release" + os.sep) in p or "publish" in p else 0
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0
        return release, mtime

    return max(found, key=rank) if found else None


def get_executable(search=True):
    path = settings.read(SETTINGS_KEY, "", str)
    if path and os.path.isfile(path):
        return path
    if search:
        path = search_executable()
        if path:
            settings.write(SETTINGS_KEY, path)
            return path
    return None


def set_executable(path: str):
    settings.write(SETTINGS_KEY, path or "")


def export_protocol(protocol, decoders, participants, name="protocol", folder=None):
    """Write the protocol to <temp>/urh-signal-studio/<name>.proto.xml."""
    folder = folder or os.path.join(tempfile.gettempdir(), "urh-signal-studio")
    os.makedirs(folder, exist_ok=True)
    safe = re.sub(r"[^\w\- .]", "_", name or "protocol").strip(" .") or "protocol"
    filename = os.path.join(folder, safe + ".proto.xml")
    protocol.to_xml_file(
        filename=filename,
        decoders=decoders,
        participants=participants,
        write_bits=True,
    )
    return filename
