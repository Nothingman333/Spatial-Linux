"""First-run introduction.

Shown once, as a layer inside the main window (not a window of its own, so
it moves with the app and cannot be left behind): a welcome that draws itself in -- who made
it, that it is open source, what it does -- then Next / Skip, and a page per
mode with that mode's own animated scene. Nothing here uses
QGraphicsEffect: the scenes repaint continuously and nested effects fight
over the painter, so fades are done either by the widget painting itself at
an opacity or by a "curtain" of background colour drawn over it.
"""

import math

from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPointF, QVariantAnimation, QEasingCurve, QEvent,
    pyqtSignal,
)
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)

from . import theme
from . import i18n
from .i18n import t
from .art import (
    SphereArt, AmbienceArt, LipsArt, BassHeadArt, NightBreathArt,
    _halo, _node, _accent,
)


def _later(owner, ms: int, fn):
    """Run `fn` after `ms`, but only if `owner` still exists by then -- the
    page it belongs to may have been replaced in the meantime. (PyQt6 has
    no singleShot overload that takes a context object.)"""
    timer = QTimer(owner)
    timer.setSingleShot(True)
    timer.timeout.connect(fn)
    timer.start(ms)


def _fade(owner, setter, start, end, ms, delay=0, curve=QEasingCurve.Type.OutCubic):
    """Animate `setter` from start to end, optionally after a delay. The
    animation is parented to `owner` so it lives exactly as long as it."""
    anim = QVariantAnimation(owner)
    anim.setStartValue(float(start))
    anim.setEndValue(float(end))
    anim.setDuration(ms)
    anim.setEasingCurve(curve)
    anim.valueChanged.connect(lambda v: setter(float(v)))
    if delay:
        setter(float(start))
        _later(owner, delay, anim.start)
    else:
        anim.start()
    return anim


