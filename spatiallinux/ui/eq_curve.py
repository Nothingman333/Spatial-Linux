from PyQt6.QtCore import Qt, QRectF, QPointF, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath, QLinearGradient
from PyQt6.QtWidgets import QWidget

from . import theme

MARGIN_L = 20
MARGIN_R = 20
MARGIN_T = 14
MARGIN_B = 26
GAIN_RANGE = 12.0  # +/- dB


def _freq_label(f: float) -> str:
    if f >= 1000:
        return f"{f/1000:g}k"
    return f"{f:g}"


class EQCurve(QWidget):
    bandChanged = pyqtSignal(int, float)

    def __init__(self, bands: list[float], gains: list[float] | None = None, parent=None):
        super().__init__(parent)
        self.bands = bands
        self.gains = list(gains) if gains else [0.0] * len(bands)
        self.setMinimumHeight(190)
        self.setMouseTracking(True)
        self._drag_index = None
        self._hover_index = None
        self.setCursor(Qt.CursorShape.CrossCursor)

        # used when a preset is loaded, so the curve morphs instead of jumping
        self._anim_from: list[float] = []
        self._anim_to: list[float] = []
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(420)
        self._anim.valueChanged.connect(self._on_anim)

    def setGains(self, gains: list[float], animate: bool = False):
        target = list(gains)
        if not animate or len(target) != len(self.gains):
            self._anim.stop()
            self.gains = target
            self.update()
            return
        # glide from where the curve is now to the new shape
        self._anim.stop()
        self._anim_from = list(self.gains)
        self._anim_to = target
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def _on_anim(self, t):
        t = float(t)
        eased = t * t * (3.0 - 2.0 * t)          # smoothstep
        self.gains = [a + (b - a) * eased
                      for a, b in zip(self._anim_from, self._anim_to)]
        self.update()

    # -- geometry -------------------------------------------------------
    def _plot_rect(self) -> QRectF:
        return QRectF(MARGIN_L, MARGIN_T, self.width() - MARGIN_L - MARGIN_R,
                       self.height() - MARGIN_T - MARGIN_B)

    def _point_pos(self, index: int) -> QPointF:
        rect = self._plot_rect()
        n = len(self.bands)
        x = rect.left() + rect.width() * (index / (n - 1)) if n > 1 else rect.center().x()
        frac = (self.gains[index] + GAIN_RANGE) / (2 * GAIN_RANGE)
        y = rect.bottom() - frac * rect.height()
        return QPointF(x, y)

    def _index_at(self, pos: QPointF):
        for i in range(len(self.bands)):
            p = self._point_pos(i)
            if (p.x() - pos.x()) ** 2 + (p.y() - pos.y()) ** 2 <= 16 ** 2:
                return i
        return None

    # -- interaction -------------------------------------------------------
    def mousePressEvent(self, ev):
        idx = self._index_at(ev.position())
        if idx is None:
            # snap to nearest band under cursor x
            rect = self._plot_rect()
            n = len(self.bands)
            if n > 1:
                frac = (ev.position().x() - rect.left()) / rect.width()
                idx = round(frac * (n - 1))
                idx = max(0, min(n - 1, idx))
        self._drag_index = idx
        self._set_gain_from_y(idx, ev.position().y())

    def mouseMoveEvent(self, ev):
        if self._drag_index is not None:
            self._set_gain_from_y(self._drag_index, ev.position().y())
        else:
            self._hover_index = self._index_at(ev.position())
            self.update()

    def mouseReleaseEvent(self, ev):
        self._drag_index = None

    def leaveEvent(self, ev):
        self._hover_index = None
        self.update()

    def wheelEvent(self, ev):
        idx = self._index_at(ev.position())
        if idx is None:
            return
        step = 0.5 if ev.angleDelta().y() > 0 else -0.5
        self._set_gain(idx, self.gains[idx] + step)

    def _set_gain_from_y(self, index: int, y: float):
        rect = self._plot_rect()
        frac = 1.0 - (y - rect.top()) / rect.height()
        gain = frac * (2 * GAIN_RANGE) - GAIN_RANGE
        self._set_gain(index, gain)

    def _set_gain(self, index: int, gain: float):
        gain = max(-GAIN_RANGE, min(GAIN_RANGE, gain))
        self.gains[index] = gain
        self.update()
        self.bandChanged.emit(index, gain)

    def mouseDoubleClickEvent(self, ev):
        # double-click a band to return it to 0 dB
        idx = self._index_at(ev.position())
        if idx is None:
            rect = self._plot_rect()
            n = len(self.bands)
            if n > 1 and rect.width() > 0:
                frac = (ev.position().x() - rect.left()) / rect.width()
                idx = max(0, min(n - 1, round(frac * (n - 1))))
        if idx is not None:
            self._drag_index = None
            self._set_gain(idx, 0.0)

    # -- painting -------------------------------------------------------
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.35)     # EQ switched off: the curve is kept, dimmed
        rect = self._plot_rect()

        # gridlines
        grid_pen = QPen(QColor(theme.PANEL_LIGHT))
        grid_pen.setWidth(1)
        p.setPen(grid_pen)
        for i in range(len(self.bands)):
            x = self._point_pos(i).x()
            p.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
        zero_y = rect.bottom() - rect.height() / 2
        pen0 = QPen(QColor(theme.PANEL_LIGHTER))
        pen0.setWidth(1)
        p.setPen(pen0)
        p.drawLine(int(rect.left()), int(zero_y), int(rect.right()), int(zero_y))

        # curve path
        pts = [self._point_pos(i) for i in range(len(self.bands))]
        path = QPainterPath()
        if pts:
            path.moveTo(pts[0])
            for i in range(len(pts) - 1):
                p0, p1 = pts[i], pts[i + 1]
                c1 = QPointF((p0.x() + p1.x()) / 2, p0.y())
                c2 = QPointF((p0.x() + p1.x()) / 2, p1.y())
                path.cubicTo(c1, c2, p1)

        # filled area under curve
        if pts:
            fill_path = QPainterPath(path)
            fill_path.lineTo(pts[-1].x(), zero_y)
            fill_path.lineTo(pts[0].x(), zero_y)
            fill_path.closeSubpath()
            top_color = QColor(theme.ACCENT2)
            top_color.setAlpha(90)
            bottom_color = QColor(theme.ACCENT)
            bottom_color.setAlpha(10)
            grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
            grad.setColorAt(0, top_color)
            grad.setColorAt(1, bottom_color)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(grad)
            p.drawPath(fill_path)

        curve_pen = QPen(QColor(theme.ACCENT))
        curve_pen.setWidth(2)
        p.setPen(curve_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # points
        for i, pt in enumerate(pts):
            active = i == self._drag_index or i == self._hover_index
            r = 5 if active else 4
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.ACCENT2 if active else theme.ACCENT))
            p.drawEllipse(pt, r, r)

        # frequency labels
        p.setPen(QColor(theme.TEXT_DIM))
        p.setFont(QFont("Noto Sans", 8))
        for i, freq in enumerate(self.bands):
            x = pts[i].x() if pts else 0
            p.drawText(QRectF(x - 20, rect.bottom() + 6, 40, 16),
                       Qt.AlignmentFlag.AlignHCenter, _freq_label(freq))

        # hover/drag dB readout
        idx = self._drag_index if self._drag_index is not None else self._hover_index
        if idx is not None:
            p.setPen(QColor(theme.TEXT))
            p.setFont(QFont("Noto Sans", 9, QFont.Weight.DemiBold))
            pt = pts[idx]
            txt = f"{self.gains[idx]:+.1f} dB"
            p.drawText(QRectF(pt.x() - 30, pt.y() - 24, 60, 16),
                       Qt.AlignmentFlag.AlignHCenter, txt)
