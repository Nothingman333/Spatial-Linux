"""App volumes: a drop-down panel with one slider and mute button per app
that is playing sound.

The list comes from `pw-dump`, run with QProcess so reading it never blocks
the window, and is refreshed every couple of seconds while the panel is
open. Volume and mute changes go through the engine's batched flush, so
dragging a slider sends one command per 30 ms at most. None of this needs
the Spatial Linux engine to be running: app streams belong to PipeWire.
"""

import json

from PyQt6.QtCore import Qt, QTimer, QProcess, QRectF, QPointF, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton,
    QScrollArea,
)

from . import theme
from .i18n import t
from ..engine import parse_streams


class MuteButton(QPushButton):
    """A drawn speaker; crossed out while muted. (The installed fonts have
    no speaker glyph, as with the globe.)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("mute")
        self.setCheckable(True)
        self.setFixedSize(30, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        muted = self.isChecked()
        colour = QColor(theme.TEXT_FAINT if muted else theme.TEXT)
        cx, cy = self.width() / 2 - 3, self.height() / 2
        body = QPainterPath()
        body.moveTo(cx - 6, cy - 3)
        body.lineTo(cx - 3, cy - 3)
        body.lineTo(cx + 2, cy - 7)
        body.lineTo(cx + 2, cy + 7)
        body.lineTo(cx - 3, cy + 3)
        body.lineTo(cx - 6, cy + 3)
        body.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        p.drawPath(body)
        pen = QPen(colour)
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if muted:
            p.drawLine(QPointF(cx + 5, cy - 4), QPointF(cx + 11, cy + 4))
            p.drawLine(QPointF(cx + 11, cy - 4), QPointF(cx + 5, cy + 4))
        else:
            for r in (4.5, 8.0):
                p.drawArc(QRectF(cx + 2 - r, cy - r, 2 * r, 2 * r),
                          -45 * 16, 90 * 16)
        p.end()


class MixerButton(QPushButton):
    """Header button that opens the panel: three little faders."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("globe")          # same round look as the globe
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(theme.TEXT))
        pen.setWidthF(1.3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        cx, cy = self.width() / 2, self.height() / 2
        for dx, knob in ((-5, 3), (0, -3), (5, 1)):
            x = cx + dx
            p.drawLine(QPointF(x, cy - 7), QPointF(x, cy + 7))
            p.setBrush(QColor(theme.TEXT))
            p.drawEllipse(QPointF(x, cy + knob), 1.8, 1.8)
            p.setBrush(Qt.BrushStyle.NoBrush)
        p.end()


class StreamRow(QWidget):
    def __init__(self, stream: dict, engine, parent=None):
        super().__init__(parent)
        self.node = stream["id"]
        self.engine = engine
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(2)

        names = QHBoxLayout()
        self.app_label = QLabel()
        self.app_label.setObjectName("mixerApp")
        names.addWidget(self.app_label)
        self.media_label = QLabel()
        self.media_label.setObjectName("subtitle")
        names.addWidget(self.media_label, 1)
        lay.addLayout(names)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.mute = MuteButton()
        self.mute.setToolTip(t("mute"))
        self.mute.toggled.connect(self._on_mute)
        row.addWidget(self.mute)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.valueChanged.connect(self._on_volume)
        row.addWidget(self.slider, 1)
        self.value = QLabel()
        self.value.setObjectName("subtitle")
        self.value.setFixedWidth(34)
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight |
                                Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.value)
        lay.addLayout(row)
        self.update_from(stream)

    def update_from(self, s: dict):
        self.app_label.setText(s["app"])
        media = s["media"] if s["media"] != s["app"] else ""
        self.media_label.setText(
            self.media_label.fontMetrics().elidedText(
                media, Qt.TextElideMode.ElideRight, 220))
        self.media_label.setToolTip(media)
        # never fight the user's hand: a slider being dragged keeps its value
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(int(min(100, s["volume"])))
            self.slider.blockSignals(False)
            self.value.setText(str(self.slider.value()))
        self.mute.blockSignals(True)
        self.mute.setChecked(s["muted"])
        self.mute.blockSignals(False)
        self.mute.update()

    def _on_volume(self, v: int):
        self.value.setText(str(v))
        self.engine.set_stream_volume(self.node, v)

    def _on_mute(self, on: bool):
        self.mute.update()
        self.engine.set_stream_mute(self.node, on)


