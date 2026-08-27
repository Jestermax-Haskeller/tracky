"""Labeling page for naming activities and grouping them into categories."""

from __future__ import annotations

# Path starts the custom-icon picker in the user's home folder. defaultdict makes
# it easy to group activity rows into category folders before rendering them.
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import QRegularExpression, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette, QPen, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..database import Database
from ..icons import IconManager
from ..styles import COLORS
from ..utils import format_duration, shorten_text


# These colors intentionally do not mirror Tracky's purple theme. They are a
# practical category palette with slightly softened values that remain readable
# over the dark calendar when the paint layer applies transparency.
PRESET_COLORS = (
    ("Red", "#E76F6F"),
    ("Orange", "#F29E62"),
    ("Yellow", "#E6C968"),
    ("Light Green", "#91C98A"),
    ("Dark Green", "#4E936B"),
    ("Teal", "#62C6B7"),
    ("Light Blue", "#86BDEB"),
    ("Dark Blue", "#507CC4"),
    ("Purple", "#A47FD1"),
    ("Baby Pink", "#E8A6C5"),
)


class ColorCircleButton(QAbstractButton):
    """One clickable translucent color dot used by the category popup."""

    def __init__(self, color: str, tooltip: str, parent=None) -> None:
        super().__init__(parent)
        self.color = color
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(26, 26)
        self.setToolTip(tooltip)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        circle = QRectF(self.rect()).adjusted(3.0, 3.0, -3.0, -3.0)

        fill = QColor(self.color)
        fill.setAlpha(215)
        painter.setBrush(fill)
        if self.isChecked():
            painter.setPen(QPen(QColor(COLORS["text"]), 2.0))
        else:
            border = QColor(self.color).lighter(120)
            border.setAlpha(160)
            painter.setPen(QPen(border, 1.0))
        painter.drawEllipse(circle)
        painter.end()


class CategoryDialog(QDialog):
    """Frameless three-line popup for creating a category and choosing its color."""

    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.database = database
        self.selected_color = PRESET_COLORS[0][1]

        # FramelessWindowHint removes the normal Windows mini title bar so this
        # feels like part of Tracky rather than a separate desktop application.
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(500)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        panel = QFrame()
        panel.setObjectName("categoryDialogCard")
        outer.addWidget(panel)

        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 155))
        panel.setGraphicsEffect(shadow)

        root = QVBoxLayout(panel)
        root.setContentsMargins(18, 18, 18, 16)
        root.setSpacing(13)

        # Line 1: category name.
        name_row = QHBoxLayout()
        name_row.setSpacing(12)
        name_label = QLabel("Name")
        name_label.setFixedWidth(100)
        name_label.setStyleSheet("font-weight: 700;")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Studing")
        name_row.addWidget(name_label)
        name_row.addWidget(self.name_edit, 1)
        root.addLayout(name_row)

        # Line 2: one horizontal row of the ten requested preset color circles.
        color_row = QHBoxLayout()
        color_row.setSpacing(6)
        color_label = QLabel("Colors")
        color_label.setFixedWidth(100)
        color_label.setStyleSheet("font-weight: 700;")
        color_row.addWidget(color_label)

        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        for index, (name, color) in enumerate(PRESET_COLORS):
            button = ColorCircleButton(color, name)
            self.color_group.addButton(button)
            button.clicked.connect(
                lambda checked=False, selected=color: self._preset_clicked(selected)
            )
            if index == 0:
                button.setChecked(True)
            color_row.addWidget(button)
        color_row.addStretch()
        root.addLayout(color_row)

        # Line 3: the # prefix stays white while only the faded placeholder text
        # disappears as the user starts typing a custom six-digit HEX value.
        custom_row = QHBoxLayout()
        custom_row.setSpacing(12)
        custom_label = QLabel("Custom Colors")
        custom_label.setFixedWidth(100)
        custom_label.setStyleSheet("font-weight: 700;")
        custom_row.addWidget(custom_label)

        hex_frame = QFrame()
        hex_frame.setObjectName("hexInput")
        hex_layout = QHBoxLayout(hex_frame)
        hex_layout.setContentsMargins(10, 0, 8, 0)
        hex_layout.setSpacing(3)
        prefix = QLabel("#")
        prefix.setStyleSheet(f"color: {COLORS['text']}; font-weight: 800;")
        self.hex_edit = QLineEdit()
        self.hex_edit.setObjectName("hexValue")
        self.hex_edit.setPlaceholderText("enter your HEX")
        self.hex_edit.setMaxLength(6)
        self.hex_edit.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"[0-9A-Fa-f]{0,6}"), self.hex_edit)
        )
        placeholder_palette = self.hex_edit.palette()
        placeholder_palette.setColor(
            QPalette.ColorRole.PlaceholderText,
            QColor(COLORS["muted"]),
        )
        self.hex_edit.setPalette(placeholder_palette)
        hex_layout.addWidget(prefix)
        hex_layout.addWidget(self.hex_edit, 1)
        custom_row.addWidget(hex_frame, 1)
        root.addLayout(custom_row)

        # Invalid input is reported inside the popup rather than opening another
        # native message box with its own title bar.
        self.error_label = QLabel()
        self.error_label.setStyleSheet(
            f"color: {COLORS['danger']}; font-size: 10px; font-weight: 700;"
        )
        self.error_label.hide()
        root.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("dialogPurpleButton")
        save = QPushButton("Save")
        save.setObjectName("accentButton")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

        self.name_edit.returnPressed.connect(self._save)
        self.hex_edit.returnPressed.connect(self._save)

    def _preset_clicked(self, color: str) -> None:
        """Remember the selected dot without filling the custom HEX field."""
        self.selected_color = color
        self.hex_edit.clear()

    def _save(self) -> None:
        """Validate the optional custom HEX value and persist the category."""
        custom = self.hex_edit.text().strip().lstrip("#")
        color = f"#{custom}" if custom else self.selected_color
        try:
            self.database.create_category(self.name_edit.text(), color)
        except (ValueError, TypeError) as exc:
            self.error_label.setText(str(exc))
            self.error_label.show()
            return
        self.accept()


