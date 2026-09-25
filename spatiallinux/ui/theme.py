BG = "#08070f"
PANEL = "#120f1e"
PANEL_LIGHT = "#1b1730"
PANEL_LIGHTER = "#251f42"
ACCENT = "#8b5cf6"
ACCENT2 = "#c084fc"
ACCENT_DIM = "#4c3a8f"
TEXT = "#eef0f6"
TEXT_DIM = "#8a8fa3"
TEXT_FAINT = "#565b70"
DANGER = "#e0517a"
OK = "#37e0c9"

STYLESHEET = f"""
QMainWindow, QWidget#root {{
    background: {BG};
}}
QWidget {{
    color: {TEXT};
    font-family: "Noto Sans", sans-serif;
}}
QLabel#title {{
    font-size: 19px;
    font-weight: 700;
    letter-spacing: 1px;
    color: {TEXT};
}}
QLabel#subtitle {{
    color: {TEXT_DIM};
    font-size: 11px;
}}
QLabel#section {{
    color: {TEXT_DIM};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QLabel#byline {{
    color: {TEXT_FAINT};
    font-size: 11px;
    padding-bottom: 3px;
}}
QLabel#byline:hover {{
    color: {ACCENT2};
}}
QLabel#version {{
    color: {TEXT_FAINT};
    font-size: 9px;
    letter-spacing: 1px;
}}
QWidget#intro {{
    background: {BG};
}}
QLabel#introTitle {{
    font-size: 24px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#introByline {{
    font-size: 12px;
    color: {ACCENT2};
    letter-spacing: 1px;
}}
QLabel#introText {{
    font-size: 13px;
    color: {TEXT_DIM};
    padding: 0 60px;
}}
QLabel#introStep {{
    font-size: 13px;
    color: {TEXT};
    padding: 0 60px;
}}
QPushButton#introNext {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT2});
    color: white;
    font-weight: 700;
    border-radius: 18px;
    padding: 9px 22px;
}}
QPushButton#introSkip {{
    background: transparent;
    color: {TEXT_DIM};
}}
QPushButton#introSkip:hover {{
    color: {TEXT};
}}
QPushButton#introLang {{
    background: {PANEL_LIGHT};
    color: {TEXT_DIM};
    border-radius: 11px;
    padding: 4px 12px;
    font-size: 11px;
}}
QFrame#mixer {{
    background: {PANEL};
    border: 1px solid {PANEL_LIGHTER};
    border-radius: 14px;
}}
QScrollArea#mixerScroll, QScrollArea#mixerScroll > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {PANEL_LIGHTER};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_DIM};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    background: transparent;
}}
QLabel#mixerApp {{
    font-size: 12px;
    font-weight: 600;
    color: {TEXT};
}}
QPushButton#mute {{
    background: {PANEL_LIGHT};
    border-radius: 8px;
    padding: 0;
}}
QPushButton#mute:checked {{
    background: {PANEL_LIGHT};
}}
QPushButton#mute:hover {{
    background: {PANEL_LIGHTER};
}}
QPushButton#rowToggle {{
    padding: 2px 0;
    border-radius: 8px;
    font-size: 11px;
}}
QSlider::sub-page:horizontal:disabled {{
    background: {ACCENT_DIM};
}}
QSlider::handle:horizontal:disabled {{
    background: {TEXT_FAINT};
}}
QPushButton#globe {{
    background: {PANEL_LIGHT};
    border-radius: 17px;
    font-size: 15px;
    padding: 0;
}}
QPushButton#globe:hover {{
    background: {ACCENT_DIM};
}}
QLabel#pill {{
    background: {PANEL_LIGHT};
    border-radius: 10px;
    padding: 3px 10px;
    color: {TEXT_DIM};
    font-size: 11px;
}}
QFrame#panel {{
    background: {PANEL};
    border-radius: 16px;
}}
QFrame#header {{
    background: {PANEL};
    border-radius: 16px;
}}
QSlider::groove:horizontal {{
    background: {PANEL_LIGHTER};
    height: 5px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QSlider::add-page:horizontal {{
    background: {PANEL_LIGHTER};
    border-radius: 2px;
}}
QPushButton {{
    background: {PANEL_LIGHT};
    border: none;
    border-radius: 9px;
    padding: 7px 16px;
    color: {TEXT};
}}
QPushButton:hover {{
    background: {PANEL_LIGHTER};
}}
QPushButton:checked {{
    background: {ACCENT};
    color: #0b0d12;
    font-weight: 600;
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
}}
QPushButton#feature {{
    font-size: 11px;
    padding: 4px 2px;
}}
/* a feature that is currently doing something gets a coloured edge, so the
   row shows at a glance what is engaged without opening each panel */
QPushButton#feature[active="true"] {{
    border: 1px solid {ACCENT};
    color: {ACCENT};
}}
QPushButton#feature:checked {{
    background: {ACCENT};
    color: #0b0d12;
    border: none;
}}
QPushButton#power {{
    background: {PANEL_LIGHT};
    margin: 6px;
    border-radius: 19px;
    font-weight: 700;
}}
QPushButton#power:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT2});
    color: white;
}}
QComboBox {{
    background: {PANEL_LIGHT};
    border: none;
    border-radius: 8px;
    padding: 4px 10px;
}}
QComboBox QAbstractItemView {{
    background: {PANEL_LIGHT};
    color: {TEXT};
    selection-background-color: {ACCENT_DIM};
}}
"""
