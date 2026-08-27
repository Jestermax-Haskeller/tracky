"""Central palette and Qt style sheet for Tracky.

Visual constants live here so a learner can change the whole application from
one file. The palette keeps an Obsidian inspired dark base while using several
purple shades so panels, controls, accents, and data blocks do not all look the
same.
"""

COLORS = {
    "bg": "#0D0B12",
    "panel": "#15101F",
    "panel_2": "#1C1528",
    "panel_3": "#241A34",
    "panel_4": "#2C1F41",
    "border": "#3A2C50",
    "border_bright": "#553C78",
    "text": "#F7F1FF",
    "muted": "#AAA0B8",
    "purple": "#9B5CFF",
    "purple_2": "#C084FC",
    "purple_3": "#7C3AED",
    "purple_4": "#B56CFF",
    "purple_soft": "#5A3A83",
    "danger": "#EF6B73",
}


# Nunito is loaded at application startup when it is available. The Segoe UI
# fallback means the program still starts if the first run has no internet.
APP_STYLESHEET = f"""
* {{
    font-family: 'Nunito', 'Segoe UI';
    font-weight: 400;
    color: {COLORS['text']};
}}

QWidget {{
    background: transparent;
}}

QFrame#windowFrame {{
    /* WindowSurface paints the shell and border itself to avoid corner pixels. */
    background: transparent;
    border: none;
}}

QFrame#sidebar {{
    background: {COLORS['panel']};
    border-right: 1px solid {COLORS['border']};
    border-top-left-radius: 18px;
    border-bottom-left-radius: 18px;
}}

QFrame#sidebar[maximized="true"] {{
    border-top-left-radius: 0px;
    border-bottom-left-radius: 0px;
}}

QLabel#brand {{
    color: {COLORS['purple_2']};
    font-size: 24px;
    font-weight: 800;
}}

QLabel#brandCaption {{
    color: {COLORS['muted']};
    font-size: 10px;
    font-weight: 600;
}}

QLabel#pageTitle {{
    font-size: 28px;
    font-weight: 800;
}}

QLabel#sectionTitle {{
    font-size: 18px;
    font-weight: 700;
}}

QLabel#muted {{
    color: {COLORS['muted']};
    font-weight: 500;
}}

QPushButton#navButton {{
    background: transparent;
    color: {COLORS['muted']};
    text-align: left;
    padding: 10px 14px;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
}}

QPushButton#navButton:hover {{
    background: {COLORS['panel_3']};
    color: {COLORS['text']};
}}

QPushButton#navButton[active="true"] {{
    background: {COLORS['panel_2']};
    color: {COLORS['purple_2']};
    font-weight: 700;
}}

QPushButton#windowButton {{
    border: none;
    border-radius: 8px;
    background: transparent;
    color: {COLORS['muted']};
    min-width: 30px;
    min-height: 28px;
    font-weight: 700;
}}

QPushButton#windowButton:hover {{
    background: {COLORS['panel_4']};
    color: {COLORS['text']};
}}

QPushButton#closeButton {{
    border: none;
    border-radius: 8px;
    background: transparent;
    color: {COLORS['muted']};
    min-width: 30px;
    min-height: 28px;
    font-weight: 700;
}}

QPushButton#closeButton:hover {{
    background: #4A2027;
    color: #FFD9DD;
}}

QFrame#card, QFrame#statCard, QFrame#labelRow, QFrame#dayBreakdown, QFrame#settingsCard {{
    background: {COLORS['panel_2']};
    border: 1px solid {COLORS['border']};
    border-radius: 14px;
}}

QFrame#hoverCard {{
    background: {COLORS['panel_4']};
    border: 1px solid {COLORS['purple_soft']};
    border-radius: 12px;
}}



QFrame#categoryFolder {{
    background: transparent;
    border: none;
}}

QPushButton#categoryFolderHeader {{
    background: {COLORS['panel_2']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    padding: 9px 12px;
    text-align: left;
}}

QPushButton#categoryFolderHeader:hover {{
    background: {COLORS['panel_3']};
    border-color: {COLORS['border_bright']};
}}

QMenu#categoryContextMenu {{
    background: {COLORS['panel_3']};
    border: 1px solid {COLORS['border_bright']};
    border-radius: 9px;
    padding: 5px;
}}

QMenu#categoryContextMenu::item {{
    background: transparent;
    border-radius: 6px;
    padding: 7px 18px 7px 10px;
    font-weight: 700;
}}

QMenu#categoryContextMenu::item:selected {{
    background: {COLORS['purple_soft']};
    color: {COLORS['text']};
}}

QMenu#categoryContextMenu::item:disabled {{
    color: {COLORS['muted']};
}}

QFrame#categoryDialogCard {{
    background: {COLORS['panel_2']};
    border: 1px solid {COLORS['border_bright']};
    border-radius: 16px;
}}

QFrame#hexInput {{
    background: {COLORS['panel_3']};
    border: 1px solid {COLORS['border']};
    border-radius: 9px;
    min-height: 36px;
}}

QLineEdit#hexValue {{
    background: transparent;
    border: none;
    padding: 7px 2px;
}}

QLineEdit#hexValue:focus {{
    border: none;
}}

QPushButton#dialogPurpleButton {{
    background: {COLORS['panel_4']};
    border: 1px solid {COLORS['purple_3']};
    border-radius: 9px;
    padding: 7px 12px;
    font-weight: 700;
}}

QPushButton#dialogPurpleButton:hover {{
    background: {COLORS['purple_soft']};
    border-color: {COLORS['purple_2']};
}}

QLineEdit {{
    background: {COLORS['panel_3']};
    border: 1px solid {COLORS['border']};
    border-radius: 9px;
    padding: 8px 10px;
    selection-background-color: {COLORS['purple']};
    font-weight: 600;
}}

QLineEdit:focus {{
    border: 1px solid {COLORS['purple_2']};
}}

QPushButton#softButton {{
    background: {COLORS['panel_3']};
    border: 1px solid {COLORS['border']};
    border-radius: 9px;
    padding: 7px 10px;
    font-weight: 700;
}}

QPushButton#softButton:hover {{
    border-color: {COLORS['purple']};
    background: {COLORS['panel_4']};
}}

QPushButton#accentButton {{
    background: {COLORS['purple_3']};
    border: 1px solid {COLORS['purple']};
    border-radius: 9px;
    padding: 7px 12px;
    font-weight: 700;
}}

QPushButton#accentButton:hover {{
    background: {COLORS['purple']};
}}

QComboBox {{
    background: {COLORS['panel_3']};
    border: 1px solid {COLORS['border']};
    border-radius: 9px;
    padding: 7px 10px;
    min-height: 20px;
    font-weight: 600;
}}

QComboBox:hover, QComboBox:focus {{
    border-color: {COLORS['purple']};
}}

QComboBox QAbstractItemView {{
    background: {COLORS['panel_3']};
    border: 1px solid {COLORS['border_bright']};
    selection-background-color: {COLORS['purple_soft']};
    outline: none;
    padding: 4px;
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {COLORS['purple']};
    min-height: 28px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLORS['purple_2']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}

QScrollBar::handle:horizontal {{
    background: {COLORS['purple']};
    min-width: 28px;
    border-radius: 5px;
}}

QToolTip {{
    background: {COLORS['panel_4']};
    border: 1px solid {COLORS['purple_soft']};
    color: {COLORS['text']};
    padding: 6px;
}}

QCheckBox {{
    spacing: 10px;
    font-weight: 600;
}}

QCheckBox::indicator {{
    width: 38px;
    height: 20px;
    border-radius: 10px;
    background: {COLORS['panel_4']};
    border: 1px solid {COLORS['border_bright']};
}}

QCheckBox::indicator:checked {{
    background: {COLORS['purple_3']};
    border-color: {COLORS['purple_2']};
}}
"""
