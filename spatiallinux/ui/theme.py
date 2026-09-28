"""Colours and the stylesheet.

The look: a deep, calm near-black with a trace of violet; cards a step
lighter with a hairline edge and generous rounding; text in Inter (bundled,
see tools/build_fonts.py) with the display cut for large type; controls as
pills, the chosen one white with dark text rather than coloured. The violet
accent is kept for what moves -- sliders, curves, the animations -- so it
reads as the sound, not as decoration.
"""

import glob
import os

BG = "#09080d"
PANEL = "#131119"
PANEL_LIGHT = "#1c1a25"
PANEL_LIGHTER = "#282535"
EDGE = "rgba(255, 255, 255, 0.06)"
EDGE_STRONG = "rgba(255, 255, 255, 0.11)"
GLASS = "rgba(255, 255, 255, 0.09)"
GLASS_HOVER = "rgba(255, 255, 255, 0.16)"
ACCENT = "#8b5cf6"
ACCENT2 = "#c4b5fd"
ACCENT_DIM = "#3d3070"
CHOSEN = "#f3f1fa"           # a picked button: near white, dark text
CHOSEN_TEXT = "#0c0b12"
TEXT = "#f3f2f8"
TEXT_DIM = "#9794a6"
TEXT_FAINT = "#5c5969"
DANGER = "#e0517a"
OK = "#3ee0a1"

FONT = '"Inter", "Noto Sans", sans-serif'
DISPLAY = '"Inter Display", "Inter", "Noto Sans", sans-serif'
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fonts")


def load_fonts():
    """Register the bundled Inter cuts with Qt (once, after the
    application object exists)."""
    from PyQt6.QtGui import QFontDatabase
    for path in sorted(glob.glob(os.path.join(FONT_DIR, "*.ttf"))):
        QFontDatabase.addApplicationFont(path)


