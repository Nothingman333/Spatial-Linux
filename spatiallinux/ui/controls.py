"""Shared controls with motion: choice strips, glass icon buttons and glass
pop-ups.

* ChoiceStrip / ChoiceButton -- a row of options where each option is its
  own glass pill, so they read as things to pick, and the chosen one is a
  white thumb that slides over to the new choice. The thumb stretches as it
  goes: its leading edge leaves first and its trailing edge catches up, and
  each option's text darkens exactly as far as the thumb covers it. The
  mode tabs, the noise-cancelling modes and the headphone choices all use
  it. The buttons stay ordinary checkable QPushButtons (clicked, toggled,
  setChecked), so nothing that drives them had to change.
* GlassIconButton -- the round buttons in the header, with a hover that
  eases in and out.
* GlassPopup -- a drop-down whose background is the window behind it,
  blurred and tinted, refreshed while it is open so the moving picture and
  animations keep showing through; it fades and grows in when it opens.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    Qt, QRectF, QRect, QPoint, QPointF, QSize, QTimer, QVariantAnimation,
    QEasingCurve, QEvent,
)
from PyQt6.QtGui import (
    QPainter, QColor, QPainterPath, QLinearGradient, QPen, QPixmap,
    QFontMetrics, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QFrame,
    QGraphicsOpacityEffect, QSizePolicy,
)

from . import theme


def _mix(a: QColor, b: QColor, k: float) -> QColor:
    k = max(0.0, min(1.0, k))
    return QColor(int(a.red() + (b.red() - a.red()) * k),
                  int(a.green() + (b.green() - a.green()) * k),
                  int(a.blue() + (b.blue() - a.blue()) * k),
                  int(a.alpha() + (b.alpha() - a.alpha()) * k))


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1.0 - (1.0 - x) ** 3            # out-cubic


def blur(pm: QPixmap, factor: int = 14) -> QPixmap:
    """A soft blur: scaled down in steps and back up, smoothly each time --
    cheap enough to redo several times a second."""
    if pm.isNull():
        return pm
    ratio = pm.devicePixelRatio()
    img = pm.toImage()
    w, h = img.width(), img.height()
    steps, small = [], img
    size = QSize(w, h)
    while factor > 1:
        k = min(4, factor)
        size = QSize(max(1, size.width() // k), max(1, size.height() // k))
        small = small.scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        steps.append(size)
        factor //= k
    for size in reversed([QSize(w, h)] + steps[:-1]):
        small = small.scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    out = QPixmap.fromImage(small)
    out.setDevicePixelRatio(ratio)
    return out


# -- choices ---------------------------------------------------------------------

class ChoiceButton(QPushButton):
    """One option of a ChoiceStrip. Draws only its text; the strip draws
    the pills and the thumb underneath."""

    def __init__(self, text: str = "", glyph: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("choice")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.glyph = glyph
        self._hover = 0.0
        self._press = 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(170)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)
        self.setLabel(text)

    def setLabel(self, label: str):
        self.label = label
        self.setText(f"{self.glyph}  {label}" if self.glyph else label)
        self.updateGeometry()

    def sizeHint(self):
        fm = QFontMetrics(self._font(True))
        return QSize(fm.horizontalAdvance(self.text()) + 30, 30)

    def minimumSizeHint(self):
        return self.sizeHint()

    def _font(self, strong: bool):
        f = self.font()
        f.setWeight(f.Weight.DemiBold if strong else f.Weight.Medium)
        return f

    def _on_hover(self, v):
        self._hover = float(v)
        strip = self.parentWidget()
        if isinstance(strip, ChoiceStrip):
            strip.update()
        self.update()

    def _animate_hover(self, target: float):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def enterEvent(self, ev):
        if self.isEnabled():
            self._animate_hover(1.0)
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._animate_hover(0.0)
        super().leaveEvent(ev)

    def mousePressEvent(self, ev):
        self._press = 1.0
        self._touch()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._press = 0.0
        self._touch()
        super().mouseReleaseEvent(ev)

    def _touch(self):
        strip = self.parentWidget()
        if isinstance(strip, ChoiceStrip):
            strip.update()

    def coverage(self) -> float:
        strip = self.parentWidget()
        if isinstance(strip, ChoiceStrip):
            return strip.coverage(self)
        return 1.0 if self.isChecked() else 0.0

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        k = self.coverage()
        idle = QColor(255, 255, 255, int(178 + 60 * self._hover))
        colour = _mix(idle, QColor(theme.CHOSEN_TEXT), k)
        if not self.isEnabled():
            colour.setAlpha(int(colour.alpha() * 0.45))
        p.setPen(colour)
        p.setFont(self._font(k > 0.5))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


class ChoiceStrip(QWidget):
    """A row of ChoiceButtons. At most one is checked; the strip keeps the
    thumb on it. `stretch` spreads the options across the width (the
    choices in a panel); without it they keep their own width (the tabs)."""

    RADIUS_K = 0.5          # pills are fully round

    def __init__(self, stretch: bool = True, height: int = 30,
                 glow: bool = False, parent=None):
        super().__init__(parent)
        self._stretch = stretch
        self._glow = glow
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding if stretch
                           else QSizePolicy.Policy.Fixed,
                           QSizePolicy.Policy.Fixed)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(6)
        self.buttons: list[ChoiceButton] = []
        self._thumb = QRectF()
        self._from = QRectF()
        self._to = QRectF()
        self._shown = 0.0            # thumb opacity
        self._move = QVariantAnimation(self)
        self._move.setDuration(380)
        self._move.setStartValue(0.0)
        self._move.setEndValue(1.0)
        self._move.valueChanged.connect(self._on_move)
        self._fade = QVariantAnimation(self)
        self._fade.setDuration(220)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.valueChanged.connect(self._on_fade)
        self._current = None

    def add(self, btn: ChoiceButton) -> ChoiceButton:
        btn.setParent(self)
        btn.setFixedHeight(self.height())
        if self._stretch:
            btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Fixed)
        self.row.addWidget(btn, 1 if self._stretch else 0)
        self.buttons.append(btn)
        btn.toggled.connect(lambda _on: QTimer.singleShot(0, self.retarget))
        btn.installEventFilter(self)
        return btn

    # -- the thumb ------------------------------------------------------------
    def _checked(self):
        for b in self.buttons:
            if b.isChecked() and b.isVisible():
                return b
        return None

    def retarget(self, animate: bool = True):
        target = self._checked()
        if target is None:
            self._current = None
            self._fade_to(0.0, animate)
            return
        rect = QRectF(target.geometry())
        if (not animate or self._shown < 0.05 or self._thumb.isNull()
                or not self.isVisible()):
            self._move.stop()
            self._thumb = QRectF(rect)
            self._current = target
            self._fade_to(1.0, animate and self.isVisible())
            self.update()
            return
        if target is self._current and self._move.state() != self._move.State.Running:
            self._thumb = rect
            self.update()
            return
        self._current = target
        self._from = QRectF(self._thumb)
        self._to = rect
        self._move.stop()
        self._move.start()
        self._fade_to(1.0, True)

    def _fade_to(self, level: float, animate: bool):
        self._fade.stop()
        if not animate:
            self._shown = level
            self.update()
            return
        self._fade.setStartValue(self._shown)
        self._fade.setEndValue(level)
        self._fade.start()

    def _on_fade(self, v):
        self._shown = float(v)
        self._repaint_all()

    def _on_move(self, u):
        u = float(u)
        # the leading edge sets off first, the trailing one follows:
        # the thumb stretches a little in flight and settles
        lead = _smooth(min(1.0, u * 1.45))
        trail = _smooth(max(0.0, (u - 0.18) / 0.82))
        a, b = self._from, self._to
        right = b.center().x() >= a.center().x()
        kl, kr = (trail, lead) if right else (lead, trail)
        self._thumb = QRectF(
            QPointF(a.left() + (b.left() - a.left()) * kl, b.top()),
            QPointF(a.right() + (b.right() - a.right()) * kr, b.bottom()))
        self._repaint_all()

    def _repaint_all(self):
        self.update()
        for b in self.buttons:
            b.update()

    def coverage(self, btn: ChoiceButton) -> float:
        if self._shown <= 0.0 or self._thumb.isNull():
            return 0.0
        g = QRectF(btn.geometry())
        inter = g.intersected(self._thumb)
        if inter.isEmpty():
            return 0.0
        return self._shown * min(1.0, inter.width() / max(1.0, g.width() - 6))

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Show,
                         QEvent.Type.Hide):
            if self._move.state() != self._move.State.Running:
                QTimer.singleShot(0, lambda: self.retarget(animate=False))
        return False

    def showEvent(self, ev):
        super().showEvent(ev)
        QTimer.singleShot(0, lambda: self.retarget(animate=False))

    def changeEvent(self, ev):
        if ev.type() == QEvent.Type.EnabledChange:
            self._repaint_all()
        super().changeEvent(ev)

    # -- drawing ----------------------------------------------------------------
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.5)
        # every option is a pill of its own -- plainly something to press
        for b in self.buttons:
            if not b.isVisible():
                continue
            r = QRectF(b.geometry()).adjusted(0.5, 0.5, -0.5, -0.5)
            rad = r.height() * self.RADIUS_K
            h = b._hover
            fill = QLinearGradient(r.topLeft(), r.bottomLeft())
            fill.setColorAt(0.0, QColor(255, 255, 255, int(26 + 22 * h - 10 * b._press)))
            fill.setColorAt(1.0, QColor(255, 255, 255, int(12 + 14 * h)))
            p.setBrush(fill)
            edge = QLinearGradient(r.topLeft(), r.bottomLeft())
            edge.setColorAt(0.0, QColor(255, 255, 255, int(46 + 40 * h)))
            edge.setColorAt(1.0, QColor(255, 255, 255, int(16 + 20 * h)))
            p.setPen(QPen(edge, 1.0))
            p.drawRoundedRect(r, rad, rad)
        # the chosen one: a white thumb, with a violet glow under it
        if self._shown > 0.0 and not self._thumb.isNull():
            r = self._thumb.adjusted(0.5, 0.5, -0.5, -0.5)
            rad = r.height() * self.RADIUS_K
            p.setOpacity(p.opacity() * self._shown)
            if self._glow:
                for grow, alpha in ((7, 16), (4, 26), (2, 40)):
                    c = QColor(theme.ACCENT)
                    c.setAlpha(alpha)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(c)
                    g = r.adjusted(-grow, -grow + 2, grow, grow + 2)
                    p.drawRoundedRect(g, rad + grow, rad + grow)
            body = QLinearGradient(r.topLeft(), r.bottomLeft())
            body.setColorAt(0.0, QColor("#ffffff"))
            body.setColorAt(1.0, QColor("#e4e0f2"))
            p.setBrush(body)
            p.setPen(QPen(QColor(255, 255, 255, 230), 1.0))
            p.drawRoundedRect(r, rad, rad)
        p.end()


# -- header buttons ------------------------------------------------------------

class GlassIconButton(QPushButton):
    """A round glass button with a drawn icon (drawn by subclasses in
    draw_icon). The hover eases in: the glass brightens, the rim catches
    the light and a soft glow comes up behind the icon."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("globe")
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self._hover = 0.0
        self._press = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_hover)

    def _on_hover(self, v):
        self._hover = float(v)
        self.update()

    def _to(self, v: float):
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(v)
        self._anim.start()

    def enterEvent(self, ev):
        self._to(1.0)
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._to(0.0)
        super().leaveEvent(ev)

    def mousePressEvent(self, ev):
        self._press = 1.0
        self.update()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._press = 0.0
        self.update()
        super().mouseReleaseEvent(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        h = self._hover
        # glass: see-through, lighter at the top, like a lens
        fill = QLinearGradient(r.topLeft(), r.bottomLeft())
        fill.setColorAt(0.0, QColor(255, 255, 255, int(34 + 30 * h - 12 * self._press)))
        fill.setColorAt(1.0, QColor(255, 255, 255, int(8 + 16 * h)))
        p.setBrush(fill)
        rim = QLinearGradient(r.topLeft(), r.bottomLeft())
        rim.setColorAt(0.0, QColor(255, 255, 255, int(80 + 70 * h)))
        rim.setColorAt(0.6, QColor(255, 255, 255, int(20 + 20 * h)))
        rim.setColorAt(1.0, QColor(255, 255, 255, int(34 + 30 * h)))
        p.setPen(QPen(rim, 1.0))
        p.drawEllipse(r)
        if h > 0.01:
            glow = QRadialGradient(r.center(), r.width() * 0.45)
            c = QColor(theme.ACCENT2)
            c.setAlpha(int(46 * h))
            glow.setColorAt(0.0, c)
            glow.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(r)
        self.draw_icon(p, self.width() / 2, self.height() / 2)
        p.end()

    def draw_icon(self, p: QPainter, cx: float, cy: float):
        pass


# -- pop-ups ---------------------------------------------------------------------

class GlassPopup(QFrame):
    """A drop-down of frosted glass. Build the content in `self.body`.

    Its background is the window underneath, blurred, tinted dark and lit
    from the top edge; it is re-read a dozen times a second while open, so
    what moves behind it keeps moving. Opening, the glass grows in from a
    little smaller and the content fades up."""

    RADIUS = 20.0
    BACKDROP_MS = 85

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.setObjectName("glassPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._source = parent.window() if parent is not None else None
        self._bg: QPixmap | None = None
        self._bg_rect = QRect()
        self._reveal = 1.0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.body = QWidget(self)
        self.body.setObjectName("glassBody")
        lay.addWidget(self.body)
        self._timer = QTimer(self)
        self._timer.setInterval(self.BACKDROP_MS)
        self._timer.timeout.connect(self._read_backdrop)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(260)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_reveal)
        self._anim.finished.connect(self._revealed)
        self._fx = None

    # -- the blurred window behind ----------------------------------------------
    def _read_backdrop(self):
        src = self._source
        if src is None or not self.isVisible():
            return
        top_left = src.mapFromGlobal(self.mapToGlobal(QPoint(0, 0)))
        want = QRect(top_left, self.size())
        rect = want.intersected(src.rect())
        if rect.isEmpty():
            self._bg = None
            return
        grabbed = src.grab(rect)
        self._bg = blur(grabbed, 16)
        self._bg_rect = rect.translated(-top_left)
        self.update()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._read_backdrop()
        self._timer.start()
        # the content fades up as the glass grows in
        self._fx = QGraphicsOpacityEffect(self.body)
        self._fx.setOpacity(0.0)
        self.body.setGraphicsEffect(self._fx)
        self._anim.stop()
        self._anim.start()

    def hideEvent(self, ev):
        self._timer.stop()
        super().hideEvent(ev)

    def _on_reveal(self, v):
        self._reveal = float(v)
        if self._fx is not None:
            self._fx.setOpacity(max(0.0, min(1.0, (self._reveal - 0.25) / 0.75)))
        self.update()

    def _revealed(self):
        # an effect renders its widget through a buffer; drop it once the
        # fade is done so text and sliders are drawn directly again
        self.body.setGraphicsEffect(None)
        self._fx = None

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        u = self._reveal
        inset = 7.0 * (1.0 - u)
        r = QRectF(self.rect()).adjusted(0.5 + inset, 0.5 + inset * 0.6,
                                         -0.5 - inset, -0.5 - inset * 1.4)
        path = QPainterPath()
        path.addRoundedRect(r, self.RADIUS, self.RADIUS)
        p.setOpacity(min(1.0, u * 1.6))
        p.setClipPath(path)
        # base, for any part hanging past the window's edge
        p.fillRect(self.rect(), QColor(19, 17, 26, 238))
        if self._bg is not None:
            p.drawPixmap(self._bg_rect.topLeft(), self._bg)
        # tint: dark enough to read on, light enough to see through
        p.fillRect(self.rect(), QColor(17, 15, 24, 150))
        sheen = QLinearGradient(0, 0, 0, self.height())
        sheen.setColorAt(0.0, QColor(255, 255, 255, 20))
        sheen.setColorAt(0.35, QColor(255, 255, 255, 6))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(self.rect(), sheen)
        p.setClipping(False)
        rim = QLinearGradient(0, 0, 0, self.height())
        rim.setColorAt(0.0, QColor(255, 255, 255, 70))
        rim.setColorAt(0.5, QColor(255, 255, 255, 22))
        rim.setColorAt(1.0, QColor(255, 255, 255, 30))
        p.setPen(QPen(rim, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()
