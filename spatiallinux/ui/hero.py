"""The header: a wide picture of light streaks -- sound drawn as a
motion-blurred spectrum -- with the name, the live status and the controls
laid over it in glass.

The picture is generated, not a bitmap: bars of light whose brightness
follows a slow waveform across the width, drawn narrow and stretched out so
they blur sideways but stay sharp top to bottom, with a bloom, a little
film grain, and shade on the left and at the bottom where text sits over
it. It is made once per size and cached; switching Spatial Linux on only
fades between a dim and a bright version of it.
"""

from __future__ import annotations

import math
import random

from PyQt6.QtCore import Qt, QRectF, QPointF, QVariantAnimation, QEasingCurve
from PyQt6.QtGui import (
    QPainter, QColor, QLinearGradient, QRadialGradient, QPainterPath, QPixmap,
    QPen, QImage,
)
from PyQt6.QtWidgets import QFrame, QPushButton, QLabel, QHBoxLayout, QWidget

from . import theme

RADIUS = 26.0

# the light's colours: violet, lavender, indigo, a little magenta and, rarely,
# a warm glint -- (r, g, b, how often)
STREAK_COLOURS = [((139, 92, 246), 10), ((196, 181, 253), 5),
                  ((99, 102, 241), 5), ((217, 70, 239), 2),
                  ((253, 186, 116), 1)]


def _pick(rnd: random.Random):
    total = sum(w for _c, w in STREAK_COLOURS)
    x = rnd.uniform(0, total)
    for colour, weight in STREAK_COLOURS:
        x -= weight
        if x <= 0:
            return colour
    return STREAK_COLOURS[0][0]


def _envelope(x: float) -> float:
    """Brightness across the width (0..1): dark behind the title on the
    left, rising into a slow, uneven waveform on the right."""
    ramp = 0.12 + 0.88 * (1.0 / (1.0 + math.exp(-(x - 0.42) * 9.0)))
    wave = (0.62 + 0.22 * math.sin(x * 11.0 + 0.6)
            + 0.16 * math.sin(x * 27.0 + 2.1))
    return max(0.0, min(1.0, ramp * wave))