class LabelRow(QFrame):
    """One raw application or website plus its user-editable metadata."""

    category_changed = Signal()

    def __init__(self, entity: dict, database: Database, icons: IconManager, parent=None) -> None:
        super().__init__(parent)
        self.entity = entity
        self.database = database
        self.icons = icons
        self.categories = self.database.categories()
        self.setObjectName("labelRow")
        self.setMinimumHeight(82)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 10, 12, 10)
        layout.setSpacing(10)

        # The category stripe gives immediate color feedback without making the
        # whole row too saturated for the dark interface.
        self.color_stripe = QFrame()
        self.color_stripe.setFixedWidth(4)
        self.color_stripe.setStyleSheet(
            f"background: {entity['category_color']}; border-radius: 2px;"
        )
        layout.addWidget(self.color_stripe)

        self.icon_button = QPushButton()
        self.icon_button.setObjectName("softButton")
        self.icon_button.setFixedSize(48, 48)
        self.icon_button.setIconSize(QSize(36, 36))
        self.icon_button.setToolTip("Click to choose a custom icon")
        self.icon_button.setIcon(self.icons.icon_for(entity))
        self.icon_button.clicked.connect(self.choose_icon)
        layout.addWidget(self.icon_button)

        info = QVBoxLayout()
        info.setSpacing(3)
        source = self._source_title(entity)
        source_label = QLabel(shorten_text(source, 65))
        source_label.setToolTip(source)
        source_label.setMinimumWidth(0)
        source_label.setMaximumWidth(330)
        source_label.setStyleSheet("font-weight: 800;")

        detail_text = self._source_detail(entity)
        detail = QLabel(shorten_text(detail_text, 65))
        detail.setToolTip(detail_text)
        detail.setObjectName("muted")
        detail.setMinimumWidth(0)
        detail.setMaximumWidth(330)
        info.addWidget(source_label)
        info.addWidget(detail)
        layout.addLayout(info, 1)

        duration = QLabel(format_duration(float(entity.get("total_duration") or 0)))
        duration.setObjectName("muted")
        duration.setMinimumWidth(62)
        duration.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(duration)

        self.label_edit = QLineEdit(entity["effective_label"])
        self.label_edit.setPlaceholderText("Friendly label")
        self.label_edit.setMinimumWidth(150)
        self.label_edit.setMaximumWidth(240)
        self.label_edit.editingFinished.connect(self.save_label)
        layout.addWidget(self.label_edit)

        # The far-right selector groups an activity. Short websites remain locked
        # to Browsing until that domain reaches ten cumulative minutes.
        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(138)
        for category in self.categories:
            self.category_combo.addItem(f"●  {category['name']}", int(category["id"]))
            index = self.category_combo.count() - 1
            self.category_combo.setItemData(
                index,
                QColor(category["color"]),
                Qt.ItemDataRole.ForegroundRole,
            )
        selected = self.category_combo.findData(int(entity["category_id"]))
        self.category_combo.blockSignals(True)
        self.category_combo.setCurrentIndex(max(0, selected))
        self.category_combo.blockSignals(False)
        self.category_combo.currentIndexChanged.connect(self.save_category)
        if entity.get("auto_browsing"):
            self.category_combo.setEnabled(False)
            self.category_combo.setToolTip(
                "Websites stay in Browsing until this domain reaches 10 minutes."
            )
        layout.addWidget(self.category_combo)

        self.icons.icon_ready.connect(self._icon_ready)

    def _source_title(self, entity: dict) -> str:
        """Show only a domain for websites, never a page path or query."""
        key = entity["entity_key"]
        if key.startswith("web:"):
            return key.removeprefix("web:")
        return entity.get("process_name") or key.removeprefix("app:")

    def _source_detail(self, entity: dict) -> str:
        """Keep the full latest URL as secondary labeling context, clipped to 65."""
        if entity["entity_key"].startswith("web:"):
            return entity.get("latest_url") or "Website"
        return entity.get("process_path") or "Application process"

    def save_label(self) -> None:
        """Persist a friendly activity label after the edit loses focus."""
        value = self.label_edit.text().strip()
        if value:
            self.database.set_label(self.entity["entity_key"], value)

    def save_category(self) -> None:
        """Persist the chosen category and update the row color immediately."""
        category_id = self.category_combo.currentData()
        if category_id is None or self.entity.get("auto_browsing"):
            return
        self.database.set_entity_category(self.entity["entity_key"], int(category_id))
        selected = next(
            (c for c in self.categories if int(c["id"]) == int(category_id)),
            None,
        )
        if selected:
            self.color_stripe.setStyleSheet(
                f"background: {selected['color']}; border-radius: 2px;"
            )
        self.category_changed.emit()

    def choose_icon(self) -> None:
        """Let the user replace the automatic executable or favicon image."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose an icon",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.ico *.webp);;All files (*.*)",
        )
        if path:
            saved = self.icons.save_custom_icon(self.entity["entity_key"], path)
            self.entity["custom_icon"] = saved
            self.icon_button.setIcon(self.icons.icon_for(self.entity))

    def _icon_ready(self, entity_key: str) -> None:
        """Refresh this row when an asynchronously downloaded favicon arrives."""
        if entity_key == self.entity["entity_key"]:
            self.icon_button.setIcon(self.icons.icon_for(self.entity))


class CategoryFolder(QFrame):
    """One collapsible category group containing its visible activity rows.

    Treating the entire category as one widget makes refreshing the Labeling page
    predictable and gives the user a large, easy target for collapsing folders.
    """

    category_changed = Signal()
    collapse_changed = Signal(int, bool)
    delete_requested = Signal(int)

    def __init__(
        self,
        category: dict,
        entities: list[dict],
        database: Database,
        icons: IconManager,
        collapsed: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.category = category
        self.category_id = int(category["id"])
        self._collapsed = bool(collapsed)
        self.setObjectName("categoryFolder")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(7)

        # The whole header is clickable. A single chevron changes direction so
        # the folder state is obvious without adding another small control.
        self.header_button = QPushButton()
        self.header_button.setObjectName("categoryFolderHeader")
        self.header_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_button.clicked.connect(self.toggle_collapsed)

        # A category folder can be managed without adding permanent buttons to
        # every heading. Right-click opens a compact Tracky-styled context menu.
        # The two built-in folders stay protected because automatic browser and
        # fallback grouping require them to exist.
        self.header_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.header_button.customContextMenuRequested.connect(self._show_context_menu)
        root.addWidget(self.header_button)

        self.body = QWidget()
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(9)

        if not entities:
            empty = QLabel("No activities yet")
            empty.setObjectName("muted")
            empty.setStyleSheet("padding: 3px 10px 9px 10px; font-size: 10px;")
            body_layout.addWidget(empty)
        else:
            for entity in entities:
                row = LabelRow(entity, database, icons)
                row.category_changed.connect(self.category_changed.emit)
                body_layout.addWidget(row)

        root.addWidget(self.body)
        self._apply_state()

    def toggle_collapsed(self) -> None:
        """Open or close the folder and report the state for persistence."""
        self._collapsed = not self._collapsed
        self._apply_state()
        self.collapse_changed.emit(self.category_id, self._collapsed)

    def _show_context_menu(self, position) -> None:
        """Offer deletion when the user right-clicks a custom category folder."""
        menu = QMenu(self)
        menu.setObjectName("categoryContextMenu")
        delete_action = menu.addAction("Delete category")

        # Misc and Browsing are structural defaults. Showing a disabled action
        # makes the right-click behavior discoverable without allowing Tracky's
        # automatic grouping rules to lose their required destination folders.
        if int(self.category.get("is_builtin") or 0):
            delete_action.setEnabled(False)
            delete_action.setText("Default category")
        else:
            delete_action.triggered.connect(
                lambda checked=False: self.delete_requested.emit(self.category_id)
            )

        menu.exec(self.header_button.mapToGlobal(position))

    def _apply_state(self) -> None:
        """Update body visibility and the colored folder heading."""
        self.body.setVisible(not self._collapsed)
        chevron = "›" if self._collapsed else "⌄"
        self.header_button.setText(f"{chevron}   {self.category['name']}")
        self.header_button.setStyleSheet(
            f"color: {self.category['color']}; font-size: 14px; font-weight: 800;"
        )


class LabelingPage(QWidget):
    """Scrollable category-folder labeling workspace."""

    def __init__(self, database: Database, icons: IconManager, parent=None) -> None:
        super().__init__(parent)
        self.database = database
        self.icons = icons

        # Folder collapse state is a lightweight UI preference, so store category
        # IDs as a comma-separated setting instead of introducing another table.
        saved = self.database.get_setting("labeling_collapsed_categories", "") or ""
        self.collapsed_category_ids = {
            int(part) for part in saved.split(",") if part.strip().isdigit()
        }
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 2, 28, 24)
        root.setSpacing(12)

        # The old explanatory subtitle/tip consumed useful horizontal and vertical
        # space. The page now starts with only the title and category action.
        header = QHBoxLayout()
        title = QLabel("Labeling")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()

        self.new_category_button = QPushButton("+ Category")
        self.new_category_button.setObjectName("accentButton")
        self.new_category_button.clicked.connect(self.create_category)
        header.addWidget(self.new_category_button, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self.scroll, 1)

        self.container = QWidget()
        self.rows_layout = QVBoxLayout(self.container)
        self.rows_layout.setContentsMargins(0, 4, 4, 4)
        self.rows_layout.setSpacing(9)
        self.rows_layout.addStretch()
        self.scroll.setWidget(self.container)

    def create_category(self) -> None:
        """Open the custom frameless category popup and refresh after save."""
        dialog = CategoryDialog(self.database, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _clear_rows(self) -> None:
        """Remove old dynamically created group headings and activity rows."""
        while self.rows_layout.count() > 1:
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _folder_collapse_changed(self, category_id: int, collapsed: bool) -> None:
        """Remember folder state so an app restart keeps the workspace tidy."""
        if collapsed:
            self.collapsed_category_ids.add(category_id)
        else:
            self.collapsed_category_ids.discard(category_id)
        stored = ",".join(str(value) for value in sorted(self.collapsed_category_ids))
        self.database.set_setting("labeling_collapsed_categories", stored)

    def _delete_category(self, category_id: int) -> None:
        """Delete a custom folder and return all of its activities to Misc."""
        try:
            self.database.delete_category(category_id)
        except (ValueError, RuntimeError):
            # The UI only enables deletion for custom categories, but the
            # database remains the final safety boundary in case the menu state
            # is stale during a refresh. Nothing should crash or lose history.
            return

        self.collapsed_category_ids.discard(category_id)
        stored = ",".join(str(value) for value in sorted(self.collapsed_category_ids))
        self.database.set_setting("labeling_collapsed_categories", stored)
        self.refresh()

    def refresh(self) -> None:
        """Show collapsible category folders and hide rows below one minute."""
        self._clear_rows()

        # Sub-minute activities are still stored in SQLite and contribute to
        # later totals. Hiding them here keeps accidental or very brief activity
        # from cluttering the organization screen.
        entities = [
            entity
            for entity in self.database.entity_summaries()
            if float(entity.get("total_duration") or 0.0) >= 60.0
        ]
        categories = self.database.categories()

        grouped: dict[int, list[dict]] = defaultdict(list)
        for entity in entities:
            grouped[int(entity["category_id"])].append(entity)

        insert_at = 0
        for category in categories:
            category_id = int(category["id"])
            rows = sorted(
                grouped.get(category_id, []),
                key=lambda entity: -float(entity.get("last_seen") or 0),
            )
            folder = CategoryFolder(
                category,
                rows,
                self.database,
                self.icons,
                collapsed=category_id in self.collapsed_category_ids,
            )
            folder.category_changed.connect(self.refresh)
            folder.collapse_changed.connect(self._folder_collapse_changed)
            folder.delete_requested.connect(self._delete_category)
            self.rows_layout.insertWidget(insert_at, folder)
            insert_at += 1

