"""Reusable custom widgets used across Tracky's interface.

This module holds UI pieces that benefit from custom drawing or behaviour:
the frameless title bar, soft sidebar icons, animated navigation marker, painted
week calendar, cursor-following session card, toggle, and statistics cards.
"""

from __future__ import annotations

# math is used only for the tiny hand-drawn gear icon. datetime places calendar
# sessions in day columns and lets the current-time marker use local time.
import math
from datetime import datetime, timedelta

from PySide6.QtCore import (
    QEvent,
    QEasingCurve,
    QPoint,
    QPointF,
    Property,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRegion,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from .styles import COLORS
from .utils import format_duration


def _soft_nav_icon(kind: str, color: str) -> QIcon:
    """Draw simple outline navigation icons with consistent rounded strokes.

    The icons are painted rather than taken from a symbol font so their weight
    and alignment stay identical across Windows versions. Home and Labeling use
    one continuous contour, while Settings uses a classic eight-tooth gear
    outline plus its center hole to match the familiar gear emoji silhouette.
    """
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.75)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "home":
        # One unbroken outline travels around the roof, walls, and doorway.
        path = QPainterPath()
        path.moveTo(5.2, 19.0)
        path.lineTo(5.2, 10.9)
        path.lineTo(12.0, 5.1)
        path.lineTo(18.8, 10.9)
        path.lineTo(18.8, 19.0)
        path.lineTo(14.3, 19.0)
        path.lineTo(14.3, 14.5)
        path.lineTo(9.7, 14.5)
        path.lineTo(9.7, 19.0)
        path.lineTo(5.2, 19.0)
        painter.drawPath(path)

    elif kind == "folder":
        # This is a single soft folder outline with a small integrated tab. The
        # larger corner curves make it read cleanly at sidebar size without
        # adding a second inner line or any sharp decorative details.
        path = QPainterPath()
        path.moveTo(4.0, 8.4)
        path.quadTo(4.0, 6.4, 6.0, 6.4)
        path.lineTo(8.8, 6.4)
        path.quadTo(9.7, 6.4, 10.4, 7.1)
        path.lineTo(11.6, 8.3)
        path.lineTo(18.0, 8.3)
        path.quadTo(20.1, 8.3, 20.1, 10.4)
        path.lineTo(20.1, 17.1)
        path.quadTo(20.1, 19.2, 18.0, 19.2)
        path.lineTo(6.0, 19.2)
        path.quadTo(3.9, 19.2, 3.9, 17.1)
        path.lineTo(3.9, 8.8)
        path.quadTo(3.9, 8.5, 4.0, 8.4)
        painter.drawPath(path)

    elif kind == "gear":
        # Build one closed eight-tooth outline. Alternating outer and inner radii
        # gives the same immediately recognizable silhouette as the gear emoji.
        center_x = 12.0
        center_y = 12.0
        outer_radius = 8.6
        inner_radius = 6.6
        gear = QPainterPath()
        point_count = 32
        for index in range(point_count):
            angle = -math.pi / 2 + index * (2 * math.pi / point_count)
            phase = index % 4
            radius = outer_radius if phase in (0, 1) else inner_radius
            point = QPointF(
                center_x + math.cos(angle) * radius,
                center_y + math.sin(angle) * radius,
            )
            if index == 0:
                gear.moveTo(point)
            else:
                gear.lineTo(point)
        gear.closeSubpath()
        painter.drawPath(gear)
        painter.drawEllipse(QPointF(center_x, center_y), 2.4, 2.4)

    painter.end()
    return QIcon(pixmap)


