"""What a program Construct starts is given of this process's environment.

Construct runs other programs: a browser for its captures, ffmpeg for films and audio, Blender for renders, FreeCAD
for exact solids, Java for NetLogo. Each is given what a program needs to start, find its libraries and keep its
files on macOS, Windows and Linux, plus the few names that program reads for itself; never the rest of the
environment, where API keys and tokens live.
"""

import os

BASE = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "TEMP", "TMP", "LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE",
        "LD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME",
        "XDG_RUNTIME_DIR", "DISPLAY", "WAYLAND_DISPLAY", "FONTCONFIG_FILE", "FONTCONFIG_PATH",
        "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
        "PROGRAMFILES", "PROGRAMFILES(X86)", "USERPROFILE", "USERNAME", "HOMEDRIVE", "HOMEPATH",
        "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE")

# the names each program reads for itself (none of them a secret)
FREECAD = ("FREECAD_USER_HOME", "FREECAD_USER_DATA", "FREECAD_USER_TEMP")
JAVA = ("JAVA_HOME",)


def minimal(names=(), **extra):
    """The environment for a program Construct starts: BASE and `names` as they are here, then `extra`."""
    env = {k: os.environ.get(k) for k in BASE + tuple(names) if os.environ.get(k) is not None}
    env.update(extra)
    return env
