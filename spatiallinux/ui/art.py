"""Animated illustrations, one per mode.

Each is a vector scene drawn with QPainter and driven by a shared phase
clock, in a neon key: luminous strokes over near-black, figures rendered as
translucent light rather than flat shapes. They stop their timer when hidden,
so an idle window costs nothing.
"""

import math

from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QPainterPath, QRadialGradient, QLinearGradient,
    QFont,
)
from PyQt6.QtWidgets import QWidget, QLabel

from . import theme
from . import i18n
from .i18n import t as tr

# These are ambient scenes, not gameplay, and every frame costs several wide
# translucent strokes, which are expensive to rasterise on the CPU. Slow
# scenes run slower still; nothing here reads as choppy at 20 fps.
FRAME_MS = 33          # ~30 fps, the default


def _ease(t: float) -> float:
    """smoothstep, for motion that starts and stops gently"""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _accent(alpha: int, second: bool = False) -> QColor:
    c = QColor(theme.ACCENT2 if second else theme.ACCENT)
    c.setAlpha(max(0, min(255, alpha)))
    return c


# --- neon helpers ----------------------------------------------------------
#
# Qt has no bloom filter, so glow is faked the way it is in vector art: draw
# the same shape several times, each pass wider and fainter, then lay the
# crisp stroke on top.

GLOW_PASSES = 2


def _glow_pen(colour: QColor, width: float, pass_i: int, passes: int) -> QPen:
    c = QColor(colour)
    c.setAlpha(int(colour.alpha() * 0.20 * (passes - pass_i) / passes))
    pen = QPen(c)
    pen.setWidthF(width + 3.2 * (pass_i + 1))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def _glow_ellipse(p: QPainter, rect: QRectF, colour: QColor, width=1.4,
                  passes=GLOW_PASSES):
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    for i in range(passes):
        p.setPen(_glow_pen(colour, width, i, passes))
        p.drawEllipse(rect)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(colour)
    pen.setWidthF(width)
    p.setPen(pen)
    p.drawEllipse(rect)


def _glow_path(p: QPainter, path: QPainterPath, colour: QColor, width=1.6,
               passes=GLOW_PASSES):
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    for i in range(passes):
        p.setPen(_glow_pen(colour, width, i, passes))
        p.drawPath(path)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(colour)
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawPath(path)


def _halo(p: QPainter, cx: float, cy: float, r: float, colour: QColor,
          inner: float = 0.0):
    """A soft radial bloom -- what makes a stroke read as light."""
    if r <= 0:
        return
    grad = QRadialGradient(cx, cy, r)
    grad.setColorAt(inner, QColor(colour))
    mid = QColor(colour)
    mid.setAlpha(int(colour.alpha() * 0.35))
    grad.setColorAt(min(0.999, inner + (1 - inner) * 0.45), mid)
    edge = QColor(colour)
    edge.setAlpha(0)
    grad.setColorAt(1.0, edge)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))


def _node(p: QPainter, cx: float, cy: float, r: float, colour: QColor,
          glow: bool = True):
    """A glowing point of light."""
    if glow:
        soft = QColor(colour)
        soft.setAlpha(int(colour.alpha() * 0.45))
        _halo(p, cx, cy, r * 2.8, soft)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(colour)
    p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
    p.setBrush(QColor(255, 255, 255, colour.alpha()))
    p.drawEllipse(QRectF(cx - r * 0.42, cy - r * 0.42, r * 0.84, r * 0.84))


def _luminous_body(p: QPainter, path: QPainterPath, rect: QRectF,
                   strength: float):
    """Fill a silhouette as translucent light with a bright edge, rather
    than as a flat block of colour."""
    grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
    a = QColor(theme.ACCENT)
    a.setAlpha(int(70 * strength) + 20)
    b = QColor(theme.ACCENT2)
    b.setAlpha(int(110 * strength) + 25)
    grad.setColorAt(0.0, a)
    grad.setColorAt(1.0, b)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawPath(path)
    _glow_path(p, path, _accent(int(150 * strength) + 50, True), 1.3, 2)