class WindowSurface(QFrame):
    """Paint the rounded application shell without stylesheet corner artifacts.

    A custom painter avoids the one-pixel colored artifacts that can appear at a
    translucent QWidget's rounded stylesheet border on some Windows GPU/DPI
    combinations. Maximized mode deliberately uses a zero radius.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("windowFrame")
        self.setProperty("maximized", False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        maximized = bool(self.property("maximized"))
        painter.setBrush(QColor(COLORS["bg"]))
        painter.setPen(QPen(QColor(COLORS["border"]), 1.0))
        if maximized:
            # Fill the complete widget first. Leaving even a half-pixel transparent
            # rim on a translucent top-level window can make Windows show rounded
            # desktop pixels at the outer corners.
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.fillRect(self.rect(), QColor(COLORS["bg"]))
            square_rect = QRectF(self.rect()).adjusted(0.0, 0.0, -1.0, -1.0)
            painter.drawRect(square_rect)
        else:
            rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            painter.drawRoundedRect(rect, 18.0, 18.0)
        painter.end()


class RoundedClipFrame(QFrame):
    """Keep the graph content rounded without cutting away its outer border.

    Masking the whole card fixed square child pixels, but a hard QRegion mask
    could also shave antialiased pixels from the card's own curved border. The
    better approach is to leave the parent unmasked so Qt can paint a complete
    border, then apply the rounded mask only to direct child widgets such as the
    calendar scroll area.
    """

    def __init__(self, radius: float = 14.0, parent=None) -> None:
        super().__init__(parent)
        self.radius = float(radius)
        self.setObjectName("card")

    def _clip_children(self) -> None:
        """Clip direct child widgets one pixel inside the visible card border."""
        child_radius = max(0.0, self.radius - 1.0)
        for child in self.children():
            if not isinstance(child, QWidget):
                continue
            child_rect = QRectF(child.rect())
            if child_rect.width() <= 0 or child_rect.height() <= 0:
                continue
            path = QPainterPath()
            path.addRoundedRect(child_rect, child_radius, child_radius)
            child.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.clearMask()
        self._clip_children()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._clip_children()


class TitleBar(QFrame):
    """Minimal window controls and drag surface for the frameless shell."""

    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(38)
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 10, 5)
        layout.setSpacing(4)
        layout.addStretch()

        self.min_button = self._button("−", "windowButton")
        self.max_button = self._button("□", "windowButton")
        self.close_button = self._button("×", "closeButton")
        self.min_button.setToolTip("Minimize")
        self.max_button.setToolTip("Maximize")
        self.close_button.setToolTip("Close")
        self.min_button.clicked.connect(self.minimize_requested)
        self.max_button.clicked.connect(self.maximize_requested)
        self.close_button.clicked.connect(self.close_requested)
        layout.addWidget(self.min_button)
        layout.addWidget(self.max_button)
        layout.addWidget(self.close_button)

    def _button(self, text: str, object_name: str) -> QPushButton:
        """Create one consistent title-bar button."""
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def set_maximized_state(self, maximized: bool) -> None:
        """Swap the glyph so the user can see whether the next click restores."""
        self.max_button.setText("❐" if maximized else "□")
        self.max_button.setToolTip("Restore" if maximized else "Maximize")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            if not getattr(window, "_tracky_manual_maximized", False):
                self._drag_offset = (
                    event.globalPosition().toPoint() - window.frameGeometry().topLeft()
                )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_requested.emit()
        super().mouseDoubleClickEvent(event)


class NavButton(QPushButton):
    """Sidebar navigation button with a custom matching vector-style icon."""

    def __init__(self, icon_kind: str, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.icon_kind = icon_kind
        self.setObjectName("navButton")
        self.setProperty("active", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self.setIconSize(QSize(20, 20))
        self.setIcon(_soft_nav_icon(icon_kind, COLORS["muted"]))

    def set_active(self, active: bool) -> None:
        """Refresh both custom property styling and the hand-drawn icon color."""
        self.setProperty("active", active)
        icon_color = COLORS["purple_2"] if active else COLORS["muted"]
        self.setIcon(_soft_nav_icon(self.icon_kind, icon_color))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class NavIndicator(QWidget):
    """Small rounded pill that slides beside the active navigation button."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(4)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS["purple_2"]))
        painter.drawRoundedRect(QRectF(self.rect()), 2.0, 2.0)
        painter.end()


class AnimatedPageHost(QWidget):
    """Fade a newly selected page in without animating the whole window."""

    def fade_in(self, page: QWidget) -> None:
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", page)
        animation.setDuration(180)
        animation.setStartValue(0.35)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: page.setGraphicsEffect(None))
        animation.finished.connect(animation.deleteLater)
        animation.start()


