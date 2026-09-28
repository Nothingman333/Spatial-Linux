"""Noise cancelling, on the main window: a glass card in the header that
shows up once supported headphones have been found (see sony.py).

The three modes are a sliding choice strip. Under it, one line that
changes with the mode: ambient sound's strength and Conversation, a short
note for noise cancelling, or -- when the headphones could not be reached
-- a short word and Try again. The card keeps its size whatever it shows,
so the window never jumps; it fades in when the headphones turn up.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QVariantAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QStackedLayout, QGraphicsOpacityEffect,
)

from .controls import ChoiceStrip, ChoiceButton
from .i18n import t

MODES = ("nc", "ambient", "off")


class NoiseCard(QFrame):
    """Emits what the listener picked; the window does the talking to the
    headphones and hands back their state through set_sony."""

    picked = pyqtSignal(str)          # "nc" / "ambient" / "off"
    level = pyqtSignal(int)           # ambient strength, on release
    voice = pyqtSignal(bool)          # Conversation
    retry = pyqtSignal()

    WIDTH = 372
    HEIGHT = 108

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("glassCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.glass_level = 0.0        # read by the header's frosting
        self._sony = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 11, 14, 10)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        # only the headphones' name: the three modes say what this is
        self.device = QLabel()
        self.device.setObjectName("cardCaption")
        head.addWidget(self.device, 1)
        from .headphones import Spinner
        self.spinner = Spinner()
        self.spinner.setVisible(False)
        head.addWidget(self.spinner)
        lay.addLayout(head)

        self.strip = ChoiceStrip(stretch=True, height=30)
        self.buttons = {}
        for key in MODES:
            btn = self.strip.add(ChoiceButton(t(f"sony_{key}")))
            btn.clicked.connect(lambda _c, k=key: self._pick(k))
            self.buttons[key] = btn
        lay.addWidget(self.strip)

        # the line under the modes: one page per situation
        # (made on its holder straight away: pages added to a stack with no
        # widget yet each became a window of their own for a moment, which
        # closed the drop-down it sits in)
        holder = QWidget()
        holder.setFixedHeight(24)
        self.pages = QStackedLayout(holder)
        self.page_blank = QWidget()
        self.pages.addWidget(self.page_blank)

        self.page_ambient = QWidget()
        row = QHBoxLayout(self.page_ambient)
        row.setContentsMargins(2, 0, 0, 0)
        row.setSpacing(8)
        self.level_caption = QLabel(t("sony_level"))
        self.level_caption.setObjectName("glassLabel")
        row.addWidget(self.level_caption)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 20)
        self.slider.valueChanged.connect(
            lambda v: self.level_value.setText(str(v)))
        self.slider.sliderReleased.connect(
            lambda: self.level.emit(self.slider.value()))
        row.addWidget(self.slider, 1)
        self.level_value = QLabel("20")
        self.level_value.setObjectName("glassValue")
        self.level_value.setFixedWidth(20)
        row.addWidget(self.level_value)
        self.voice_btn = QPushButton(t("sony_voice"))
        self.voice_btn.setObjectName("cardToggle")
        self.voice_btn.setCheckable(True)
        self.voice_btn.setToolTip(t("sony_voice_tip"))
        self.voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.voice_btn.setFixedHeight(24)
        self.voice_btn.clicked.connect(lambda on: self.voice.emit(on))
        row.addWidget(self.voice_btn)
        self.pages.addWidget(self.page_ambient)

        self.page_note = QLabel(t("sony_nc_note"))
        self.page_note.setObjectName("cardNote")
        self.pages.addWidget(self.page_note)

        self.page_failed = QWidget()
        row = QHBoxLayout(self.page_failed)
        row.setContentsMargins(2, 0, 0, 0)
        row.setSpacing(8)
        self.failed_label = QLabel(t("sony_failed_short"))
        self.failed_label.setObjectName("cardNote")
        self.failed_label.setToolTip(t("sony_failed"))
        row.addWidget(self.failed_label, 1)
        self.retry_btn = QPushButton(t("sony_retry"))
        self.retry_btn.setObjectName("cardToggle")
        self.retry_btn.setFixedHeight(24)
        self.retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_btn.clicked.connect(self.retry.emit)
        row.addWidget(self.retry_btn)
        self.pages.addWidget(self.page_failed)
        lay.addWidget(holder)

        # fading the card in and the line under the modes across
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)
        self._appear = QVariantAnimation(self)
        self._appear.setDuration(420)
        self._appear.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._appear.valueChanged.connect(self._on_appear)
        self._appear.finished.connect(self._appeared)
        self._page_fx = None
        self._page_anim = QVariantAnimation(self)
        self._page_anim.setDuration(240)
        self._page_anim.setStartValue(0.0)
        self._page_anim.setEndValue(1.0)
        self._page_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._page_anim.valueChanged.connect(self._on_page)
        self._page_anim.finished.connect(self._page_done)
        self.setVisible(False)

    # -- showing -------------------------------------------------------------------
    def _on_appear(self, v):
        v = float(v)
        self.glass_level = v
        if self._fx is not None:
            self._fx.setOpacity(v)
        w = self.parentWidget()
        while w is not None and not hasattr(w, "add_glass"):
            w = w.parentWidget()
        if w is not None:
            w.update()              # the header's frosting under the card

    def _appeared(self):
        if self.glass_level >= 1.0:
            self.setGraphicsEffect(None)
            self._fx = None
        else:
            self.setVisible(False)

    def _fade(self, show: bool):
        if show == (self.isVisible() and self.glass_level > 0.5):
            return
        if self._fx is None:
            self._fx = QGraphicsOpacityEffect(self)
            self._fx.setOpacity(self.glass_level)
            self.setGraphicsEffect(self._fx)
        if show:
            self.setVisible(True)
        self._appear.stop()
        self._appear.setStartValue(self.glass_level)
        self._appear.setEndValue(1.0 if show else 0.0)
        self._appear.start()

    def _show_page(self, page: QWidget):
        if self.pages.currentWidget() is page:
            return
        self.pages.setCurrentWidget(page)
        if not self.isVisible() or self.glass_level < 1.0:
            return
        self._page_fx = QGraphicsOpacityEffect(page)
        self._page_fx.setOpacity(0.0)
        page.setGraphicsEffect(self._page_fx)
        self._page_anim.stop()
        self._page_anim.start()

    def _on_page(self, v):
        if self._page_fx is not None:
            try:
                self._page_fx.setOpacity(float(v))
            except RuntimeError:
                self._page_fx = None

    def _page_done(self):
        page = self.pages.currentWidget()
        if page is not None:
            page.setGraphicsEffect(None)
        self._page_fx = None

    # -- state -----------------------------------------------------------------------
    def _pick(self, key: str):
        # the thumb moves at once; set_sony confirms (or undoes) it
        for k, btn in self.buttons.items():
            btn.setChecked(k == key)
        self.picked.emit(key)

    def retranslate(self):
        for key, btn in self.buttons.items():
            btn.setLabel(t(f"sony_{key}"))
        self.level_caption.setText(t("sony_level"))
        self.voice_btn.setText(t("sony_voice"))
        self.voice_btn.setToolTip(t("sony_voice_tip"))
        self.page_note.setText(t("sony_nc_note"))
        self.failed_label.setText(t("sony_failed_short"))
        self.failed_label.setToolTip(t("sony_failed"))
        self.retry_btn.setText(t("sony_retry"))

    def set_sony(self, sony: dict | None):
        """{name, mode, level, voice, status} of the headphones, or None
        to hide the card."""
        self._sony = sony
        if not sony:
            self._fade(False)
            return
        self.device.setText(sony.get("name") or "")
        detail = sony.get("error")
        self.failed_label.setToolTip(
            t("sony_failed") + (f"\n\n({detail})" if detail else ""))
        status = sony.get("status")
        busy = status in ("reading", "applying")
        failed = status not in (None, "reading", "applying")
        mode = sony.get("mode")
        for key, btn in self.buttons.items():
            btn.setChecked(key == mode)
        self.strip.setEnabled(not busy)
        self.spinner.setVisible(busy)
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(int(sony.get("level") or 20))
            self.slider.blockSignals(False)
            self.level_value.setText(str(self.slider.value()))
        self.voice_btn.setChecked(bool(sony.get("voice")))
        self.page_ambient.setEnabled(not busy)
        if failed:
            self._show_page(self.page_failed)
        elif mode == "ambient":
            self._show_page(self.page_ambient)
        elif mode == "nc":
            self._show_page(self.page_note)
        else:
            self._show_page(self.page_blank)
        self._fade(True)