def make_backdrop(width: int, height: int, ratio: float = 1.0,
                  seed: int = 7) -> QPixmap:
    """The streak picture, `width` x `height` logical pixels."""
    w, h = max(1, int(width * ratio)), max(1, int(height * ratio))

    # the streaks, drawn at a third of the width and stretched back out:
    # a sideways blur that keeps them sharp from top to bottom
    narrow = max(1, w // 3)
    img = QImage(narrow, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor("#0b0913"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    rnd = random.Random(seed)
    x = 0.0
    while x < narrow:
        bar = rnd.uniform(0.3, 2.6)
        level = _envelope(x / narrow) * (rnd.random() ** 1.5)
        r, g, b = _pick(rnd)
        grad = QLinearGradient(0, 0, 0, h)
        # each streak breaks up along its length, as light through leaves
        # or a spectrum caught mid-movement does
        stops = sorted(rnd.uniform(0.0, 1.0) for _ in range(5))
        grad.setColorAt(0.0, QColor(r, g, b, int(255 * level * 0.10)))
        for pos in stops:
            k = rnd.uniform(0.15, 1.0)
            grad.setColorAt(pos, QColor(r, g, b, int(255 * min(1.0, level * k * 0.95))))
        grad.setColorAt(1.0, QColor(r, g, b, int(255 * level * 0.04)))
        p.fillRect(QRectF(x, 0, bar, h), grad)
        x += bar * rnd.uniform(0.55, 1.3)
    # a few bright glints, short and near white, where the light is
    for _ in range(int(narrow * 0.06)):
        gx = rnd.uniform(0.35, 1.0) * narrow
        if rnd.random() > _envelope(gx / narrow):
            continue
        gy = rnd.uniform(0.05, 0.75) * h
        length = rnd.uniform(0.12, 0.45) * h
        grad = QLinearGradient(0, gy, 0, gy + length)
        tint = rnd.choice(((236, 233, 254), (221, 214, 254), (254, 215, 170)))
        grad.setColorAt(0.0, QColor(*tint, 0))
        grad.setColorAt(0.5, QColor(*tint, rnd.randint(70, 150)))
        grad.setColorAt(1.0, QColor(*tint, 0))
        p.fillRect(QRectF(gx, gy, rnd.uniform(0.3, 0.9), length), grad)
    p.end()
    img = img.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # bloom, where the waveform is strongest
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    for cx, cy, rad, colour, alpha in ((0.72, 0.40, 0.55, (167, 139, 250), 70),
                                       (0.90, 0.25, 0.35, (217, 70, 239), 34),
                                       (0.55, 0.55, 0.40, (99, 102, 241), 30)):
        g = QRadialGradient(QPointF(cx * w, cy * h), rad * w)
        g.setColorAt(0.0, QColor(*colour, alpha))
        g.setColorAt(1.0, QColor(*colour, 0))
        p.fillRect(QRectF(0, 0, w, h), g)

    # shade: behind the title on the left, and under the tabs at the bottom
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    left = QLinearGradient(0, 0, w, 0)
    left.setColorAt(0.0, QColor(8, 7, 13, 235))
    left.setColorAt(0.30, QColor(8, 7, 13, 170))
    left.setColorAt(0.58, QColor(8, 7, 13, 0))
    p.fillRect(QRectF(0, 0, w, h), left)
    bottom = QLinearGradient(0, 0, 0, h)
    bottom.setColorAt(0.55, QColor(8, 7, 13, 0))
    bottom.setColorAt(1.0, QColor(8, 7, 13, 200))
    p.fillRect(QRectF(0, 0, w, h), bottom)

    # film grain, faint
    grain = random.Random(seed + 1)
    for _ in range(int(w * h / 90)):
        v = grain.randint(0, 255)
        p.setPen(QColor(v, v, v, 10))
        p.drawPoint(grain.randrange(w), grain.randrange(h))
    p.end()

    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(ratio)
    return pm


class Hero(QFrame):
    """The header panel: the backdrop, dimmer while Spatial Linux is off."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hero")
        self._cache: QPixmap | None = None
        self._level = 0.55
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(700)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.valueChanged.connect(self._on_level)

    def set_active(self, on: bool, animate: bool = True):
        target = 1.0 if on else 0.55
        if not animate:
            self._anim.stop()
            self._on_level(target)
            return
        self._anim.stop()
        self._anim.setStartValue(self._level)
        self._anim.setEndValue(target)
        self._anim.start()

    def _on_level(self, v):
        self._level = float(v)
        self.update()

    def resizeEvent(self, ev):
        self._cache = None
        super().resizeEvent(ev)

    def paintEvent(self, ev):
        ratio = self.devicePixelRatioF() or 1.0
        if self._cache is None or self._cache.size() != self.size() * ratio:
            self._cache = make_backdrop(self.width(), self.height(), ratio)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), RADIUS, RADIUS)
        p.setClipPath(path)
        p.fillRect(self.rect(), QColor("#0b0913"))
        p.setOpacity(self._level)
        p.drawPixmap(0, 0, self._cache)
        p.setOpacity(1.0)
        # a hairline round the edge, lighter at the top, like glass
        p.setClipping(False)
        edge = QLinearGradient(0, 0, 0, self.height())
        edge.setColorAt(0.0, QColor(255, 255, 255, 38))
        edge.setColorAt(1.0, QColor(255, 255, 255, 8))
        pen = QPen(edge, 1.0)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                          RADIUS, RADIUS)
        p.end()


class Chip(QFrame):
    """A dark pill with a dot or glyph, a label and a value: live status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        # Qt drops a border-radius larger than half the height altogether,
        # so the pills get fixed heights their rounding fits
        self.setFixedHeight(26)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 12, 0)
        lay.setSpacing(7)
        self.dot = QLabel()
        self.dot.setFixedSize(7, 7)
        lay.addWidget(self.dot)
        self.label = QLabel()
        self.label.setObjectName("chipLabel")
        lay.addWidget(self.label)
        self.value = QLabel()
        self.value.setObjectName("chipValue")
        lay.addWidget(self.value)

    def set(self, label: str, value: str = "", colour: str | None = None):
        self.label.setText(label)
        self.value.setText(value)
        self.value.setVisible(bool(value))
        self.dot.setVisible(colour is not None)
        # without a dot the text starts where the dot would have
        self.layout().setContentsMargins(10 if colour else 12, 0, 12, 0)
        if colour:
            self.dot.setStyleSheet(f"background: {colour}; border-radius: 3px;")


class Glass(QFrame):
    """A frosted pill that holds a few controls (volume, pre-amp)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("glass")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedHeight(36)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(14, 0, 14, 0)
        self.row.setSpacing(10)


class ModeTab(QPushButton):
    """One of the five modes, as a tab along the bottom of the header. The
    same interface as the old feature buttons: checkable, and an "active"
    property for the one that is engaged."""

    def __init__(self, glyph: str, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("tab")
        self.setCheckable(True)
        self.setFixedHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.glyph = glyph
        self.setLabel(label)

    def setLabel(self, label: str):
        self.setText(f"{self.glyph}  {label}")


class PowerPill(QPushButton):
    """Switching Spatial Linux on and off: the one bright control in the
    header -- white while on, with a slow breathing glow; glass while off."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("powerPill")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)
        self._texts = ("", "")
        self._phase = 0.0
        from .art import FrameTimer
        self._timer = FrameTimer(self, 40, self._tick)
        self.toggled.connect(self._on_toggled)

    def setTexts(self, off: str, on: str):
        self._texts = (off, on)
        self._relabel()

    def _relabel(self):
        self.setText(self._texts[1 if self.isChecked() else 0])
        # room on the left for the drawn power symbol (see the stylesheet)
        self.setMinimumWidth(self.fontMetrics().horizontalAdvance(self.text()) + 64)

    def _on_toggled(self, on: bool):
        self._relabel()
        self._timer.want(on)
        self.update()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._timer.shown(True)

    def hideEvent(self, ev):
        self._timer.shown(False)
        super().hideEvent(ev)

    def _tick(self):
        self._phase = (self._phase + 0.018) % 1.0
        self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        colour = QColor(theme.ACCENT) if on else QColor(theme.TEXT)
        if on:
            # the power symbol's own soft glow, breathing
            pulse = 0.5 + 0.5 * math.sin(self._phase * 2 * math.pi)
            glow = QRadialGradient(QPointF(24, self.height() / 2), 14)
            glow.setColorAt(0, QColor(139, 92, 246, int(60 + 50 * pulse)))
            glow.setColorAt(1, QColor(139, 92, 246, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QPointF(24, self.height() / 2), 14, 14)
        pen = QPen(colour)
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy, r = 24.0, self.height() / 2 + 0.5, 6.5
        p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), 60 * 16, -300 * 16)
        p.drawLine(QPointF(cx, cy - r - 1.5), QPointF(cx, cy - 1))
        p.end()


def spacer(width: int) -> QWidget:
    w = QWidget()
    w.setFixedWidth(width)
    return w
