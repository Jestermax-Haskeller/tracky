"""Browser URL detection using Windows UI Automation.

Browsers intentionally do not expose the current tab URL through a universal
public API.  Tracky therefore reads the visible address-bar control with
Microsoft UI Automation via pywinauto.  This keeps Tracky extension-free and
local, but browser accessibility changes can require future heuristic updates.
"""

from __future__ import annotations

# sys keeps the Windows-only accessibility code from running on other systems.
import sys

# URL validation is shared with the tracker rather than duplicated here.
from .utils import normalise_url

BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "brave.exe",
    "firefox.exe",
    "opera.exe",
    "opera_gx.exe",
    "vivaldi.exe",
}

# Common UIA names/IDs used by Chromium and Firefox address bars.  We still
# include generic fallbacks because these labels vary by browser version/locality.
ADDRESS_HINTS = (
    "address and search bar",
    "address bar",
    "search or enter address",
    "urlbar-input",
    "omnibox",
)


def is_browser(process_name: str) -> bool:
    return process_name.lower() in BROWSER_PROCESSES


def read_browser_url(hwnd: int) -> str | None:
    """Best-effort address bar read for the foreground browser window.

    The function is intentionally defensive: URL tracking should never crash
    the screen-time tracker just because a browser changed its accessibility
    tree or denied access.
    """
    if sys.platform != "win32":
        return None

    try:
        from pywinauto import Desktop

        window = Desktop(backend="uia").window(handle=hwnd)
        edits = window.descendants(control_type="Edit")

        # First choose controls whose accessible name or automation ID clearly
        # looks like an address bar. This avoids accidentally reading a webpage
        # text field such as a search box inside the page.
        preferred = []
        fallback = []
        for control in edits:
            try:
                info = control.element_info
                name = (info.name or "").lower()
                auto_id = (info.automation_id or "").lower()
                combined = f"{name} {auto_id}"
                if any(hint in combined for hint in ADDRESS_HINTS):
                    preferred.append(control)
                else:
                    # Localised browsers may not use an English accessible name.
                    # As a fallback, only consider Edit controls near the browser
                    # chrome at the top of the window; webpage text boxes lower
                    # down are deliberately ignored to reduce false URL captures.
                    try:
                        window_top = window.rectangle().top
                        if control.rectangle().top - window_top < 180:
                            fallback.append(control)
                    except Exception:
                        pass
            except Exception:
                continue

        for control in preferred + fallback[:4]:
            value = _control_value(control)
            url = normalise_url(value)
            if url:
                return url
    except Exception:
        # Browser URL capture is an enhancement over app tracking.  Swallowing
        # UIA errors keeps the foreground process tracker reliable.
        return None

    return None


def _control_value(control) -> str | None:
    """Try multiple UIA value access patterns used by different wrappers."""
    for getter in (
        lambda: control.get_value(),
        lambda: control.iface_value.CurrentValue,
        lambda: control.window_text(),
    ):
        try:
            value = getter()
            if isinstance(value, str) and value.strip():
                return value.strip()
        except Exception:
            pass
    return None