class AnimatedArt(QWidget):
    """Base: a phase that advances while visible, and an eased `amount`."""

    PERIOD_S = 6.0        # seconds for one full cycle

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._amount = 0.0
        self._shown = 0.0
        self.setMinimumHeight(150)
        self._timer = QTimer(self)
        self._timer.setInterval(getattr(self, "FRAME_MS", FRAME_MS))
        self._timer.timeout.connect(self._tick)

    def setAmount(self, amount: float):
        self._amount = max(0.0, min(1.0, amount))
        if self.isVisible() and not self._timer.isActive():
            self._timer.start()
        self.update()

    def showEvent(self, ev):
        self._timer.start()

    def hideEvent(self, ev):
        self._timer.stop()

    def _tick(self):
        step = getattr(self, "FRAME_MS", FRAME_MS) / 1000.0
        self._phase = (self._phase + step / self.PERIOD_S) % 1.0
        self._shown += (self._amount - self._shown) * 0.10
        if abs(self._amount - self._shown) < 0.002:
            self._shown = self._amount
        self.update()

    def _caption(self, p: QPainter, text: str, alpha: int = 150):
        p.setPen(_accent(alpha))
        p.setFont(QFont("Noto Sans", 8))
        p.drawText(QRectF(0, self.height() - 20, self.width(), 16),
                   Qt.AlignmentFlag.AlignHCenter, text)


class SphereArt(AnimatedArt):
    """3D Surround: flat rings inflate into a lit orb wrapped in orbits,
    then settle back."""

    PERIOD_S = 9.0
    FRAME_MS = 50
    WAVES = 3
    LABELS = [
        ("spk_front_l", 0.20, 0.13), ("spk_front_r", 0.80, 0.13),
        ("spk_side_l", 0.07, 0.50), ("spk_side_r", 0.93, 0.50),
        ("spk_rear_l", 0.22, 0.87), ("spk_rear_r", 0.78, 0.87),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels = []
        # the panel is rebuilt on a language switch, so translating here
        # is enough to keep these in step with the rest of the interface
        for key, fx, fy in self.LABELS:
            lbl = QLabel(tr(key), self)
            lbl.setObjectName("pill")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._labels.append((lbl, fx, fy))

    def resizeEvent(self, ev):
        self._place_labels()

    def _place_labels(self):
        w, h = self.width(), self.height()
        spread = 0.80 + 0.20 * self._shown
        for lbl, fx, fy in self._labels:
            lbl.adjustSize()
            cx = 0.5 + (fx - 0.5) * spread
            cy = 0.5 + (fy - 0.5) * spread
            lbl.move(int(cx * w - lbl.width() / 2),
                     int(cy * h - lbl.height() / 2))

    def _tick(self):
        super()._tick()
        self._place_labels()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        r = min(self.width(), self.height()) / 2 - 18
        if r <= 0:
            return

        tri = 1.0 - abs(self._phase * 2.0 - 1.0)
        depth = _ease(tri) * (0.3 + 0.7 * self._shown)
        spin = self._phase * 2 * math.pi
        lit = 0.35 + 0.65 * self._shown

        _halo(p, cx, cy, r * 1.15, _accent(int(30 * lit), True))

        # waves rolling out across the floor
        for i in range(self.WAVES):
            t = (self._phase * 3 + i / self.WAVES) % 1.0
            rr = r * t
            if rr < 4:
                continue
            fade = (1.0 - t) ** 1.6
            squash = 1.0 - 0.72 * depth
            _glow_ellipse(p, QRectF(cx - rr, cy - rr * squash,
                                    rr * 2, rr * 2 * squash),
                          _accent(int(150 * fade * lit), i % 2 == 1),
                          1.0 + 1.2 * fade, 1)

        # the shell
        _glow_ellipse(p, QRectF(cx - r, cy - r, r * 2, r * 2),
                      _accent(int(70 + 120 * depth)), 1.5)

        # latitudes
        for i in (-2, -1, 0, 1, 2):
            frac = i / 2.7
            lat_r = r * math.sqrt(max(0.0, 1.0 - frac * frac))
            y = cy + r * frac * depth
            squash = max(0.04, 1.0 - 0.80 * depth)
            rad = lat_r if depth > 0.03 else r * (0.34 + 0.33 * abs(i) / 2)
            pen = QPen(_accent(int(38 + 80 * depth)))
            pen.setWidthF(1.1)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - rad, y - rad * squash,
                                 rad * 2, rad * 2 * squash))

        # orbits, tilting as they turn -- the part that sells the volume
        if depth > 0.04:
            for k in range(2):
                a = spin * (1.0 + 0.26 * k) + k * 2.1
                ow = abs(math.cos(a)) * r * 1.02 + r * 0.05
                oh = r * (1.0 - 0.06 * k)
                _glow_ellipse(p, QRectF(cx - ow, cy - oh, ow * 2, oh * 2),
                              _accent(int(105 * depth), k % 2 == 0), 1.2, 1)
                nx = cx + ow * math.cos(a * 1.7)
                ny = cy + oh * math.sin(a * 1.7) * 0.42
                _node(p, nx, ny, 2.6 + 1.2 * depth,
                      _accent(int(220 * depth), True), glow=False)

        # poles light up as the orb forms
        for sign in (-1, 1):
            _node(p, cx, cy + sign * r * depth * 0.98,
                  2.4 + 1.6 * depth, _accent(int(200 * depth)), glow=False)

        # core
        _halo(p, cx, cy, r * 0.42, _accent(int(120 * lit), True), inner=0.12)
        _node(p, cx, cy, 5.5 + 2.0 * math.sin(self._phase * 6 * math.pi),
              _accent(240, True))

        self._caption(p, tr("cap_depth") if depth > 0.5
                      else tr("cap_widening"),
                      int(90 + 60 * self._shown))


