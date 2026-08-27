"""Windows startup registration for the Settings page.

The per-user Run registry key is used because it does not require administrator
permissions. The packaged EXE registers itself directly. During development the
same setting can launch the current Python interpreter plus main.py.
"""

from __future__ import annotations

# sys tells us whether Tracky is a PyInstaller EXE; Path safely quotes the
# executable or development entry-point path used by the registry command.
import sys
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Tracky"


def startup_command() -> str:
    """Build the command Windows should execute after the user signs in."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"'
    main_file = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{Path(sys.executable)}" "{main_file}"'


def set_startup_enabled(enabled: bool) -> tuple[bool, str]:
    """Add or remove Tracky from HKCU Run and return a status message."""
    if sys.platform != "win32":
        return False, "Startup registration is available on Windows only."

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, startup_command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True, "Startup preference saved."
    except OSError as exc:
        return False, f"Windows could not update startup: {exc}"
