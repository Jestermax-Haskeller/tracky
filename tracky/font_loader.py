"""Load Nunito for the application without bundling font binaries.

Tracky prefers Nunito at several weights. Windows does not ship Nunito by
default, so this helper first checks installed fonts, then a local Tracky cache,
and finally makes a small one time download from the Google Fonts repository.
If that download is unavailable, Qt falls back to Segoe UI through the style
sheet and the rest of the application keeps working normally.
"""

from __future__ import annotations

# urllib performs the optional one-time font download without another package.
from urllib.request import Request, urlopen

# QFontDatabase registers a font only for this running Qt application.
from PySide6.QtGui import QFontDatabase

from .utils import app_data_dir


NUNITO_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/"
    "ofl/nunito/Nunito%5Bwght%5D.ttf"
)


def ensure_nunito_font() -> bool:
    """Return True when Nunito is available to Qt for this process."""
    if any(family.lower() == "nunito" for family in QFontDatabase.families()):
        return True

    font_dir = app_data_dir() / "fonts"
    font_dir.mkdir(exist_ok=True)
    cached_font = font_dir / "Nunito-Variable.ttf"

    if not cached_font.exists():
        try:
            request = Request(NUNITO_URL, headers={"User-Agent": "Tracky/0.2"})
            with urlopen(request, timeout=3.0) as response:
                data = response.read(2_000_000)
            if data:
                cached_font.write_bytes(data)
        except Exception:
            return False

    return QFontDatabase.addApplicationFont(str(cached_font)) >= 0
