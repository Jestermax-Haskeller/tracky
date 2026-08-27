"""Settings page for persistent Tracky preferences."""

from __future__ import annotations

# Qt is needed for rich-text link handling. The remaining widgets build the
# simple startup preference card without extra native Windows controls.
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..database import Database
from ..startup import set_startup_enabled
from ..styles import COLORS
from ..widgets import ToggleSwitch


GITHUB_URL = "https://github.com/Jestermax-Haskeller/tracky"


class SettingsPage(QWidget):
    """Expose small app-wide preferences that should survive restarts."""

    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.database = database
        self._build_ui()
        self._load_startup_setting()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 2, 28, 28)
        layout.setSpacing(14)

        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(7)

        # Keep this preference intentionally minimal. The two visible lines below
        # are intentionally short so the startup setting stays easy to scan.
        startup_row = QHBoxLayout()
        startup_text = QLabel("Launch at startup")
        startup_text.setStyleSheet("font-size: 14px; font-weight: 700;")
        startup_row.addWidget(startup_text)
        startup_row.addStretch()
        self.startup_toggle = ToggleSwitch()
        self.startup_toggle.toggled.connect(self._startup_toggled)
        startup_row.addWidget(self.startup_toggle)
        card_layout.addLayout(startup_row)

        description = QLabel("Runs in the background")
        description.setObjectName("muted")
        card_layout.addWidget(description)

        layout.addWidget(card)
        layout.addStretch()

        # The repository callout belongs at the bottom of Settings. Qt rich text
        # keeps the visible wording intact while making only the URL clickable.
        star = QLabel(
            'like what I made? consider giving a star ⭐: '
            f'<a style="color:{COLORS["purple_2"]};" href="{GITHUB_URL}">{GITHUB_URL}</a>'
        )
        star.setOpenExternalLinks(True)
        star.setTextFormat(Qt.TextFormat.RichText)
        star.setStyleSheet("font-weight: 600;")
        layout.addWidget(star)

    def _load_startup_setting(self) -> None:
        """Default startup to enabled on first launch, then honor the saved value."""
        saved = self.database.get_setting("start_at_startup")
        enabled = True if saved is None else saved == "1"
        if saved is None:
            self.database.set_setting("start_at_startup", "1")

        self.startup_toggle.blockSignals(True)
        self.startup_toggle.setChecked(enabled)
        self.startup_toggle.offset = 1.0 if enabled else 0.0
        self.startup_toggle.blockSignals(False)

        # The startup helper returns diagnostics, but the interface intentionally
        # stays at exactly two lines of setting copy as requested.
        set_startup_enabled(enabled)

    def _startup_toggled(self, enabled: bool) -> None:
        """Save the switch and apply it to the current Windows user's Run key."""
        self.database.set_setting("start_at_startup", "1" if enabled else "0")
        set_startup_enabled(enabled)