def _headphones(p: QPainter, cx: float, cy: float, head_r: float,
                colour: QColor):
    rect = QRectF(cx - head_r * 1.18, cy - head_r * 1.30,
                  head_r * 2.36, head_r * 2.05)
    band = QPainterPath()
    band.arcMoveTo(rect, 18)
    band.arcTo(rect, 18, 144)
    _glow_path(p, band, colour, max(2.2, head_r * 0.12))

    cup_w, cup_h = head_r * 0.36, head_r * 0.66
    for side in (-1, 1):
        cr = QRectF(cx + side * head_r * 1.18 - cup_w / 2, cy - cup_h / 2,
                    cup_w, cup_h)
        cup = QPainterPath()
        cup.addRoundedRect(cr, cup_w / 2, cup_w / 2)
        soft = QColor(colour)
        soft.setAlpha(70)
        _halo(p, cr.center().x(), cr.center().y(), cup_w * 2.2, soft)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        p.drawPath(cup)


def _figure(cx: float, cy: float, head_r: float, top_y: float) -> QPainterPath:
    """Neck and shoulders meeting the head, so it reads as a person."""
    path = QPainterPath()
    neck = head_r * 0.34
    path.moveTo(cx - neck, cy + head_r * 0.94)
    path.lineTo(cx - neck, top_y - head_r * 0.08)
    path.cubicTo(cx - head_r * 0.95, top_y,
                 cx - head_r * 1.38, top_y + head_r * 0.32,
                 cx - head_r * 1.60, top_y + head_r * 1.35)
    path.lineTo(cx + head_r * 1.60, top_y + head_r * 1.35)
    path.cubicTo(cx + head_r * 1.38, top_y + head_r * 0.32,
                 cx + head_r * 0.95, top_y,
                 cx + neck, top_y - head_r * 0.08)
    path.lineTo(cx + neck, cy + head_r * 0.94)
    path.closeSubpath()
    return path


