"""Tracky's top-level frameless application window."""

from __future__ import annotations

# ctypes asks Windows 11 to disable its native rounded-corner treatment while
# Tracky is maximized. sys keeps that Windows-only call harmless elsewhere.
import ctypes
import sys

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .database import Database
from .icons import IconManager
from .pages.home import HomePage
from .pages.labeling import LabelingPage
from .pages.settings import SettingsPage
from .tracker import FocusTracker
from .widgets import (
    AnimatedPageHost,
    NavButton,
    NavIndicator,
    ResizeCorner,
    TitleBar,
    WindowSurface,
)


class MainWindow(QWidget):
    """The rounded Tracky window, navigation, pages, and maximize behaviour."""

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.icons = IconManager(database, self)
        self.tracker = FocusTracker(database)
        self._active_index = 0
        self._indicator_animation: QPropertyAnimation | None = None
        self._tracky_manual_maximized = False

        # A translucent frameless window lets our inner frame own the rounded
        # corners instead of using the standard Windows title bar. The
        # NoDropShadowWindowHint also asks Windows not to add a native shadow.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(880, 620)
        self.resize(1080, 720)
        self.setWindowTitle("tracky")

        self._build_ui()
        self._connect_tracking()
        self.tracker.start()

    def _build_ui(self) -> None:
        self.outer_layout = QVBoxLayout(self)
        # There is intentionally no transparent padding around the shell. The
        # previous padding only existed to make room for a drop shadow, which
        # Tracky no longer draws. Keeping the shell flush also makes maximize
        # transitions more predictable on Windows.
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)

        # WindowSurface paints the shell itself. This avoids the occasional
        # one-pixel purple artifact produced by stylesheet rounded borders on a
        # translucent frameless Windows window.
        self.window_frame = WindowSurface()
        self.outer_layout.addWidget(self.window_frame)

        frame_layout = QHBoxLayout(self.window_frame)
        frame_layout.setContentsMargins(1, 1, 1, 1)
        frame_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setProperty("maximized", False)
        self.sidebar.setFixedWidth(204)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(16, 18, 16, 18)
        sidebar_layout.setSpacing(6)

        brand = QLabel("tracky")
        brand.setObjectName("brand")
        sidebar_layout.addWidget(brand)

        # This is the exact product description requested for the sidebar.
        caption = QLabel("a free & open source screentime tracking app")
        caption.setObjectName("brandCaption")
        caption.setWordWrap(True)
        caption.setMaximumWidth(168)
        sidebar_layout.addWidget(caption)
        sidebar_layout.addSpacing(20)

        self.home_button = NavButton("home", "Home")
        self.label_button = NavButton("folder", "Labeling")
        self.settings_button = NavButton("gear", "Settings")
        self.nav_buttons = [self.home_button, self.label_button, self.settings_button]

        sidebar_layout.addWidget(self.home_button)
        sidebar_layout.addSpacing(20)
        sidebar_layout.addWidget(self.label_button)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(self.settings_button)

        # A custom-painted rounded pill replaces the old styled QFrame marker.
        # Moving one opaque child and repainting its parent prevents the thin
        # trail artifacts that could be left behind during fast tab changes.
        self.indicator = NavIndicator(self.sidebar)
        self.indicator.raise_()

        frame_layout.addWidget(self.sidebar)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        frame_layout.addWidget(main, 1)

        self.title_bar = TitleBar()
        self.title_bar.minimize_requested.connect(self.showMinimized)
        self.title_bar.maximize_requested.connect(self._toggle_maximize)
        self.title_bar.close_requested.connect(self.close)
        main_layout.addWidget(self.title_bar)

        self.page_host = AnimatedPageHost()
        host_layout = QVBoxLayout(self.page_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        host_layout.addWidget(self.stack)
        main_layout.addWidget(self.page_host, 1)

        self.home_page = HomePage(self.database, self.icons)
        self.labeling_page = LabelingPage(self.database, self.icons)
        self.settings_page = SettingsPage(self.database)
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.labeling_page)
        self.stack.addWidget(self.settings_page)

        # A QSizeGrip restores an obvious resize target while the native frame is
        # removed. It is hidden when maximized because resizing is then disabled.
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 3, 3)
        grip_row.addStretch()
        self.resize_grip = ResizeCorner(self.window_frame)
        grip_row.addWidget(self.resize_grip)
        main_layout.addLayout(grip_row)

        self.home_button.clicked.connect(lambda: self.set_page(0))
        self.label_button.clicked.connect(lambda: self.set_page(1))
        self.settings_button.clicked.connect(lambda: self.set_page(2))
        self.home_button.set_active(True)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._place_indicator_immediately(self.home_button)
        # Reapply the visual state after restore/minimize transitions. Qt owns
        # the actual maximize geometry; this helper only changes Tracky's shell.
        self._apply_window_state()

        # A short startup fade keeps the rounded window from popping onscreen.
        if not hasattr(self, "_startup_animation"):
            self.setWindowOpacity(0.0)
            self._startup_animation = QPropertyAnimation(self, b"windowOpacity", self)
            self._startup_animation.setDuration(220)
            self._startup_animation.setStartValue(0.0)
            self._startup_animation.setEndValue(1.0)
            self._startup_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._startup_animation.start()

    def set_page(self, index: int) -> None:
        if index == self._active_index and self.stack.currentIndex() == index:
            if index == 1:
                self.labeling_page.refresh()
            return

        self._active_index = index
        self.stack.setCurrentIndex(index)
        page = self.stack.currentWidget()
        self.page_host.fade_in(page)

        for i, button in enumerate(self.nav_buttons):
            button.set_active(i == index)

        if index == 0:
            self.home_page.refresh()
        elif index == 1:
            self.labeling_page.refresh()

        self._animate_indicator(self.nav_buttons[index])

    def _place_indicator_immediately(self, button: NavButton) -> None:
        """Place the rounded active-page pill without running an animation."""
        y = button.mapTo(self.sidebar, button.rect().topLeft()).y() + 7
        self.indicator.setFixedHeight(button.height() - 14)
        self.indicator.move(8, y)
        self.indicator.raise_()
        self.sidebar.update()

    def _animate_indicator(self, button: NavButton) -> None:
        """Slide the marker and repaint its old position on every animation tick."""
        y = button.mapTo(self.sidebar, button.rect().topLeft()).y() + 7
        self.indicator.setFixedHeight(button.height() - 14)

        # Stopping the previous animation matters when users click several tabs
        # rapidly. Two geometry animations fighting over the same widget were a
        # major cause of the visible purple trail in the earlier build.
        if self._indicator_animation is not None:
            self._indicator_animation.stop()
            self._indicator_animation.deleteLater()

        animation = QPropertyAnimation(self.indicator, b"pos", self)
        animation.setDuration(180)
        animation.setStartValue(self.indicator.pos())
        animation.setEndValue(QPoint(8, y))
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.valueChanged.connect(lambda _value: self.sidebar.repaint())

        def finish() -> None:
            self.sidebar.update()
            if self._indicator_animation is animation:
                self._indicator_animation = None
            animation.deleteLater()

        animation.finished.connect(finish)
        self._indicator_animation = animation
        animation.start()

    def _toggle_maximize(self) -> None:
        """Use Qt's native maximize path so Windows keeps the taskbar usable.

        Earlier revisions manually resized the frameless window and also forced
        a native HRGN. That combination could leave the window in a broken
        geometry state on some Windows 11 display and DPI setups. Qt already
        knows the monitor work area, so showMaximized is both simpler and more
        reliable.
        """
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event) -> None:
        """Refresh shell styling whenever Windows changes the window state."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._apply_window_state()

    def _apply_window_state(self) -> None:
        """Keep custom controls in sync with Qt's real maximize state."""
        maximized = self.isMaximized()
        self._tracky_manual_maximized = maximized
        self.resize_grip.setVisible(not maximized)
        self.window_frame.setProperty("maximized", maximized)
        self.sidebar.setProperty("maximized", maximized)
        self._refresh_dynamic_styles()
        self._set_windows_square_corners(maximized)
        self.title_bar.set_maximized_state(maximized)

    def _set_windows_square_corners(self, square: bool) -> None:
        """Tell Windows 11 not to round the native frame while maximized.

        Tracky no longer changes the Win32 window region. SetWindowRgn was the
        source of unstable maximize behavior on some systems because the region
        could become stale after DPI, monitor, or work-area changes. DWM's corner
        preference is enough here because WindowSurface itself also paints a
        square shell in maximized mode.
        """
        if sys.platform != "win32":
            return

        try:
            hwnd = ctypes.c_void_p(int(self.winId()))
            attribute = ctypes.c_uint(33)  # DWMWA_WINDOW_CORNER_PREFERENCE
            preference = ctypes.c_int(1 if square else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(preference),
                ctypes.sizeof(preference),
            )
        except Exception:
            # Older Windows builds may not expose this attribute. The painted
            # shell still changes shape correctly even when DWM ignores it.
            pass

    def _refresh_dynamic_styles(self) -> None:
        for widget in (self.window_frame, self.sidebar):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def _connect_tracking(self) -> None:
        self.tracker.activity_changed.connect(self._activity_changed)

    def _activity_changed(self, _activity: dict) -> None:
        if self.stack.currentIndex() == 0:
            self.home_page.refresh()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.tracker.stop()
        event.accept()
