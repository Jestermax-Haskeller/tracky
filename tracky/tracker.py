"""Foreground-window screen-time tracker for Windows."""

from __future__ import annotations

# ctypes and wintypes call foreground-window and idle-time Win32 APIs.
# os identifies Tracky's own process, threading keeps polling off the GUI thread,
# and time supplies wall-clock timestamps plus the sample cadence.
import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes

# QObject and Signal are the bridge that safely reports tracker changes to Qt.
from PySide6.QtCore import QObject, Signal

from .browser import is_browser, read_browser_url
from .database import Database
from .utils import domain_from_url


class LASTINPUTINFO(ctypes.Structure):
    """Win32 structure filled by GetLastInputInfo."""

    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def _idle_seconds() -> float:
    """Return seconds since the last keyboard or mouse input on Windows."""
    if sys.platform != "win32":
        return 0.0

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0

    tick = ctypes.windll.kernel32.GetTickCount()
    return ((int(tick) - int(info.dwTime)) & 0xFFFFFFFF) / 1000.0


def _foreground_activity() -> dict | None:
    """Read the foreground window, owning process, title, and browser URL."""
    if sys.platform != "win32":
        return None

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value or pid.value == os.getpid():
        # Do not count Tracky itself while the user is checking their stats.
        return None

    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    title = buffer.value

    try:
        # psutil is used instead of more Win32 calls because it makes executable
        # name/path access concise and easy for a Python learner to inspect.
        import psutil

        process = psutil.Process(pid.value)
        process_name = process.name() or "unknown.exe"
        try:
            process_path = process.exe()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            process_path = None
    except Exception:
        return None

    # URL extraction is best effort. If it fails, the browser process still gets
    # tracked and the database later places it in the Browsing folder by default.
    url = read_browser_url(hwnd) if is_browser(process_name) else None
    domain = domain_from_url(url)
    entity_key = f"web:{domain}" if domain else f"app:{process_name.lower()}"

    return {
        "hwnd": int(hwnd),
        "pid": int(pid.value),
        "process_name": process_name,
        "process_path": process_path,
        "window_title": title,
        "url": url,
        "domain": domain,
        "entity_key": entity_key,
    }


def _activity_identity(activity: dict) -> tuple:
    """Return the fields that make one focused activity visually distinct."""
    return (
        activity["pid"],
        activity["entity_key"],
        activity.get("url") or activity.get("window_title") or "",
    )


class FocusTracker(QObject):
    """Poll foreground activity on a lightweight daemon thread.

    Qt's GUI must stay on the main thread. The tracking loop therefore runs in a
    normal Python thread and emits a Qt signal only when a confirmed activity
    change occurs. A one-minute confirmation window filters brief Alt-Tab or tab
    switches so the calendar does not become a stack of tiny noisy fragments.
    """

    activity_changed = Signal(dict)

    def __init__(self, database: Database, sample_seconds: float = 1.0) -> None:
        super().__init__()
        self.database = database
        self.sample_seconds = sample_seconds
        self.idle_cutoff_seconds = 120

        # A new foreground activity must remain selected for this long before it
        # becomes a real switch. Shorter interruptions are folded into the prior
        # session, which implements the requested "ignore quick switches" rule.
        self.switch_confirm_seconds = 60.0

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_identity: tuple | None = None
        self._current_session_id: int | None = None
        self._current_activity: dict | None = None

        # Pending state holds a possible switch while the 60-second confirmation
        # timer runs. Keeping it separate means raw database rows stay clean.
        self._pending_identity: tuple | None = None
        self._pending_activity: dict | None = None
        self._pending_since: float | None = None

    def start(self) -> None:
        """Start tracking once; repeated calls are intentionally harmless."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="screen time tracking",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the worker and wait briefly so SQLite writes can finish."""
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def _clear_pending(self) -> None:
        """Forget an unconfirmed foreground switch."""
        self._pending_identity = None
        self._pending_activity = None
        self._pending_since = None

    def _clear_current(self) -> None:
        """Forget the current session after idle time or an unreadable window."""
        self._current_identity = None
        self._current_session_id = None
        self._current_activity = None
        self._clear_pending()

    def _start_initial_activity(self, activity: dict, identity: tuple, now: float) -> None:
        """Start the first activity immediately instead of delaying first launch."""
        self._current_session_id = self.database.start_session(activity, now)
        self._current_identity = identity
        self._current_activity = activity
        self._clear_pending()
        self.activity_changed.emit(activity)

    def _begin_pending_switch(self, activity: dict, identity: tuple, now: float) -> None:
        """Remember the first instant a different activity becomes foreground."""
        self._pending_identity = identity
        self._pending_activity = activity
        self._pending_since = now

        # End the visible current session at the exact switch time for now. If the
        # user returns within 60 seconds, extend_session later bridges this brief
        # interruption and makes it disappear from the final timeline.
        if self._current_session_id:
            self.database.extend_session(self._current_session_id, now)

    def _confirm_pending_switch(self, now: float) -> None:
        """Commit a switch that stayed stable for at least one minute."""
        if not self._pending_activity or self._pending_since is None:
            return

        # Backdate the new session to the real switch instant. This preserves
        # accurate screen time while the UI adds a tiny visual gap between stable
        # sessions so their boundary remains easy to see.
        session_id = self.database.start_session(self._pending_activity, self._pending_since)
        self.database.extend_session(session_id, now)
        self._current_session_id = session_id
        self._current_identity = self._pending_identity
        self._current_activity = self._pending_activity
        confirmed = self._pending_activity
        self._clear_pending()
        self.activity_changed.emit(confirmed)

    def _run(self) -> None:
        """Main polling loop executed on the daemon thread."""
        while not self._stop.is_set():
            now = time.time()

            # Screen time should not grow while the machine is unattended.
            idle = _idle_seconds()
            if idle >= self.idle_cutoff_seconds:
                if self._current_session_id:
                    # Move the last session end back to the user's real last input
                    # so the idle detection delay itself is never counted.
                    self.database.extend_session(
                        self._current_session_id,
                        max(0.0, now - idle),
                    )
                self._clear_current()
                self._stop.wait(self.sample_seconds)
                continue

            activity = _foreground_activity()
            if not activity:
                self._clear_current()
                self._stop.wait(self.sample_seconds)
                continue

            identity = _activity_identity(activity)

            # There is nothing to debounce on the first readable foreground app.
            if self._current_identity is None or not self._current_session_id:
                self._start_initial_activity(activity, identity, now)
                self._stop.wait(self.sample_seconds)
                continue

            if identity == self._current_identity:
                # Returning to the original activity before one minute expires
                # makes the transient switch disappear completely.
                self.database.extend_session(self._current_session_id, now)
                self._clear_pending()
                self._stop.wait(self.sample_seconds)
                continue

            if identity != self._pending_identity:
                # A new candidate resets the one-minute stability clock. This is
                # intentional: rapidly bouncing through several windows should
                # not create several short calendar fragments.
                self._begin_pending_switch(activity, identity, now)
                self._stop.wait(self.sample_seconds)
                continue

            if (
                self._pending_since is not None
                and now - self._pending_since >= self.switch_confirm_seconds
            ):
                self._confirm_pending_switch(now)

            self._stop.wait(self.sample_seconds)