class BassHeadArt(AnimatedArt):
    """Bass Boost: someone in headphones nodding along, the room answering
    on every downbeat."""

    PERIOD_S = 2.2

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h * 0.44
        head_r = min(w, h) * 0.155
        if head_r <= 0:
            return

        lit = 0.3 + 0.7 * self._shown
        beat = math.sin(self._phase * 2 * math.pi)
        lean = beat * 11.0 * (0.25 + 0.75 * self._shown)
        hit = max(0.0, -math.cos(self._phase * 4 * math.pi))
        pulse = hit ** 2.2 * self._shown

        _halo(p, cx, cy, head_r * 2.8, _accent(int(26 * lit), True))

        # rings blooming from each ear cup
        for side in (-1, 1):
            ex = cx + side * head_r * 1.18
            for i in range(3):
                t = (self._phase * 2 + i / 3.0) % 1.0
                rr = head_r * (0.45 + 2.7 * t)
                fade = (1.0 - t) ** 1.8 * (0.35 + 0.65 * pulse)
                rect = QRectF(ex - rr, cy - rr * 0.82, rr * 2, rr * 1.64)
                arc = QPainterPath()
                arc.arcMoveTo(rect, 90 if side < 0 else -90)
                arc.arcTo(rect, 90 if side < 0 else -90, 180)
                _glow_path(p, arc, _accent(int(165 * fade * lit), i % 2 == 1),
                           1.0 + 1.6 * fade, 2)

        # the floor thumps with the beat
        gw = head_r * (3.2 + 1.5 * pulse)
        fy = cy + head_r * 2.4
        grad = QRadialGradient(cx, fy, max(1.0, gw))
        c = _accent(int(95 * pulse), True)
        grad.setColorAt(0.0, c)
        fade_c = QColor(c)
        fade_c.setAlpha(0)
        grad.setColorAt(1.0, fade_c)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(QRectF(cx - gw, fy - gw * 0.16, gw * 2, gw * 0.32))

        body = _figure(cx, cy, head_r, cy + head_r * 1.42)
        _luminous_body(p, body, QRectF(cx - head_r * 1.7, cy,
                                       head_r * 3.4, head_r * 2.8), lit)

        p.save()
        p.translate(cx, cy + head_r * 0.9)
        p.rotate(lean)
        p.translate(-cx, -(cy + head_r * 0.9))

        head = QPainterPath()
        head.addEllipse(QRectF(cx - head_r, cy - head_r,
                               head_r * 2, head_r * 2))
        _luminous_body(p, head, QRectF(cx - head_r, cy - head_r,
                                       head_r * 2, head_r * 2), lit)
        _headphones(p, cx, cy, head_r, _accent(int(120 + 110 * lit)))
        p.restore()

        self._caption(p, tr("cap_bass"),
                      int(80 + 70 * self._shown))


class LipsArt(AnimatedArt):
    """Fidelity: lips shaping a line, every syllable lifting away as light
    and leaving a clean waveform behind -- the detail this mode restores."""

    PERIOD_S = 3.6
    # uneven, so it reads as singing rather than a machine opening and closing
    SYLLABLES = [(0.02, 0.10, 0.95), (0.16, 0.07, 0.55), (0.27, 0.12, 1.0),
                 (0.44, 0.06, 0.45), (0.53, 0.14, 0.85), (0.72, 0.09, 0.65),
                 (0.85, 0.08, 0.9)]
    # the line being sung, a word at a time, in the interface language
    LYRICS = {"en": ["every", "note", "rings", "out", "in", "place"],
              "tr": ["her", "nota", "yerli", "yerinde", "duyul", "sun"]}

    def _openness(self) -> float:
        total = 0.0
        for start, length, strength in self.SYLLABLES:
            t = (self._phase - start) % 1.0
            if t < length:
                total = max(total, strength * math.sin(math.pi * t / length))
        return total

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h * 0.58
        lw = min(w * 0.20, h * 0.46)
        if lw <= 0:
            return

        lit = 0.3 + 0.7 * self._shown
        open_amt = self._openness() * (0.3 + 0.7 * self._shown)
        gap = lw * 0.52 * open_amt

        _halo(p, cx, cy, lw * 2.0, _accent(int(28 * lit), True))

        # the words being sung, rising and fading
        p.setFont(QFont("Noto Sans", 9, QFont.Weight.DemiBold))
        lyrics = self.LYRICS.get(i18n.language(), self.LYRICS["en"])
        for i, word in enumerate(lyrics):
            t = (self._phase + i / len(lyrics)) % 1.0
            side = 1 if i % 2 else -1
            wx = cx + side * lw * (0.45 + 0.95 * t)
            wy = cy - lw * 0.80 - t * (cy - lw * 0.80 - 18)
            fade = math.sin(math.pi * min(1.0, t * 1.15)) ** 1.2 * self._shown
            p.setPen(_accent(int(190 * fade), i % 2 == 0))
            p.drawText(QRectF(wx - 50, wy - 10, 100, 20),
                       Qt.AlignmentFlag.AlignCenter, word)

        # a clean waveform leaving the mouth
        for side in (-1, 1):
            wave = QPainterPath()
            x0 = cx + side * lw * 1.15
            wave.moveTo(x0, cy)
            for k in range(1, 91):
                u = k / 90.0
                fx = x0 + side * u * lw * 2.6
                amp = lw * 0.17 * open_amt * (1.0 - u) ** 1.2
                wave.lineTo(fx, cy + amp * math.sin(u * 13.0 - self._phase * 9))
            _glow_path(p, wave, _accent(int(130 * lit), True), 1.3, 2)

        # the dark of the mouth sits behind the lips
        if gap > 1:
            inner = QPainterPath()
            inner.moveTo(cx - lw * 0.86, cy)
            inner.cubicTo(cx - lw * 0.4, cy - gap * 0.75,
                          cx + lw * 0.4, cy - gap * 0.75, cx + lw * 0.86, cy)
            inner.cubicTo(cx + lw * 0.4, cy + gap * 0.95,
                          cx - lw * 0.4, cy + gap * 0.95, cx - lw * 0.86, cy)
            inner.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(4, 3, 10))
            p.drawPath(inner)

        upper = QPainterPath()
        upper.moveTo(cx - lw, cy)
        upper.cubicTo(cx - lw * 0.55, cy - lw * 0.46 - gap * 0.5,
                      cx - lw * 0.16, cy - lw * 0.20 - gap * 0.5,
                      cx, cy - gap * 0.28)
        upper.cubicTo(cx + lw * 0.16, cy - lw * 0.20 - gap * 0.5,
                      cx + lw * 0.55, cy - lw * 0.46 - gap * 0.5, cx + lw, cy)
        upper.cubicTo(cx + lw * 0.5, cy - lw * 0.10,
                      cx - lw * 0.5, cy - lw * 0.10, cx - lw, cy)
        upper.closeSubpath()

        lower = QPainterPath()
        lower.moveTo(cx - lw, cy)
        lower.cubicTo(cx - lw * 0.5, cy + lw * 0.10 + gap * 0.2,
                      cx + lw * 0.5, cy + lw * 0.10 + gap * 0.2, cx + lw, cy)
        lower.cubicTo(cx + lw * 0.52, cy + lw * 0.46 + gap,
                      cx - lw * 0.52, cy + lw * 0.46 + gap, cx - lw, cy)
        lower.closeSubpath()

        rect = QRectF(cx - lw, cy - lw, lw * 2, lw * 2)
        for path, shade in ((upper, 132), (lower, 104)):
            grad = QLinearGradient(rect.left(), rect.top(),
                                   rect.right(), rect.bottom())
            a = QColor(theme.ACCENT)
            a.setAlpha(int(150 * lit) + 40)
            b = QColor(theme.ACCENT2).darker(shade)
            b.setAlpha(int(200 * lit) + 45)
            grad.setColorAt(0.0, a)
            grad.setColorAt(1.0, b)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(grad)
            p.drawPath(path)
        _glow_path(p, upper, _accent(int(150 * lit), True), 1.2, 2)
        _glow_path(p, lower, _accent(int(150 * lit), True), 1.2, 2)

        self._caption(p, tr("cap_fidelity"),
                      int(80 + 70 * self._shown))