class FadeLabel(QLabel):
    """A label that paints itself at an adjustable opacity and can rise a
    few pixels into place as it appears."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._opacity = 1.0
        self._lift = 0.0

    def setOpacity(self, v: float):
        self._opacity = v
        self._lift = (1.0 - v) * 8.0
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setOpacity(self._opacity)
        p.setPen(self.palette().color(self.foregroundRole()))
        p.setFont(self.font())
        r = QRectF(self.contentsRect()).translated(0, self._lift)
        flags = self.alignment()
        if self.wordWrap():
            flags |= Qt.AlignmentFlag.AlignTop
            p.drawText(r, int(flags) | Qt.TextFlag.TextWordWrap.value,
                       self.text())
        else:
            p.drawText(r, int(flags), self.text())
        p.end()


class Curtain(QWidget):
    """Background colour drawn over a widget at a given strength -- a fade
    that works on anything underneath, animated scenes included."""

    def __init__(self, target: QWidget):
        super().__init__(target)
        self._level = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        target.installEventFilter(self)
        self.setGeometry(target.rect())
        self.raise_()

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Resize:
            self.setGeometry(obj.rect())
        return False

    def setLevel(self, v: float):
        self._level = max(0.0, min(1.0, v))
        self.setVisible(self._level > 0.0)
        self.raise_()
        self.update()

    def paintEvent(self, ev):
        c = QColor(theme.BG)
        c.setAlphaF(self._level)
        QPainter(self).fillRect(self.rect(), c)


class WelcomeArt(QWidget):
    """Sound waves ringing out from a point of light while the name draws
    itself in with a glow."""

    FRAME_MS = 33

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(self.FRAME_MS)
        self._timer.timeout.connect(self._tick)

    def showEvent(self, ev):
        self._timer.start()

    def hideEvent(self, ev):
        self._timer.stop()

    def _tick(self):
        self._t += self.FRAME_MS / 1000.0
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h * 0.42
        intro = min(1.0, self._t / 1.4)                 # the opening swell
        ease = intro * intro * (3 - 2 * intro)

        _halo(p, cx, cy, 90 * ease + 10, _accent(int(70 * ease)))

        # rings travel outward and fade, one after another
        p.setBrush(Qt.BrushStyle.NoBrush)
        for k in range(5):
            u = (self._t * 0.32 + k / 5.0) % 1.0
            r = 18 + u * min(w, h * 1.6) * 0.42
            alpha = int(170 * (1 - u) ** 1.6 * ease)
            for width, a in ((5.0, alpha // 5), (1.4, alpha)):
                pen = QPen(_accent(a, second=(k % 2 == 0)))
                pen.setWidthF(width)
                p.setPen(pen)
                p.drawEllipse(QPointF(cx, cy), r, r * 0.62)

        pulse = 0.5 + 0.5 * math.sin(self._t * 2.4)
        _node(p, cx, cy, 6 + 2 * pulse, _accent(int(255 * ease), True))

        # the wordmark: grows in, glow first and the crisp letters over it
        word = min(1.0, max(0.0, (self._t - 0.5) / 1.1))
        if word > 0:
            we = word * word * (3 - 2 * word)
            font = QFont("Noto Sans", 30)
            font.setWeight(QFont.Weight.Black)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6 - 3 * we)
            path = QPainterPath()
            path.addText(0, 0, font, "SPATIAL LINUX")
            br = path.boundingRect()
            p.save()
            p.translate(cx - br.width() / 2 - br.left(), h * 0.93)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for width, a in ((9.0, 30), (5.0, 55), (2.5, 90)):
                pen = QPen(_accent(int(a * we), True))
                pen.setWidthF(width)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen)
                p.drawPath(path)
            p.setPen(Qt.PenStyle.NoPen)
            text = QColor(theme.TEXT)
            text.setAlphaF(we)
            p.setBrush(text)
            p.drawPath(path)
            p.restore()
        p.end()


class StepsArt(QWidget):
    """The how-to page's scene: four numbered points on a line. Each lights
    up as its step's text arrives, and a spark keeps running along the
    finished path."""

    FRAME_MS = 33
    STEPS = 4
    # matches the text: a step's line fades in 150 ms + 380 ms per line,
    # and the title is line 0
    FIRST_S, EACH_S = 0.15 + 0.38, 0.38

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(self.FRAME_MS)
        self._timer.timeout.connect(self._tick)

    def showEvent(self, ev):
        self._timer.start()

    def hideEvent(self, ev):
        self._timer.stop()

    def _tick(self):
        self._t += self.FRAME_MS / 1000.0
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cy = h * 0.5
        left, right = w * 0.2, w * 0.8
        xs = [left + (right - left) * k / (self.STEPS - 1)
              for k in range(self.STEPS)]
        lit = [min(1.0, max(0.0, (self._t - self.FIRST_S - k * self.EACH_S)
                            / 0.3)) for k in range(self.STEPS)]

        # the track, and the part of it already travelled
        pen = QPen(QColor(theme.PANEL_LIGHTER))
        pen.setWidthF(2.0)
        p.setPen(pen)
        p.drawLine(QPointF(xs[0], cy), QPointF(xs[-1], cy))
        done = sum(lit) - 1.0
        if done > 0:
            end = xs[0] + (xs[-1] - xs[0]) * min(1.0, done / (self.STEPS - 1))
            for width, a in ((6.0, 50), (2.0, 220)):
                pen = QPen(_accent(a, True))
                pen.setWidthF(width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLine(QPointF(xs[0], cy), QPointF(end, cy))
            if done >= self.STEPS - 1:          # a spark running the path
                u = (self._t * 0.35) % 1.0
                _node(p, xs[0] + (xs[-1] - xs[0]) * u, cy, 3.0,
                      _accent(230, True))

        font = QFont("Noto Sans", 12)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        for k, (x, on) in enumerate(zip(xs, lit)):
            r = 17.0
            _halo(p, x, cy, r * 2.4 * on + 1, _accent(int(90 * on)))
            p.setPen(QPen(_accent(int(80 + 175 * on), True), 1.6))
            fill = QColor(theme.ACCENT)
            fill.setAlpha(int(40 + 150 * on))
            p.setBrush(fill if on else QColor(theme.PANEL))
            p.drawEllipse(QPointF(x, cy), r, r)
            p.setPen(QColor(theme.TEXT) if on else QColor(theme.TEXT_FAINT))
            p.drawText(QRectF(x - r, cy - r, 2 * r, 2 * r),
                       Qt.AlignmentFlag.AlignCenter, str(k + 1))
        p.end()


class Dots(QWidget):
    """Page indicator: the current page is a short bar, the rest are dots."""

    def __init__(self, count: int, parent=None):
        super().__init__(parent)
        self._count = count
        self._index = 0
        self.setFixedSize(count * 16 + 12, 12)

    def setIndex(self, i: int):
        self._index = i
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        x = 0.0
        for i in range(self._count):
            on = i == self._index
            p.setBrush(QColor(theme.ACCENT2 if on else theme.PANEL_LIGHTER))
            wdt = 20.0 if on else 6.0
            p.drawRoundedRect(QRectF(x, 3, wdt, 6), 3, 3)
            x += wdt + 8
        p.end()


class IntroOverlay(QWidget):
    """Covers the whole main window until it is finished or skipped, then
    emits `finished` and removes itself."""

    finished = pyqtSignal()

    # (title key, text key, scene) for every page after the welcome
    MODES = [
        ("surround", "intro_surround", SphereArt),
        ("ambience", "intro_ambience", AmbienceArt),
        ("fidelity", "intro_fidelity", LipsArt),
        ("bass", "intro_bass", BassHeadArt),
        ("night", "intro_night", NightBreathArt),
    ]
    # the welcome's buttons wait until its text has finished arriving
    BUTTONS_AFTER_MS = 2600

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("intro")
        # paint the stylesheet background, so nothing underneath shows through
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        parent.installEventFilter(self)
        self.setGeometry(parent.rect())
        # welcome, a page per mode, how to use, ready
        self._pages = 1 + len(self.MODES) + 2
        self._howto = 1 + len(self.MODES)
        self._index = 0
        self._busy = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(34, 22, 34, 26)
        outer.setSpacing(10)

        top = QHBoxLayout()
        top.addStretch()
        self.lang_btn = QPushButton()
        self.lang_btn.setObjectName("introLang")
        self.lang_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_btn.clicked.connect(self._toggle_language)
        top.addWidget(self.lang_btn)
        outer.addLayout(top)

        self.stage = QWidget()
        self.stage_lay = QVBoxLayout(self.stage)
        self.stage_lay.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.stage, 1)
        self.curtain = Curtain(self.stage)

        self.controls = QWidget()
        row = QHBoxLayout(self.controls)
        row.setContentsMargins(0, 0, 0, 0)
        self.skip_btn = QPushButton()
        self.skip_btn.setObjectName("introSkip")
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.clicked.connect(self.finish)
        row.addWidget(self.skip_btn)
        row.addStretch()
        self.dots = Dots(self._pages)
        row.addWidget(self.dots)
        row.addStretch()
        self.next_btn = QPushButton()
        self.next_btn.setObjectName("introNext")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setMinimumWidth(120)
        self.next_btn.clicked.connect(self._next)
        row.addWidget(self.next_btn)
        outer.addWidget(self.controls)
        self.controls_curtain = Curtain(self.controls)

        self._page = None
        self._show_page(0, first=True)

    # -- pages --------------------------------------------------------------
    def _build_page(self, i: int) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        if i == 0:
            art = WelcomeArt()
            lay.addWidget(art, 1)
            texts = [(t("intro_welcome"), "introTitle"),
                     (t("intro_open"), "introByline"),
                     (t("intro_what"), "introText")]
        elif i <= len(self.MODES):
            key, text_key, scene = self.MODES[i - 1]
            art = scene()
            art.setAmount(0.8)
            lay.addWidget(art, 1)
            texts = [(t(key), "introTitle"), (t(text_key), "introText")]
        elif i == self._howto:
            lay.addWidget(StepsArt(), 1)
            texts = [(t("howto_title"), "introTitle")]
            texts += [(f"{n}  ·  {t(f'howto_{n}')}", "introStep")
                      for n in range(1, StepsArt.STEPS + 1)]
        else:
            art = WelcomeArt()
            art._t = 2.0                        # already fully drawn in
            lay.addWidget(art, 1)
            texts = [(t("intro_ready_t"), "introTitle"),
                     (t("intro_ready"), "introText")]

        labels = []
        for text, name in texts:
            lbl = FadeLabel(text)
            lbl.setObjectName(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
            labels.append(lbl)
        lay.addSpacing(6)
        page._labels = labels
        return page

    def _show_page(self, i: int, first: bool = False):
        if self._page is not None:
            self.stage_lay.removeWidget(self._page)
            self._page.deleteLater()
        self._index = i
        self._page = self._build_page(i)
        self.stage_lay.addWidget(self._page)
        self.dots.setIndex(i)
        self._label_buttons()

        # the text arrives line by line
        start = 900 if i == 0 else 150
        for n, lbl in enumerate(self._page._labels):
            _fade(lbl, lbl.setOpacity, 0.0, 1.0, 520, delay=start + n * 380)

        if first:
            self.controls_curtain.setLevel(1.0)
            self.controls.setEnabled(False)

            def reveal():
                self.controls.setEnabled(True)
                _fade(self.controls_curtain, self.controls_curtain.setLevel,
                      1.0, 0.0, 500)
            _later(self, self.BUTTONS_AFTER_MS, reveal)

    def _label_buttons(self):
        last = self._index == self._pages - 1
        self.next_btn.setText(t("intro_start") if last else t("intro_next"))
        self.skip_btn.setText(t("intro_skip"))
        self.skip_btn.setVisible(not last)
        self.lang_btn.setText("EN  ·  TR" if i18n.language() == "en"
                              else "TR  ·  EN")

    def _next(self):
        if self._busy:
            return
        if self._index >= self._pages - 1:
            self.finish()
            return
        self._busy = True
        target = self._index + 1

        def swap():
            self._show_page(target)
            _fade(self.curtain, self.curtain.setLevel, 1.0, 0.0, 280)
            self._busy = False

        anim = _fade(self.curtain, self.curtain.setLevel, 0.0, 1.0, 200,
                     curve=QEasingCurve.Type.InCubic)
        anim.finished.connect(swap)

    def _toggle_language(self):
        i18n.set_language("tr" if i18n.language() == "en" else "en")
        # rebuild the page in place; its text appears again in the new language
        self._show_page(self._index)
        if self.parent() is not None and hasattr(self.parent(), "_retranslate"):
            self.parent()._retranslate()

    def showEvent(self, ev):
        super().showEvent(ev)
        self.raise_()
        self.setFocus()

    def eventFilter(self, obj, ev):
        if obj is self.parent() and ev.type() == QEvent.Type.Resize:
            self.setGeometry(obj.rect())      # follow the window's size
        return False

    def finish(self):
        self.parent().removeEventFilter(self)
        self.hide()
        self.finished.emit()
        self.deleteLater()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter,
                        Qt.Key.Key_Space) and self.controls.isEnabled():
            self._next()
        elif ev.key() == Qt.Key.Key_Escape:
            self.finish()
        else:
            super().keyPressEvent(ev)