class MixerPanel(QFrame):
    """The drop-down itself. A Qt popup, so a click anywhere else closes it."""

    REFRESH_MS = 1500
    WIDTH = 380
    ROW_HEIGHT = 62

    def __init__(self, engine, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("mixer")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.engine = engine
        self.setFixedWidth(self.WIDTH)
        self._rows: dict[int, StreamRow] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 14)
        outer.setSpacing(6)
        self.title = QLabel(t("mixer_title"))
        self.title.setObjectName("section")
        outer.addWidget(self.title)

        self.list_host = QWidget()
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(2)
        self.list_lay.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("mixerScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.list_host)
        self.scroll = scroll
        outer.addWidget(scroll)

        self.note = QLabel()
        self.note.setObjectName("subtitle")
        self.note.setWordWrap(True)
        outer.addWidget(self.note)

        self._timer = QTimer(self)
        self._timer.setInterval(self.REFRESH_MS)
        self._timer.timeout.connect(self.refresh)
        self._proc = None

    # -- showing -------------------------------------------------------------
    def open_below(self, anchor: QWidget):
        self.title.setText(t("mixer_title"))
        pos = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height() + 6))
        self.move(pos.x() - self.WIDTH, pos.y())
        self.refresh()
        self._timer.start()
        self.show()

    def hideEvent(self, ev):
        self._timer.stop()
        super().hideEvent(ev)

    # -- reading the stream list, without blocking ----------------------------
    def refresh(self):
        if self._proc is not None:
            return                           # the last read is still running
        proc = QProcess(self)
        proc.finished.connect(lambda *_: self._read(proc))
        proc.errorOccurred.connect(lambda *_: self._failed(proc))
        self._proc = proc
        proc.start("pw-dump", [])

    def _failed(self, proc):
        if proc.error() == QProcess.ProcessError.FailedToStart:
            self._proc = None
            self._show([], t("mixer_no_tools"))

    def _read(self, proc):
        self._proc = None
        text = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        proc.deleteLater()
        try:
            objects, _ = json.JSONDecoder().raw_decode(text) if text else ([], 0)
        except json.JSONDecodeError:
            return                           # caught mid-change; next tick
        self._show(parse_streams(objects if isinstance(objects, list) else []))

    def _show(self, streams: list, error: str | None = None):
        seen = set()
        for s in streams:
            seen.add(s["id"])
            row = self._rows.get(s["id"])
            if row is None:
                row = StreamRow(s, self.engine)
                self._rows[s["id"]] = row
                self.list_lay.insertWidget(self.list_lay.count() - 1, row)
            else:
                row.update_from(s)
        for node in [n for n in self._rows if n not in seen]:
            row = self._rows.pop(node)
            row.setParent(None)
            row.deleteLater()
        # keep the order the list came in (alphabetical by app)
        for i, s in enumerate(streams):
            self.list_lay.removeWidget(self._rows[s["id"]])
            self.list_lay.insertWidget(i, self._rows[s["id"]])

        if error:
            self.note.setText(error)
        elif not streams:
            self.note.setText(t("mixer_empty"))
        else:
            self.note.setText(t("mixer_hint"))
        # room for up to four apps; more than that scrolls
        rows = len(self._rows)
        spacing = self.list_lay.spacing()
        needed = sum(r.sizeHint().height() + spacing
                     for r in self._rows.values())
        self.scroll.setFixedHeight(min(needed, 4 * self.ROW_HEIGHT))
        self.scroll.setVisible(rows > 0)
        self.adjustSize()
