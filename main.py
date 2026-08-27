"""Entry point for Tracky.

Run this file directly during development. PyInstaller also points at this same
entry point, so the packaged EXE and the source version exercise identical code.
"""

from __future__ import annotations

# ctypes calls the small Windows shell API used for taskbar identity. sys
# provides platform checks and Qt arguments. threading gives the UI thread a
# descriptive OS-level name on Python 3.14.
import ctypes
import sys
import threading

# QtGui supplies the window icon. QtWidgets supplies the application loop and
# a safe error dialog for failures in a no-console packaged build.
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from tracky.database import Database
from tracky.font_loader import ensure_nunito_font
from tracky.main_window import MainWindow
from tracky.styles import APP_STYLESHEET
from tracky.utils import resource_path


def main() -> int:
    # Python 3.14 forwards a running thread name to Windows. Naming the main
    # thread makes diagnostics describe its real role instead of a generic name.
    threading.current_thread().name = "tracky interface"

    if sys.platform != "win32":
        # Tracky's tracking backend is intentionally Windows-specific. Keeping
        # this clear error avoids confusing partial behaviour on other systems.
        print("Tracky currently runs on Windows only.")
        return 1

    # This AppUserModelID gives the packaged program a stable taskbar identity.
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Tracky.Tracky.0.3.5")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("tracky")
    app.setApplicationDisplayName("tracky")
    app.setOrganizationName("tracky")

    # QFontDatabase can only be used after QApplication exists. This one-time
    # helper loads Nunito from the Windows font collection or Tracky cache and
    # falls back cleanly when the first launch is offline.
    ensure_nunito_font()
    app.setStyleSheet(APP_STYLESHEET)

    icon_path = resource_path("assets/tracky.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    try:
        database = Database()
        window = MainWindow(database)
        if icon_path.exists():
            window.setWindowIcon(QIcon(str(icon_path)))
        window.show()
        return app.exec()
    except Exception as exc:
        # A GUI error dialog is more useful than a disappearing console because
        # the final executable is built with --windowed / console=False.
        QMessageBox.critical(None, "Tracky could not start", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