class NightBreathArt(AnimatedArt):
    """Night Mode: someone settling -- a long exhale, shoulders letting go."""

    PERIOD_S = 7.5
    FRAME_MS = 50
    BULLET_GLYPHS = ("☾", "≋", "✿")
    BULLET_KEYS = ("night_relax", "night_soft", "night_sleep")

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w * 0.58, h * 0.46
        head_r = min(w, h) * 0.145
        if head_r <= 0:
            return

        lit = 0.3 + 0.7 * self._shown
        t = self._phase
        breath = _ease(t / 0.35) if t < 0.35 else 1.0 - _ease((t - 0.35) / 0.65)
        drop = (1.0 - breath) * head_r * 0.30 * (0.3 + 0.7 * self._shown)
        rise = breath * head_r * 0.16

        _halo(p, cx, cy, head_r * 2.8, _accent(int(24 * lit), True))

        # moon and stars
        mx, my = w * 0.88, h * 0.16
        _halo(p, mx, my, 34, _accent(int(60 * lit), True))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_accent(int(150 + 60 * lit), True))
        p.drawEllipse(QRectF(mx - 14, my - 14, 28, 28))
        p.setBrush(QColor(theme.PANEL))
        p.drawEllipse(QRectF(mx - 8, my - 17, 25, 25))
        for i, (sx, sy) in enumerate(((0.12, 0.14), (0.22, 0.30),
                                      (0.74, 0.10), (0.44, 0.08))):
            tw = 0.5 + 0.5 * math.sin(self._phase * 4 * math.pi + i * 2.0)
            _node(p, w * sx, h * sy, 1.6, _accent(int(150 * tw * lit)),
                  glow=False)

        # the exhale drifting away
        if t >= 0.35:
            e = (t - 0.35) / 0.65
            for i in range(3):
                et = (e + i * 0.16) % 1.0
                if et > 0.92:
                    continue
                ex = cx + head_r * (0.95 + 1.6 * et)
                ey = cy - head_r * 0.20 - et * head_r * 0.70
                rad = head_r * (0.16 + 0.40 * et)
                _halo(p, ex, ey, rad * 2.0,
                      _accent(int(165 * (1 - et) ** 1.2 * self._shown), True))

        body = _figure(cx, cy, head_r, cy + head_r * 1.34 + drop)
        _luminous_body(p, body, QRectF(cx - head_r * 1.7, cy,
                                       head_r * 3.4, head_r * 2.8), lit)

        p.save()
        p.translate(0, drop * 0.7 - rise * 0.25)
        head = QPainterPath()
        head.addEllipse(QRectF(cx - head_r, cy - head_r,
                               head_r * 2, head_r * 2))
        _luminous_body(p, head, QRectF(cx - head_r, cy - head_r,
                                       head_r * 2, head_r * 2), lit)
        _headphones(p, cx, cy, head_r, _accent(int(120 + 110 * lit)))

        for side in (-1, 1):
            rect = QRectF(cx + side * head_r * 0.40 - head_r * 0.20,
                          cy - head_r * 0.12, head_r * 0.40, head_r * 0.26)
            eye = QPainterPath()
            eye.arcMoveTo(rect, 0)
            eye.arcTo(rect, 0, -180)
            _glow_path(p, eye, _accent(int(200 * lit)),
                       max(1.6, head_r * 0.07), 1)
        p.restore()

        # what the mode is for, and the breath itself
        p.setFont(QFont("Noto Sans", 9))
        for i, (glyph, key) in enumerate(zip(self.BULLET_GLYPHS,
                                             self.BULLET_KEYS)):
            y = h * 0.30 + i * 26
            p.setPen(_accent(int(170 * lit), True))
            p.drawText(QRectF(14, y - 10, 24, 20),
                       Qt.AlignmentFlag.AlignCenter, glyph)
            p.setPen(QColor(theme.TEXT_DIM))
            p.drawText(QRectF(42, y - 10, 160, 20),
                       Qt.AlignmentFlag.AlignVCenter, tr(key))

        p.setFont(QFont("Noto Sans", 10))
        phrase = tr("breathe_in") if t < 0.35 else tr("breathe_out")
        p.setPen(_accent(int((110 + 110 * abs(breath - 0.5) * 2) * self._shown)))
        p.drawText(QRectF(w - 180, h * 0.24, 160, 22),
                   Qt.AlignmentFlag.AlignRight, phrase)