STYLESHEET = f"""
QMainWindow, QWidget#root {{
    background: {BG};
}}
QWidget {{
    color: {TEXT};
    font-family: {FONT};
    font-size: 13px;
}}
QToolTip {{
    background: {PANEL_LIGHT};
    color: {TEXT};
    border: 1px solid {EDGE_STRONG};
    border-radius: 8px;
    padding: 5px 8px;
}}

/* -- header ------------------------------------------------------------- */
QLabel#heroCaption {{
    color: rgba(255, 255, 255, 0.62);
    font-size: 12px;
}}
QLabel#heroTitle {{
    font-family: {DISPLAY};
    font-size: 34px;
    font-weight: 400;
    color: white;
}}
QLabel#heroTitleItalic {{
    font-family: {DISPLAY};
    font-size: 34px;
    font-weight: 700;
    font-style: italic;
    color: white;
}}
QLabel#byline {{
    color: rgba(255, 255, 255, 0.45);
    font-size: 12px;
    padding-bottom: 6px;
}}
QLabel#byline:hover {{
    color: {ACCENT2};
}}
QLabel#version {{
    color: rgba(255, 255, 255, 0.35);
    font-size: 11px;
    padding-bottom: 7px;
}}
QFrame#chip, QFrame#glass {{
    /* the header frosts the picture behind these (see hero.py); this is
       only the tint and the rim on top */
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 255, 255, 0.10), stop:1 rgba(255, 255, 255, 0.04));
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-top-color: rgba(255, 255, 255, 0.24);
    border-radius: 17px;
}}
QLabel#chipLabel {{
    color: rgba(255, 255, 255, 0.70);
    font-size: 12px;
    font-weight: 500;
}}
QLabel#chipValue {{
    color: white;
    font-size: 12px;
    font-weight: 600;
}}
QLabel#glassLabel {{
    color: rgba(255, 255, 255, 0.72);
    font-size: 12px;
    font-weight: 500;
}}
QLabel#glassValue {{
    color: white;
    font-size: 12px;
    font-weight: 600;
}}
QFrame#glassCard {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 255, 255, 0.11), stop:1 rgba(255, 255, 255, 0.035));
    border: 1px solid rgba(255, 255, 255, 0.13);
    border-top-color: rgba(255, 255, 255, 0.26);
    border-radius: 18px;
}}
QLabel#cardCaption {{
    color: rgba(255, 255, 255, 0.82);
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
QLabel#cardDevice {{
    color: rgba(255, 255, 255, 0.45);
    font-size: 11px;
}}
QLabel#cardNote {{
    color: rgba(255, 255, 255, 0.55);
    font-size: 11px;
    padding-left: 2px;
}}
QPushButton#cardToggle {{
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 12px;
    padding: 0 12px;
    font-size: 11px;
    font-weight: 600;
    color: white;
}}
QPushButton#cardToggle:hover {{
    background: rgba(255, 255, 255, 0.16);
}}
QPushButton#cardToggle:checked {{
    background: {CHOSEN};
    color: {CHOSEN_TEXT};
    border: 1px solid white;
}}
QPushButton#choice {{
    font-size: 12px;
}}
QPushButton#tab {{
    font-size: 13px;
}}
QPushButton#powerPill {{
    font-size: 13px;
}}

/* -- cards --------------------------------------------------------------- */
QFrame#panel {{
    background: {PANEL};
    border: 1px solid {EDGE};
    border-radius: 22px;
}}
QLabel#title {{
    font-family: {DISPLAY};
    font-size: 19px;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#cardTitle {{
    font-family: {DISPLAY};
    font-size: 20px;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#subtitle {{
    color: {TEXT_DIM};
    font-size: 12px;
}}
QLabel#section {{
    color: {TEXT_DIM};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.6px;
}}
QLabel#pill {{
    background: {PANEL_LIGHT};
    border-radius: 10px;
    padding: 3px 10px;
    color: {TEXT_DIM};
    font-size: 12px;
}}

/* -- controls ------------------------------------------------------------- */
QPushButton {{
    background: {PANEL_LIGHT};
    border: 1px solid {EDGE};
    border-radius: 13px;
    padding: 6px 16px;
    color: {TEXT};
    font-weight: 500;
}}
QPushButton:hover {{
    background: {PANEL_LIGHTER};
}}
QPushButton:checked {{
    background: {CHOSEN};
    color: {CHOSEN_TEXT};
    border: 1px solid {CHOSEN};
    font-weight: 600;
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
}}
QPushButton#rowToggle {{
    padding: 3px 0;
    border-radius: 9px;
    font-size: 11px;
}}
QPushButton#smallButton {{
    padding: 4px 12px;
    border-radius: 10px;
    font-size: 12px;
}}
QPushButton#headChoice {{
    padding: 7px 0;
    border-radius: 13px;
    font-size: 12px;
}}
QSlider::groove:horizontal {{
    background: {PANEL_LIGHTER};
    height: 4px;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT2});
    border-radius: 2px;
}}
QSlider::add-page:horizontal {{
    background: {PANEL_LIGHTER};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: white;
    border: 3px solid {ACCENT};
    width: 10px;
    height: 10px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    border-color: {ACCENT2};
}}
QSlider::sub-page:horizontal:disabled {{
    background: {ACCENT_DIM};
}}
QSlider::handle:horizontal:disabled {{
    background: {TEXT_FAINT};
    border-color: {PANEL_LIGHTER};
}}
QComboBox {{
    background: {PANEL_LIGHT};
    border: 1px solid {EDGE};
    border-radius: 13px;
    padding: 5px 14px;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {PANEL_LIGHT};
    color: {TEXT};
    border: 1px solid {EDGE_STRONG};
    border-radius: 10px;
    selection-background-color: {ACCENT_DIM};
    outline: none;
}}

/* -- drop-down panels (app volumes, headphones) ----------------------------- */
/* frosted glass, painted by GlassPopup (controls.py) */
QFrame#glassPopup, QWidget#glassBody, QFrame#eqContent {{
    background: transparent;
    border: none;
}}
QFrame#glassPopup QPushButton#smallButton,
QFrame#glassPopup QFrame#eqContent QPushButton,
QFrame#glassPopup QPushButton#rowToggle {{
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
}}
QFrame#glassPopup QPushButton#smallButton:hover,
QFrame#glassPopup QFrame#eqContent QPushButton:hover,
QFrame#glassPopup QPushButton#rowToggle:hover {{
    background: rgba(255, 255, 255, 0.16);
}}
QFrame#glassPopup QPushButton#rowToggle:checked,
QFrame#glassPopup QFrame#eqContent QPushButton:checked {{
    background: {CHOSEN};
    color: {CHOSEN_TEXT};
    border: 1px solid {CHOSEN};
}}
QFrame#glassPopup QComboBox {{
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
}}
QFrame#glassPopup QPushButton#mute {{
    background: rgba(255, 255, 255, 0.08);
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
    font-size: 13px;
    font-weight: 600;
    color: {TEXT};
}}
QPushButton#mute {{
    background: {PANEL_LIGHT};
    border-radius: 10px;
    padding: 0;
}}
QPushButton#mute:checked {{
    background: {PANEL_LIGHT};
    border: 1px solid {EDGE};
}}
QPushButton#mute:hover {{
    background: {PANEL_LIGHTER};
}}

/* -- introduction ------------------------------------------------------------ */
QWidget#intro {{
    background: {BG};
}}
QLabel#introTitle {{
    font-family: {DISPLAY};
    font-size: 30px;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#introByline {{
    font-size: 13px;
    color: {ACCENT2};
}}
QLabel#introText {{
    font-size: 14px;
    color: {TEXT_DIM};
    padding: 0 60px;
}}
QLabel#introStep {{
    font-size: 14px;
    color: {TEXT};
    padding: 0 60px;
}}
QPushButton#introNext {{
    background: {CHOSEN};
    color: {CHOSEN_TEXT};
    border: none;
    font-weight: 600;
    border-radius: 18px;
    padding: 10px 26px;
}}
QPushButton#introNext:hover {{
    background: white;
}}
QPushButton#introSkip {{
    background: transparent;
    border: none;
    color: {TEXT_DIM};
}}
QPushButton#introSkip:hover {{
    color: {TEXT};
}}
QPushButton#introLang {{
    background: {PANEL_LIGHT};
    color: {TEXT_DIM};
    border-radius: 11px;
    padding: 5px 14px;
    font-size: 12px;
}}
"""
