"""The header: a wide picture of light streaks -- sound drawn as a
motion-blurred spectrum -- that flows, with the name and the controls laid
over it in frosted glass.

The picture is generated, not a bitmap, and built from layers that move at
their own pace:

* far streaks: broad and dim, drifting slowly;
* near streaks: thin and bright, drifting faster -- the two together give
  the light depth as it flows past;
* glints: short sparks of near-white that fall slowly through the streaks;
* bloom: soft colour where the light is strongest, swaying a little;
* a band of light that sweeps across now and then;
* shade on the left and at the bottom, where text sits, and a faint grain.

Each layer is drawn once per size, wider than it needs to be and seamless
at its ends, and then only slid along -- so the motion costs a handful of
picture copies per frame, not a redraw. It runs only while the window is
visible and in front (see FrameTimer), faster while Spatial Linux is on.

The glass controls on top are frosted for real: the header paints a
blurred copy of the same moving layers inside each of them, before they
draw themselves.
"""

from __future__ import annotations

import math
import random

from PyQt6.QtCore import (
    Qt, QRectF, QPointF, QPoint, QVariantAnimation, QEasingCurve,
)
from PyQt6.QtGui import (
    QPainter, QColor, QLinearGradient, QRadialGradient, QPainterPath, QPixmap,
    QPen, QImage, QFontMetrics, QBrush, QTransform,
)
from PyQt6.QtWidgets import QFrame, QPushButton, QLabel, QHBoxLayout, QWidget

from . import theme
from .controls import ChoiceButton, blur

RADIUS = 26.0
BASE = QColor("#0b0913")

# the light's colours: violet, lavender, indigo, a little magenta and, rarely,
# a warm glint -- (r, g, b, how often)
STREAK_COLOURS = [((139, 92, 246), 10), ((196, 181, 253), 5),
                  ((99, 102, 241), 5), ((217, 70, 239), 2),
                  ((253, 186, 116), 1)]

# drift, in logical pixels a second, while on (while off: OFF_SPEED of it)
FAR_SPEED = 9.0
NEAR_SPEED = 24.0
GLINT_FALL = 13.0
OFF_SPEED = 0.35
FRAME_MS = 33
FROST_SCALE = 4


def _pick(rnd: random.Random):
    total = sum(w for _c, w in STREAK_COLOURS)
    x = rnd.uniform(0, total)
    for colour, weight in STREAK_COLOURS:
        x -= weight
        if x <= 0:
            return colour
    return STREAK_COLOURS[0][0]


def _envelope(x: float, phase: float) -> float:
    """Brightness along the width (0..1), repeating every 1.0 so a layer's
    two ends meet without a seam: a slow, uneven waveform."""
    wave = (0.58 + 0.24 * math.sin(2 * math.pi * 2 * x + phase)
            + 0.18 * math.sin(2 * math.pi * 5 * x + 2.1 + phase))
    return max(0.0, min(1.0, wave))