class AmbienceArt(AnimatedArt):
    """Ambience: a sound leaving the source and returning off the walls."""

    PERIOD_S = 4.5
    FRAME_MS = 40

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h * 0.52
        room_w, room_h = w * 0.34, h * 0.28
        if room_w <= 0:
            return

        lit = 0.3 + 0.7 * self._shown
        _halo(p, cx, cy, room_w * 1.3, _accent(int(26 * lit), True))

        room = QPainterPath()
        room.addRoundedRect(QRectF(cx - room_w, cy - room_h,
                                   room_w * 2, room_h * 2), 14, 14)
        _glow_path(p, room, _accent(int(60 + 60 * lit)), 1.3, 2)

        # direct sound, then its reflections arriving later and softer
        for i in range(4):
            t = (self._phase + i * 0.22) % 1.0
            spread = t * room_w * 2.0
            fade = (1.0 - t) ** 1.7 * lit
            _glow_ellipse(p, QRectF(cx - spread, cy - spread * 0.60,
                                    spread * 2, spread * 1.20),
                          _accent(int(175 * fade), i % 2 == 1),
                          1.0 + 1.6 * fade, 2)

        # where each reflection strikes the wall
        for i in range(4):
            a = self._phase * 2 * math.pi + i * math.pi / 2
            _node(p, cx + math.cos(a) * room_w, cy + math.sin(a) * room_h,
                  2.2, _accent(int(190 * lit), i % 2 == 0))

        _halo(p, cx, cy, 26, _accent(int(120 * lit), True), inner=0.15)
        _node(p, cx, cy, 5.0, _accent(240, True))

        self._caption(p, tr("cap_ambience"),
                      int(80 + 70 * self._shown))
