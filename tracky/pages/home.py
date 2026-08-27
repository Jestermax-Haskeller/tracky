"""Home page with the weekly calendar, daily totals, and summary stats."""

from __future__ import annotations

# defaultdict keeps category aggregation concise. datetime/timedelta define week
# boundaries and clip daily totals without bringing date logic into the widgets.
from collections import defaultdict
from datetime import datetime, timedelta

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..database import Database
from ..styles import COLORS
from ..utils import format_duration, week_start_for
from ..widgets import CalendarCanvas, RoundedClipFrame, StatCard


class DayBreakdownCard(QFrame):
    """One compact column summarising categories for one calendar day."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dayBreakdown")
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(8, 9, 8, 9)
        self.layout_box.setSpacing(3)

        self.day_label = QLabel()
        self.day_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.day_label.setStyleSheet("font-size: 11px; font-weight: 800;")
        self.layout_box.addWidget(self.day_label)

        self.total_label = QLabel()
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_label.setStyleSheet(
            f"color: {COLORS['purple_2']}; font-size: 10px; font-weight: 700;"
        )
        self.layout_box.addWidget(self.total_label)
        self.category_widgets: list[QLabel] = []

    def set_data(self, day: datetime, categories: list[tuple[str, str, float]], total: float) -> None:
        """Replace the prior category lines without rebuilding the entire Home page."""
        self.day_label.setText(day.strftime("%a"))
        self.total_label.setText(f"Total {format_duration(total)}")

        for label in self.category_widgets:
            self.layout_box.removeWidget(label)
            label.deleteLater()
        self.category_widgets.clear()

        if not categories:
            empty = QLabel("No activity")
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("font-size: 9px; font-weight: 500;")
            self.layout_box.addWidget(empty)
            self.category_widgets.append(empty)
            return

        for name, color, seconds in categories:
            line = QLabel(f"● {name}\n  {format_duration(seconds)}")
            line.setWordWrap(True)
            line.setToolTip(f"{name}: {format_duration(seconds)}")
            line.setStyleSheet(f"color: {color}; font-size: 9px; font-weight: 700;")
            self.layout_box.addWidget(line)
            self.category_widgets.append(line)


class HomePage(QWidget):
    """Show the selected week and remember the user's calendar zoom level."""

    def __init__(self, database: Database, icons, parent=None) -> None:
        super().__init__(parent)
        self.database = database
        self.icons = icons
        self.week_start = week_start_for(datetime.now())
        self._build_ui()

        # A modest refresh rate keeps a long-running focused session visible
        # without continuously repainting the custom calendar.
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(15_000)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start()
        self.refresh(scroll_to_now=True)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # This outer scroll area owns page-level scrolling below and around the
        # fixed-height calendar viewport.
        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self.page_scroll)

        body = QWidget()
        self.page_scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 16, 28, 28)
        layout.setSpacing(14)

        top = QHBoxLayout()
        title = QLabel("Home")
        title.setObjectName("pageTitle")
        top.addWidget(title)
        top.addStretch()

        self.prev_button = QPushButton("‹")
        self.prev_button.setObjectName("softButton")
        self.reset_button = QPushButton("Reset")
        self.reset_button.setObjectName("softButton")
        self.next_button = QPushButton("›")
        self.next_button.setObjectName("softButton")
        self.zoom_out_button = QPushButton("−")
        self.zoom_out_button.setObjectName("softButton")
        self.zoom_out_button.setToolTip("Zoom out vertically")
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setObjectName("softButton")
        self.zoom_in_button.setToolTip("Zoom in vertically")

        self.prev_button.clicked.connect(lambda: self._move_week(-1))
        self.reset_button.clicked.connect(self._reset_week)
        self.next_button.clicked.connect(lambda: self._move_week(1))
        self.zoom_out_button.clicked.connect(lambda: self._change_zoom(-4))
        self.zoom_in_button.clicked.connect(lambda: self._change_zoom(4))

        # Previous, Reset, and Next form one week-navigation group. Zoom controls
        # remain to the right because they change scale rather than date.
        top.addWidget(self.prev_button)
        top.addWidget(self.reset_button)
        top.addWidget(self.next_button)
        top.addSpacing(8)
        top.addWidget(self.zoom_out_button)
        top.addWidget(self.zoom_in_button)
        layout.addLayout(top)

        self.week_label = QLabel()
        self.week_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(self.week_label)

        header = self._make_day_header()
        layout.addWidget(header)

        # RoundedClipFrame masks its child scroll area, so the calendar content
        # itself follows the rounded card instead of only painting a rounded border.
        calendar_card = RoundedClipFrame(14.0)
        calendar_layout = QVBoxLayout(calendar_card)
        calendar_layout.setContentsMargins(1, 1, 1, 1)
        calendar_layout.setSpacing(0)

        self.calendar_scroll = QScrollArea()
        self.calendar_scroll.setWidgetResizable(True)
        self.calendar_scroll.setMinimumHeight(500)
        self.calendar_scroll.setMaximumHeight(500)

        # 32px per hour is intentionally compact for the default view, while the
        # saved setting restores whatever zoom the user last chose.
        default_zoom = int(self.database.get_setting("calendar_hour_height", "32") or 32)
        self.calendar_canvas = CalendarCanvas(default_zoom, self.icons)
        self.calendar_scroll.setWidget(self.calendar_canvas)
        self.calendar_canvas.set_hover_host(self.calendar_scroll.viewport())

        # Ctrl+wheel asks the page to reuse the same persistent zoom function.
        # Shift+wheel asks the outer page to move while leaving graph zoom alone.
        self.calendar_canvas.zoom_requested.connect(self._change_zoom)
        self.calendar_canvas.outer_scroll_requested.connect(self._scroll_main_page)
        self.calendar_scroll.verticalScrollBar().valueChanged.connect(
            lambda _value: self.calendar_canvas.hide_hover()
        )
        calendar_layout.addWidget(self.calendar_scroll)
        layout.addWidget(calendar_card)

        breakdown_title = QLabel("Daily total")
        breakdown_title.setObjectName("sectionTitle")
        layout.addWidget(breakdown_title)

        # A left spacer mirrors the calendar time gutter, placing each summary
        # directly under the day column it describes.
        breakdown_row = QHBoxLayout()
        breakdown_row.setSpacing(6)
        breakdown_row.addSpacing(CalendarCanvas.TIME_GUTTER)
        self.day_breakdowns: list[DayBreakdownCard] = []
        for _ in range(7):
            card = DayBreakdownCard()
            breakdown_row.addWidget(card, 1)
            self.day_breakdowns.append(card)
        layout.addLayout(breakdown_row)

        stats_heading = QLabel("Stats")
        stats_heading.setObjectName("sectionTitle")
        layout.addWidget(stats_heading)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.average_card = StatCard("Daily Average")
        self.difference_card = StatCard("Weekly % Difference")
        self.top_card = StatCard("Top Category")
        cards.addWidget(self.average_card)
        cards.addWidget(self.difference_card)
        cards.addWidget(self.top_card)
        layout.addLayout(cards)
        layout.addStretch()

    def _make_day_header(self) -> QFrame:
        """Build seven day labels aligned exactly with the calendar columns."""
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedHeight(54)
        self.day_header_layout = QHBoxLayout(frame)
        self.day_header_layout.setContentsMargins(CalendarCanvas.TIME_GUTTER, 6, 8, 6)
        self.day_header_layout.setSpacing(0)
        self.day_header_labels: list[QLabel] = []
        for _ in range(7):
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.day_header_layout.addWidget(label, 1)
            self.day_header_labels.append(label)
        return frame

    def _move_week(self, delta: int) -> None:
        """Move exactly one week backward or forward without changing zoom."""
        self.week_start += timedelta(days=7 * delta)
        self.refresh(scroll_to_now=False)

    def _reset_week(self) -> None:
        """Return to today's week and bring the current hour back into view."""
        self.week_start = week_start_for(datetime.now())
        self.refresh(scroll_to_now=True)

    def _change_zoom(self, delta: int) -> None:
        """Zoom around the currently visible time and persist the preference."""
        old_height = self.calendar_canvas.hour_height
        old_scroll = self.calendar_scroll.verticalScrollBar().value()
        hour_at_top = old_scroll / max(1, old_height)

        new_height = max(
            CalendarCanvas.MIN_HOUR_HEIGHT,
            min(CalendarCanvas.MAX_HOUR_HEIGHT, old_height + int(delta)),
        )
        if new_height == old_height:
            return

        self.calendar_canvas.set_hour_height(new_height)
        self.database.set_setting("calendar_hour_height", new_height)
        self.calendar_scroll.verticalScrollBar().setValue(int(hour_at_top * new_height))

    def _scroll_main_page(self, wheel_delta: int) -> None:
        """Route Shift+wheel over the graph to the Home page's outer scrollbar."""
        bar = self.page_scroll.verticalScrollBar()
        bar.setValue(bar.value() - int(wheel_delta))

    def refresh(self, scroll_to_now: bool = False) -> None:
        """Reload calendar segments, day totals, and summary stats for the week."""
        start_ts = self.week_start.timestamp()
        end_ts = (self.week_start + timedelta(days=7)).timestamp()
        segments = self.database.calendar_segments_between(start_ts, end_ts)
        self.calendar_canvas.set_data(self.week_start, segments)

        end_date = self.week_start + timedelta(days=6)
        self.week_label.setText(
            f"{self.week_start.strftime('%d %b')} - {end_date.strftime('%d %b %Y')}"
        )

        today = datetime.now().date()
        for index, label in enumerate(self.day_header_labels):
            day = self.week_start + timedelta(days=index)
            text = f"{day.strftime('%a')}\n{day.day}"
            if day.date() == today:
                label.setText(f"●  {text}")
                label.setStyleSheet(f"font-weight: 800; color: {COLORS['purple_2']};")
            else:
                label.setText(text)
                label.setStyleSheet(f"color: {COLORS['muted']}; font-weight: 600;")

        self._refresh_breakdowns(segments)
        self._refresh_stats(segments)

        if scroll_to_now:
            now = datetime.now()
            target = max(0, int((now.hour - 2) * self.calendar_canvas.hour_height))
            self.calendar_scroll.verticalScrollBar().setValue(target)

    def _refresh_breakdowns(self, segments: list[dict]) -> None:
        """Aggregate every category into the day card directly below it."""
        for day_index, card in enumerate(self.day_breakdowns):
            day_start = self.week_start + timedelta(days=day_index)
            day_end = day_start + timedelta(days=1)
            start_ts = day_start.timestamp()
            end_ts = day_end.timestamp()
            by_category: dict[tuple[str, str], float] = defaultdict(float)

            for segment in segments:
                overlap = max(
                    0.0,
                    min(float(segment["ended_at"]), end_ts)
                    - max(float(segment["started_at"]), start_ts),
                )
                if overlap:
                    key = (segment["category_name"], segment["category_color"])
                    by_category[key] += overlap

            ordered = sorted(
                ((name, color, seconds) for (name, color), seconds in by_category.items()),
                key=lambda item: item[2],
                reverse=True,
            )
            card.set_data(day_start, ordered, sum(item[2] for item in ordered))

    def _refresh_stats(self, segments: list[dict]) -> None:
        """Populate Daily Average, weekly difference, and color-coded Top Category."""
        total = sum(float(segment.get("duration") or 0) for segment in segments)
        now = datetime.now()
        if self.week_start <= now < self.week_start + timedelta(days=7):
            days = max(1, (now.date() - self.week_start.date()).days + 1)
        else:
            days = 7

        # Daily Average now uses the same purple emphasis as Weekly % Difference.
        self.average_card.set_value(format_duration(total / days if days else 0), purple=True)

        previous_start = self.week_start - timedelta(days=7)
        if self.week_start <= now < self.week_start + timedelta(days=7):
            # Compare a current partial week against the same elapsed slice of the
            # previous week so Wednesday is not unfairly compared with seven days.
            elapsed = now - self.week_start
            previous_end = previous_start + elapsed
        else:
            previous_end = self.week_start

        previous_segments = self.database.calendar_segments_between(
            previous_start.timestamp(), previous_end.timestamp()
        )
        previous_total = sum(
            float(segment.get("duration") or 0) for segment in previous_segments
        )
        if previous_total > 0:
            difference = ((total - previous_total) / previous_total) * 100.0
        elif total > 0:
            difference = 100.0
        else:
            difference = 0.0
        prefix = "+" if difference >= 0 else ""
        self.difference_card.set_value(f"{prefix}{difference:.1f}%", purple=True)

        by_category: dict[tuple[str, str], float] = defaultdict(float)
        for segment in segments:
            key = (segment["category_name"], segment["category_color"])
            by_category[key] += float(segment.get("duration") or 0)

        if by_category:
            (name, color), seconds = max(by_category.items(), key=lambda pair: pair[1])
            self.top_card.set_value(
                f"{name} · {format_duration(seconds)}",
                color=color,
            )
        else:
            self.top_card.set_value("-", color=COLORS["muted"])