def _streaks(width: int, height: int, ratio: float, seed: int,
             squeeze: int, bars: tuple, strength: float,
             phase: float) -> QPixmap:
    """One layer of streaks, `width` logical pixels wide and seamless at its
    ends. Drawn `squeeze` times narrower and stretched back out: a sideways
    blur that keeps the streaks sharp from top to bottom."""
    w, h = max(1, int(width * ratio)), max(1, int(height * ratio))
    narrow = max(8, w // squeeze)
    pad = 6                                   # wraps round, for the stretch
    img = QImage(narrow + 2 * pad, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    rnd = random.Random(seed)
    x = 0.0
    while x < narrow:
        bar = rnd.uniform(*bars)
        level = _envelope(x / narrow, phase) * (rnd.random() ** 1.5) * strength
        r, g, b = _pick(rnd)
        grad = QLinearGradient(0, 0, 0, h)
        # each streak breaks up along its length, as light through leaves
        # or a spectrum caught mid-movement does
        stops = sorted(rnd.uniform(0.0, 1.0) for _ in range(5))
        grad.setColorAt(0.0, QColor(r, g, b, int(255 * min(1.0, level * 0.10))))
        for pos in stops:
            k = rnd.uniform(0.15, 1.0)
            grad.setColorAt(pos, QColor(r, g, b, int(255 * min(1.0, level * k * 0.95))))
        grad.setColorAt(1.0, QColor(r, g, b, int(255 * min(1.0, level * 0.04))))
        for shift in (0, narrow, -narrow):
            left = x + shift + pad
            if left + bar >= 0 and left <= narrow + 2 * pad:
                p.fillRect(QRectF(left, 0, bar, h), grad)
        x += bar * rnd.uniform(0.55, 1.3)
    p.end()
    wide = img.scaled((narrow + 2 * pad) * w // narrow, h,
                      Qt.AspectRatioMode.IgnoreAspectRatio,
                      Qt.TransformationMode.SmoothTransformation)
    cut = pad * w // narrow
    pm = QPixmap.fromImage(wide.copy(cut, 0, w, h))
    pm.setDevicePixelRatio(ratio)
    return pm


def _glints(width: int, height: int, ratio: float, seed: int) -> QPixmap:
    """Short near-white sparks, seamless top to bottom and side to side."""
    w, h = max(1, int(width * ratio)), max(1, int(height * ratio))
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    rnd = random.Random(seed)
    for _ in range(max(6, int(width * 0.05))):
        gx = rnd.uniform(0.0, 1.0) * w
        if rnd.random() > _envelope(gx / w, 0.0):
            continue
        gy = rnd.uniform(0.0, 1.0) * h
        length = rnd.uniform(0.12, 0.40) * h
        tint = rnd.choice(((236, 233, 254), (221, 214, 254), (254, 215, 170)))
        bar = rnd.uniform(0.8, 2.2) * ratio
        for dx in (0, -w, w):
            for dy in (0, -h):
                grad = QLinearGradient(0, gy + dy, 0, gy + dy + length)
                grad.setColorAt(0.0, QColor(*tint, 0))
                grad.setColorAt(0.5, QColor(*tint, rnd.randint(60, 140)))
                grad.setColorAt(1.0, QColor(*tint, 0))
                p.fillRect(QRectF(gx + dx, gy + dy, bar, length), grad)
    p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(ratio)
    return pm


def _bloom(width: int, height: int, ratio: float) -> QPixmap:
    w, h = max(1, int(width * ratio)), max(1, int(height * ratio))
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    for cx, cy, rad, colour, alpha in ((0.72, 0.40, 0.55, (167, 139, 250), 64),
                                       (0.90, 0.25, 0.35, (217, 70, 239), 32),
                                       (0.55, 0.55, 0.40, (99, 102, 241), 28)):
        g = QRadialGradient(QPointF(cx * w, cy * h), rad * w)
        g.setColorAt(0.0, QColor(*colour, alpha))
        g.setColorAt(1.0, QColor(*colour, 0))
        p.fillRect(QRectF(0, 0, w, h), g)
    p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(ratio)
    return pm


def _shade(width: int, height: int, ratio: float, seed: int) -> QPixmap:
    """Darkness behind the name on the left and under the tabs at the
    bottom, and a faint film grain."""
    w, h = max(1, int(width * ratio)), max(1, int(height * ratio))
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    left = QLinearGradient(0, 0, w, 0)
    left.setColorAt(0.0, QColor(8, 7, 13, 246))
    left.setColorAt(0.22, QColor(8, 7, 13, 214))
    left.setColorAt(0.42, QColor(8, 7, 13, 120))
    left.setColorAt(0.62, QColor(8, 7, 13, 0))
    p.fillRect(QRectF(0, 0, w, h), left)
    bottom = QLinearGradient(0, 0, 0, h)
    bottom.setColorAt(0.55, QColor(8, 7, 13, 0))
    bottom.setColorAt(1.0, QColor(8, 7, 13, 190))
    p.fillRect(QRectF(0, 0, w, h), bottom)
    grain = random.Random(seed)
    for _ in range(int(w * h / 90)):
        v = grain.randint(0, 255)
        p.setPen(QColor(v, v, v, 10))
        p.drawPoint(grain.randrange(w), grain.randrange(h))
    p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(ratio)
    return pm


def make_backdrop(width: int, height: int, ratio: float = 1.0,
                  seed: int = 7) -> QPixmap:
    """A still of the picture, `width` x `height` logical pixels (the
    README screenshot and tests; the header itself draws the layers)."""
    layers = _Layers(width, height, ratio, seed)
    pm = QPixmap(max(1, int(width * ratio)), max(1, int(height * ratio)))
    pm.setDevicePixelRatio(ratio)
    pm.fill(BASE)
    p = QPainter(pm)
    layers.paint(p, 0.0, 1.0)
    p.end()
    return pm


def _tile(p: QPainter, pm: QPixmap, x: float, y: float, w: float, h: float):
    """Draw a seamless layer shifted by (x, y), wrapping round."""
    x = -(x % w)
    y = -(y % h) if y else 0.0
    for dx in (x, x + w):
        if dx >= w:
            continue
        p.drawPixmap(QPointF(dx, y), pm)
        if y:
            p.drawPixmap(QPointF(dx, y + h), pm)


class _Layers:
    """The picture's layers for one size, and how to draw them at time t."""

    def __init__(self, width: int, height: int, ratio: float, seed: int = 7):
        self.w, self.h = width, height
        self.far = _streaks(width, height, ratio, seed, 5, (0.8, 3.2), 0.55, 0.0)
        self.near = _streaks(width, height, ratio, seed + 11, 3, (0.3, 2.2), 0.85, 1.3)
        self.glints = _glints(width, height, ratio, seed + 23)
        self.bloom = _bloom(width, height, ratio)
        self.shade = _shade(width, height, ratio, seed + 1)
        # the glass on top shows a frosted version: the same layers, small
        # and blurred, composed at a quarter of the size each frame and
        # stretched back out (the stretch blurs it further)
        k = FROST_SCALE
        self.fw, self.fh = max(1, width // k), max(1, height // k)
        self.far_s = self._small(self.far, 2)
        self.near_s = self._small(self.near, 2)
        self.bloom_s = self._small(self.bloom, 1)
        self.shade_s = self._small(self.shade, 1)
        self.frost = QImage(self.fw, self.fh, QImage.Format.Format_ARGB32_Premultiplied)

    def _small(self, pm: QPixmap, soften: int) -> QPixmap:
        img = pm.toImage().scaled(self.fw, self.fh,
                                  Qt.AspectRatioMode.IgnoreAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
        small = QPixmap.fromImage(img)
        return blur(small, soften) if soften > 1 else small

    def offsets(self, t: float):
        return (t * FAR_SPEED, t * NEAR_SPEED, t * GLINT_FALL)

    def frosted(self, t: float, level: float) -> QImage:
        """The picture at time t, small and soft, for the glass."""
        far_x, near_x, _fall = self.offsets(t)
        k = FROST_SCALE
        self.frost.fill(BASE)
        p = QPainter(self.frost)
        p.setOpacity(level)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        _tile(p, self.far_s, far_x / k, 0, self.fw, self.fh)
        _tile(p, self.near_s, near_x / k, 0, self.fw, self.fh)
        p.setOpacity(level * (0.85 + 0.15 * math.sin(t * 0.45)))
        p.drawPixmap(QPointF(18.0 * math.sin(t * 0.21) / k,
                             6.0 * math.sin(t * 0.33) / k), self.bloom_s)
        p.setOpacity(1.0)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.drawPixmap(0, 0, self.shade_s)
        p.end()
        return self.frost

    def paint(self, p: QPainter, t: float, level: float):
        far_x, near_x, fall = self.offsets(t)
        w, h = self.w, self.h
        p.save()
        # placed to a fraction of a pixel: snapped to whole pixels, a slow
        # drift moves in visible one-pixel hops
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setOpacity(level)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        _tile(p, self.far, far_x, 0, w, h)
        _tile(p, self.near, near_x, 0, w, h)
        p.setOpacity(level * (0.75 + 0.25 * math.sin(t * 0.9)))
        _tile(p, self.glints, near_x, -fall, w, h)
        # the bloom sways, breathing a little
        p.setOpacity(level * (0.85 + 0.15 * math.sin(t * 0.45)))
        p.drawPixmap(QPointF(18.0 * math.sin(t * 0.21), 6.0 * math.sin(t * 0.33)),
                     self.bloom)
        # now and then a broad band of light sweeps across
        sweep = (t / 9.0) % 1.0
        if sweep < 0.55:
            x = w * (1.25 - 1.6 * sweep / 0.55)
            band = QLinearGradient(x - w * 0.18, 0, x + w * 0.18, 0)
            strength = math.sin(math.pi * sweep / 0.55)
            band.setColorAt(0.0, QColor(167, 139, 250, 0))
            band.setColorAt(0.5, QColor(196, 181, 253, int(26 * strength)))
            band.setColorAt(1.0, QColor(167, 139, 250, 0))
            p.setOpacity(level)
            p.fillRect(QRectF(0, 0, w, h), band)
        p.setOpacity(1.0)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.drawPixmap(0, 0, self.shade)
        p.restore()


class Hero(QFrame):
    """The header panel: the flowing picture, dimmer and slower while
    Spatial Linux is off, and frosted glass under the controls on it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hero")
        self._layers: _Layers | None = None
        self._level = 0.55
        self._t = 0.0
        self._speed = OFF_SPEED
        self._target_speed = OFF_SPEED
        self._glass: list[tuple[QWidget, float]] = []
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(700)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.valueChanged.connect(self._on_level)
        from .art import FrameTimer
        self._timer = FrameTimer(self, FRAME_MS, self._tick)
        self._timer.want(True)

    def add_glass(self, widget: QWidget, radius: float | None = None):
        """Frost the picture behind `widget` (a rounded rect of `radius`,
        or fully round ends when None)."""
        self._glass.append((widget, radius))

    def set_active(self, on: bool, animate: bool = True):
        target = 1.0 if on else 0.55
        self._target_speed = 1.0 if on else OFF_SPEED
        if not animate:
            self._anim.stop()
            self._speed = self._target_speed
            self._on_level(target)
            return
        self._anim.stop()
        self._anim.setStartValue(self._level)
        self._anim.setEndValue(target)
        self._anim.start()

    def _on_level(self, v):
        self._level = float(v)
        self.update()

    def _tick(self):
        # speed eases toward its target, so switching on the light gathers
        # pace rather than jumping
        dt = self._timer.elapsed()
        self._speed += (self._target_speed - self._speed) * min(1.0, dt * 1.2)
        self._t += dt * self._speed
        self.update()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._timer.shown(True)

    def hideEvent(self, ev):
        self._timer.shown(False)
        super().hideEvent(ev)

    def resizeEvent(self, ev):
        self._layers = None
        super().resizeEvent(ev)

    def paintEvent(self, ev):
        ratio = self.devicePixelRatioF() or 1.0
        if (self._layers is None or self._layers.w != self.width()
                or self._layers.h != self.height()):
            self._layers = _Layers(self.width(), self.height(), ratio)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), BASE)
        self._layers.paint(p, self._t, self._level)

        # frosted glass: the same light, blurred, under each glass control
        frost = QBrush(self._layers.frosted(self._t, self._level))
        frost.setTransform(QTransform.fromScale(FROST_SCALE, FROST_SCALE))
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setPen(Qt.PenStyle.NoPen)
        for widget, radius in self._glass:
            if not widget.isVisible():
                continue
            level = getattr(widget, "glass_level", 1.0)
            if level <= 0.0:
                continue
            top_left = widget.mapTo(self, QPoint(0, 0))
            r = QRectF(top_left.x(), top_left.y(), widget.width(), widget.height())
            rad = r.height() / 2 if radius is None else radius
            p.setOpacity(level)
            p.setBrush(frost)
            p.drawRoundedRect(r, rad, rad)
        p.setOpacity(1.0)

        # the rounded corners: cut out by painting the window's own
        # background over them (cheaper than clipping every frame)
        outside = QPainterPath()
        outside.addRect(QRectF(self.rect()))
        inside = QPainterPath()
        inside.addRoundedRect(QRectF(self.rect()), RADIUS, RADIUS)
        p.setBrush(QColor(theme.BG))
        p.drawPath(outside.subtracted(inside))

        # a hairline round the edge, lighter at the top, like glass
        p.setClipping(False)
        edge = QLinearGradient(0, 0, 0, self.height())
        edge.setColorAt(0.0, QColor(255, 255, 255, 40))
        edge.setColorAt(1.0, QColor(255, 255, 255, 8))
        p.setPen(QPen(edge, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                          RADIUS, RADIUS)
        p.end()


class Chip(QFrame):
    """A glass pill with a dot or glyph, a label and a value."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        # Qt drops a border-radius larger than half the height altogether,
        # so the pills get fixed heights their rounding fits
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 16, 0)
        lay.setSpacing(8)
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
        if colour:
            self.set_dot(colour)

    def set_dot(self, colour: str):
        """The dot's colour: green while Spatial Linux is on."""
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


class ModeTab(ChoiceButton):
    """One of the five modes, as a tab along the bottom of the header: a
    glass pill of its own, with the white thumb sliding to the one that is
    engaged (see ChoiceStrip)."""

    def __init__(self, glyph: str, label: str, parent=None):
        super().__init__(label, glyph, parent)
        self.setObjectName("tab")

    def sizeHint(self):
        size = super().sizeHint()
        return size.expandedTo(size.__class__(size.width() + 6, 32))


class PowerPill(QPushButton):
    """Switching Spatial Linux on and off: the one bright control in the
    header. Switching on, white floods out from the power symbol across the
    pill; off, it drains back into it. While on, the symbol breathes a soft
    violet glow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("powerPill")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFixedHeight(40)
        self._texts = ("", "")
        self._phase = 0.0
        self._fill = 0.0
        self._hover = 0.0
        from .art import FrameTimer
        self._timer = FrameTimer(self, 33, self._tick)
        self._flood = QVariantAnimation(self)
        self._flood.setDuration(520)
        self._flood.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._flood.valueChanged.connect(self._on_fill)
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(180)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)
        self.toggled.connect(self._on_toggled)

    def setTexts(self, off: str, on: str):
        self._texts = (off, on)
        self._relabel()

    def _font(self):
        f = self.font()
        f.setWeight(f.Weight.DemiBold)
        return f

    def _relabel(self):
        self.setText(self._texts[1 if self.isChecked() else 0])
        widest = max(QFontMetrics(self._font()).horizontalAdvance(s)
                     for s in self._texts + (self.text(),))
        # room on the left for the drawn power symbol
        self.setMinimumWidth(widest + 64)

    def _on_toggled(self, on: bool):
        self._relabel()
        self._timer.want(on)
        self._flood.stop()
        if self.isVisible():
            self._flood.setStartValue(self._fill)
            self._flood.setEndValue(1.0 if on else 0.0)
            self._flood.start()
        else:
            self._on_fill(1.0 if on else 0.0)

    def _on_fill(self, v):
        self._fill = float(v)
        self.update()

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def enterEvent(self, ev):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(ev)

    def showEvent(self, ev):
        super().showEvent(ev)
        self._timer.shown(True)

    def hideEvent(self, ev):
        self._timer.shown(False)
        super().hideEvent(ev)

    def _tick(self):
        self._phase = (self._phase + self._timer.elapsed() * 0.45) % 1.0
        self.update()

    def _content(self, p: QPainter, text: QColor, icon: QColor):
        p.setPen(text)
        p.setFont(self._font())
        p.drawText(QRectF(40, 0, self.width() - 52, self.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self.text())
        pen = QPen(icon)
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy, r = 24.0, self.height() / 2 + 0.5, 6.5
        p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), 60 * 16, -300 * 16)
        p.drawLine(QPointF(cx, cy - r - 1.5), QPointF(cx, cy - 1))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = r.height() / 2
        pill = QPainterPath()
        pill.addRoundedRect(r, rad, rad)
        h = self._hover
        # glass while off
        fill = QLinearGradient(r.topLeft(), r.bottomLeft())
        fill.setColorAt(0.0, QColor(255, 255, 255, int(36 + 26 * h)))
        fill.setColorAt(1.0, QColor(255, 255, 255, int(12 + 16 * h)))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawPath(pill)

        # white, flooding out from the symbol
        centre = QPointF(24.0, self.height() / 2)
        reach = math.hypot(self.width(), self.height()) * self._fill
        flood = QPainterPath()
        flood.addEllipse(centre, reach, reach)
        lit = pill.intersected(flood)
        if self._fill > 0.0:
            body = QLinearGradient(r.topLeft(), r.bottomLeft())
            body.setColorAt(0.0, QColor("#ffffff"))
            body.setColorAt(1.0, QColor("#e6e2f3"))
            p.setBrush(body)
            p.drawPath(lit)

        rim = QLinearGradient(r.topLeft(), r.bottomLeft())
        rim.setColorAt(0.0, QColor(255, 255, 255, int(90 + 60 * h)))
        rim.setColorAt(1.0, QColor(255, 255, 255, int(30 + 30 * h)))
        p.setPen(QPen(rim, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(pill)

        if self._fill > 0.5:
            # the symbol's own soft glow, breathing
            pulse = 0.5 + 0.5 * math.sin(self._phase * 2 * math.pi)
            glow = QRadialGradient(centre, 15)
            k = (self._fill - 0.5) * 2
            glow.setColorAt(0, QColor(139, 92, 246, int((60 + 50 * pulse) * k)))
            glow.setColorAt(1, QColor(139, 92, 246, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(centre, 15, 15)

        # text and symbol: light over the glass, dark over the white
        p.save()
        p.setClipPath(pill.subtracted(flood) if self._fill > 0 else pill)
        self._content(p, QColor(theme.TEXT), QColor(theme.TEXT))
        p.restore()
        if self._fill > 0.0:
            p.save()
            p.setClipPath(lit)
            self._content(p, QColor(theme.CHOSEN_TEXT), QColor(theme.ACCENT))
            p.restore()
        p.end()


def spacer(width: int) -> QWidget:
    w = QWidget()
    w.setFixedWidth(width)
    return w