class SessionHoverCard(QFrame):
    """Single in-window hover card that follows the cursor over a session.

    It is intentionally a normal child widget, not a native ToolTip window. That
    avoids the compositor ghosting/layering seen with transparent top-level
    tooltip windows while still allowing the card to follow the mouse smoothly.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("hoverCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(230)
        self.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.activity_label = QLabel()
        self.activity_label.setWordWrap(True)
        self.activity_label.setStyleSheet("font-size: 13px; font-weight: 800;")
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(28, 28)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self.activity_label, 1)
        top.addWidget(self.icon_label)
        root.addLayout(top)

        self.category_label = QLabel()
        self.category_label.setObjectName("muted")
        self.category_label.setStyleSheet("font-weight: 600;")
        root.addWidget(self.category_label)

        self.duration_label = QLabel()
        self.duration_label.setStyleSheet(
            f"color: {COLORS['purple_2']}; font-size: 12px; font-weight: 700;"
        )
        root.addWidget(self.duration_label)

    def set_session(self, segment: dict, icon) -> None:
        """Populate activity, category, icon, and duration for one segment."""
        self.activity_label.setText(
            segment.get("hover_label") or segment.get("activity_label") or "Unknown activity"
        )
        self.category_label.setText(segment.get("category_name") or "Misc")
        seconds = max(0.0, float(segment["ended_at"]) - float(segment["started_at"]))
        self.duration_label.setText(format_duration(seconds))
        self.icon_label.setPixmap(icon.pixmap(24, 24))
        self.adjustSize()
        self.setFixedWidth(230)


class CalendarCanvas(QWidget):
    """Paint a seven-column, 24-hour calendar similar to desktop calendars."""

    TIME_GUTTER = 56
    TOP_GUTTER = 8
    MIN_HOUR_HEIGHT = 24
    MAX_HOUR_HEIGHT = 90

    # HomePage owns the actual scroll areas, so these signals let the canvas ask
    # its page to perform zooming or outer-page scrolling without tight coupling.
    zoom_requested = Signal(int)
    outer_scroll_requested = Signal(int)

    def __init__(self, hour_height: int = 36, icon_manager=None, parent=None) -> None:
        super().__init__(parent)
        self.week_start = datetime.now()
        self.segments: list[dict] = []
        self.hour_height = max(self.MIN_HOUR_HEIGHT, min(self.MAX_HOUR_HEIGHT, int(hour_height)))
        self.icon_manager = icon_manager
        self._hit_regions: list[tuple[QRect, dict]] = []
        self.hover_card: SessionHoverCard | None = None
        self.hover_host: QWidget | None = None
        self._modifier_order: list[str] = []
        self.setMouseTracking(True)
        self.setMinimumWidth(660)
        self._update_height()

        # Tracking modifier key press order at the QApplication level makes
        # Ctrl+Shift deterministic even if keyboard focus is inside another
        # control while the mouse is over the graph.
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    @property
    def HOUR_HEIGHT(self) -> int:
        """Compatibility property kept for older learning examples."""
        return self.hour_height

    def eventFilter(self, watched, event) -> bool:
        """Remember whether Ctrl or Shift was pressed first."""
        event_type = event.type()
        if event_type == QEvent.Type.KeyPress and not event.isAutoRepeat():
            if event.key() == Qt.Key.Key_Control and "ctrl" not in self._modifier_order:
                self._modifier_order.append("ctrl")
            elif event.key() == Qt.Key.Key_Shift and "shift" not in self._modifier_order:
                self._modifier_order.append("shift")
        elif event_type == QEvent.Type.KeyRelease and not event.isAutoRepeat():
            if event.key() == Qt.Key.Key_Control and "ctrl" in self._modifier_order:
                self._modifier_order.remove("ctrl")
            elif event.key() == Qt.Key.Key_Shift and "shift" in self._modifier_order:
                self._modifier_order.remove("shift")
        elif event_type == QEvent.Type.ApplicationDeactivate:
            self._modifier_order.clear()
        return False

    def set_hover_host(self, host: QWidget) -> None:
        """Place the hover card inside the visible calendar viewport."""
        if self.hover_card is not None:
            self.hover_card.deleteLater()
        self.hover_host = host
        self.hover_card = SessionHoverCard(host)

    def hide_hover(self) -> None:
        """Hide the single hover overlay before scrolls or data refreshes."""
        if self.hover_card is not None:
            self.hover_card.hide()

    def _update_height(self) -> None:
        self.setMinimumHeight(self.hour_height * 24 + self.TOP_GUTTER)
        self.resize(self.width(), self.minimumHeight())
        self.updateGeometry()

    def set_hour_height(self, value: int) -> None:
        """Change vertical zoom while keeping each day exactly 24 hours tall."""
        self.hour_height = max(self.MIN_HOUR_HEIGHT, min(self.MAX_HOUR_HEIGHT, int(value)))
        self.hide_hover()
        self._update_height()
        self.update()

    def set_data(self, week_start: datetime, segments: list[dict]) -> None:
        """Replace graph data and invalidate stale hover hit regions immediately."""
        self.week_start = week_start
        self.segments = segments
        self._hit_regions.clear()
        self.hide_hover()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(COLORS["panel_2"]))
        self._hit_regions.clear()

        content_left = self.TIME_GUTTER
        column_width = max(1.0, (self.width() - content_left) / 7.0)
        total_height = self.hour_height * 24

        # Horizontal hour lines and clock labels make the calendar readable.
        for hour in range(25):
            y = self.TOP_GUTTER + hour * self.hour_height
            painter.setPen(QPen(QColor("#33283F"), 1))
            painter.drawLine(content_left, y, self.width(), y)
            if hour < 24:
                painter.setPen(QColor(COLORS["muted"]))
                painter.setFont(QFont("Nunito", 8, QFont.Weight.Medium))
                painter.drawText(4, y + 12, f"{hour:02d}:00")

        # Vertical day separators use a slightly different purple-gray tone.
        for day in range(8):
            x = content_left + day * column_width
            painter.setPen(QPen(QColor("#3B2D49"), 1))
            painter.drawLine(int(x), self.TOP_GUTTER, int(x), self.TOP_GUTTER + total_height)

        for segment in self.segments:
            self._paint_session(painter, segment, column_width)

        # Draw the current-time marker last so the bright Google Calendar style
        # line and leading dot remain visible above activity blocks.
        now = datetime.now()
        if self.week_start.date() <= now.date() < (self.week_start + timedelta(days=7)).date():
            day = (now.date() - self.week_start.date()).days
            minutes = now.hour * 60 + now.minute + now.second / 60
            y = self.TOP_GUTTER + minutes / 60.0 * self.hour_height
            x1 = self.TIME_GUTTER + day * column_width
            x2 = x1 + column_width
            current_color = QColor("#E080FF")
            painter.setPen(QPen(current_color, 2))
            painter.drawLine(int(x1), int(y), int(x2), int(y))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(current_color)
            painter.drawEllipse(QPoint(int(x1 + 2), int(y)), 5, 5)

        painter.end()

    def _paint_session(self, painter: QPainter, segment: dict, column_width: float) -> None:
        start = max(datetime.fromtimestamp(segment["started_at"]), self.week_start)
        end = min(datetime.fromtimestamp(segment["ended_at"]), self.week_start + timedelta(days=7))
        if end <= start:
            return

        # A foreground activity can cross midnight. Splitting its drawing at
        # midnight keeps every visual rectangle inside one day column.
        cursor = start
        while cursor < end:
            next_midnight = cursor.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            segment_end = min(end, next_midnight)
            self._paint_segment(painter, segment, cursor, segment_end, column_width)
            cursor = segment_end

    def _paint_segment(
        self,
        painter: QPainter,
        segment: dict,
        start: datetime,
        end: datetime,
        column_width: float,
    ) -> None:
        day_index = (start.date() - self.week_start.date()).days
        if not 0 <= day_index < 7:
            return

        start_minutes = start.hour * 60 + start.minute + start.second / 60
        end_minutes = 24 * 60 if end.date() != start.date() else (
            end.hour * 60 + end.minute + end.second / 60
        )

        x = self.TIME_GUTTER + day_index * column_width + 4
        raw_y = self.TOP_GUTTER + start_minutes / 60 * self.hour_height
        raw_height = max(5.0, (end_minutes - start_minutes) / 60 * self.hour_height)

        # A one-pixel inset at each end creates a clean visual gap between stable
        # activity switches without changing any stored timestamps or totals.
        gap = 1.0 if raw_height >= 7.0 else 0.0
        y = raw_y + gap
        height = max(4.0, raw_height - gap * 2.0)
        rect = QRect(int(x), int(y), max(4, int(column_width - 8)), int(height))

        category_color = QColor(segment.get("category_color") or COLORS["purple"])
        fill = QColor(category_color)
        fill.setAlpha(112)
        border = category_color.lighter(135)
        painter.setPen(QPen(border, 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 6, 6)

        if rect.height() >= 18:
            painter.setPen(QColor(COLORS["text"]))
            painter.setFont(QFont("Nunito", 8, QFont.Weight.DemiBold))
            text_rect = rect.adjusted(5, 2, -4, -2)
            full_label = segment.get("activity_label") or segment.get("process_name") or "Activity"
            metrics = QFontMetrics(painter.font())
            elided = metrics.elidedText(
                full_label,
                Qt.TextElideMode.ElideRight,
                max(1, text_rect.width()),
            )
            painter.drawText(text_rect, Qt.TextFlag.TextSingleLine, elided)

        # Store the exact painted rectangle so hover hit-testing cannot disagree
        # with the pixels on screen.
        hit_segment = dict(segment)
        hit_segment["started_at"] = start.timestamp()
        hit_segment["ended_at"] = end.timestamp()
        self._hit_regions.append((rect, hit_segment))

    def _segment_at(self, point: QPoint) -> dict | None:
        for rect, segment in reversed(self._hit_regions):
            if rect.contains(point):
                return segment
        return None

    def _show_hover(self, segment: dict, global_pos: QPoint) -> None:
        if self.icon_manager is None or self.hover_card is None or self.hover_host is None:
            return

        icon = self.icon_manager.icon_for(segment)
        self.hover_card.set_session(segment, icon)

        # Convert the global cursor into viewport coordinates and clamp the card
        # so it never extends beyond the visible graph area.
        cursor = self.hover_host.mapFromGlobal(global_pos)
        x = cursor.x() + 16
        y = cursor.y() + 16
        width = self.hover_card.width()
        height = self.hover_card.height()
        margin = 8
        if x + width > self.hover_host.width() - margin:
            x = cursor.x() - width - 16
        if y + height > self.hover_host.height() - margin:
            y = cursor.y() - height - 16
        x = max(margin, min(x, self.hover_host.width() - width - margin))
        y = max(margin, min(y, self.hover_host.height() - height - margin))

        self.hover_card.move(x, y)
        self.hover_card.show()
        self.hover_card.raise_()
        self.hover_card.update()

    def mouseMoveEvent(self, event) -> None:
        segment = self._segment_at(event.position().toPoint())
        if segment:
            self._show_hover(segment, event.globalPosition().toPoint())
        else:
            self.hide_hover()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            segment = self._segment_at(event.position().toPoint())
            if segment:
                self._show_hover(segment, event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:
        """Implement Ctrl zoom and Shift outer-page scrolling over the graph."""
        self.hide_hover()
        modifiers = event.modifiers()
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        action: str | None = None
        if ctrl and shift:
            # Use whichever modifier was pressed first, exactly as requested.
            action = next(
                (name for name in self._modifier_order if name in {"ctrl", "shift"}),
                "ctrl",
            )
        elif ctrl:
            action = "ctrl"
        elif shift:
            action = "shift"

        delta = event.angleDelta().y() or event.pixelDelta().y()
        if action == "ctrl" and delta:
            self.zoom_requested.emit(4 if delta > 0 else -4)
            event.accept()
            return
        if action == "shift" and delta:
            self.outer_scroll_requested.emit(delta)
            event.accept()
            return

        super().wheelEvent(event)

    def leaveEvent(self, event) -> None:
        self.hide_hover()
        super().leaveEvent(event)


class ToggleSwitch(QAbstractButton):
    """Animated compact on/off switch used for persistent boolean settings."""

    def __init__(self, checked: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 25)
        self._offset = 1.0 if checked else 0.0
        self.setChecked(checked)
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate_to_state)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = max(0.0, min(1.0, float(value)))
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate_to_state(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = self.rect().adjusted(1, 1, -1, -1)
        track_color = QColor(COLORS["purple_3"] if self.isChecked() else COLORS["panel_4"])
        painter.setPen(QPen(QColor(COLORS["purple_soft"]), 1))
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 12, 12)

        knob_diameter = 19
        travel = self.width() - knob_diameter - 6
        knob_x = 3 + int(travel * self._offset)
        knob_rect = QRect(knob_x, 3, knob_diameter, knob_diameter)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS["text"]))
        painter.drawEllipse(knob_rect)
        painter.end()


class StatCard(QFrame):
    """Simple two-line statistic card used below the calendar."""

    def __init__(self, caption: str, value: str = "-", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        caption_label = QLabel(caption)
        caption_label.setObjectName("muted")
        caption_label.setStyleSheet("font-weight: 600;")
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 21px; font-weight: 800;")
        layout.addWidget(caption_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str, purple: bool = False, color: str | None = None) -> None:
        """Set text plus either theme purple or a category-specific color."""
        self.value_label.setText(value)
        resolved_color = color or (COLORS["purple_2"] if purple else COLORS["text"])
        self.value_label.setStyleSheet(
            f"font-size: 21px; font-weight: 800; color: {resolved_color};"
        )


class ResizeCorner(QSizeGrip):
    """Visible resize grip so a frameless normal window remains resizable."""

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setToolTip("Drag to resize")
