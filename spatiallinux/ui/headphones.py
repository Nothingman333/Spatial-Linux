"""Headphones: which measured head the 3D sound uses, the listener's own
HRIR file, and a correction for their headphones (an AutoEQ file); plus the
A/B button that plays the original sound while it is held.

These belong to the listener and their headphones rather than to a sound,
so they live in the settings, not in presets. The panel only reports what
was picked; the window does the work (file dialogs cannot open from a
popup, which closes the moment another window takes the focus).
"""

from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)

from . import theme
from .i18n import t
from .panels import TOGGLE_WIDTH

HEADS = ("kemar", "sadie", "custom")


class HeadphonesButton(QPushButton):
    """Header button that opens the panel: a drawn pair of headphones."""

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
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        cx, cy = self.width() / 2, self.height() / 2 + 1
        band = QPainterPath()
        band.moveTo(cx - 7, cy + 2)
        band.cubicTo(cx - 7, cy - 10, cx + 7, cy - 10, cx + 7, cy + 2)
        p.drawPath(band)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.TEXT))
        for x in (cx - 8.5, cx + 5.0):
            p.drawRoundedRect(QRectF(x, cy, 3.5, 7), 1.5, 1.5)
        p.end()


class ABButton(QPushButton):
    """Held: the original sound. Released: Spatial Linux again."""

    def __init__(self, parent=None):
        super().__init__("A/B", parent)
        self.setObjectName("abButton")
        self.setFixedSize(40, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class HeadphonesPanel(QFrame):
    """The drop-down. Emits what the listener picked."""

    headPicked = pyqtSignal(str)          # "kemar" / "sadie" / "custom"
    chooseHrir = pyqtSignal()             # wants a file dialog
    loadEq = pyqtSignal()                 # wants a file dialog
    eqToggled = pyqtSignal(bool)
    eqRemoved = pyqtSignal()

    WIDTH = 400

    def __init__(self, head: str, hrir_name: str | None,
                 eq_name: str | None, eq_on: bool, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("mixer")        # the mixer's popup look
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedWidth(self.WIDTH)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 16)
        outer.setSpacing(8)

        title = QLabel(t("hp_title"))
        title.setObjectName("section")
        outer.addWidget(title)

        # -- 3D head ------------------------------------------------------
        outer.addWidget(self._heading(t("hp_head")))
        row = QHBoxLayout()
        row.setSpacing(6)
        self.head_buttons = {}
        for key in HEADS:
            btn = QPushButton(t(f"head_{key}"))
            btn.setObjectName("headChoice")
            btn.setCheckable(True)
            btn.setChecked(key == head)
            btn.setToolTip(t(f"head_{key}_tip"))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _c, k=key: self._pick_head(k))
            row.addWidget(btn)
            self.head_buttons[key] = btn
        outer.addLayout(row)

        file_row = QHBoxLayout()
        self.hrir_label = QLabel(hrir_name or t("hp_no_hrir"))
        self.hrir_label.setObjectName("subtitle")
        file_row.addWidget(self.hrir_label, 1)
        choose = QPushButton(t("hp_choose_hrir"))
        choose.setObjectName("smallButton")
        choose.setCursor(Qt.CursorShape.PointingHandCursor)
        choose.clicked.connect(self._choose_hrir)
        file_row.addWidget(choose)
        outer.addLayout(file_row)
        outer.addWidget(self._hint(t("hp_head_hint")))

        # -- headphone correction ------------------------------------------
        outer.addSpacing(4)
        outer.addWidget(self._heading(t("hp_eq")))
        eq_row = QHBoxLayout()
        eq_row.setSpacing(6)
        self.eq_label = QLabel(eq_name or t("hp_no_eq"))
        self.eq_label.setObjectName("mixerApp" if eq_name else "subtitle")
        eq_row.addWidget(self.eq_label, 1)
        if eq_name:
            toggle = QPushButton(t("on") if eq_on else t("off"))
            toggle.setObjectName("rowToggle")
            toggle.setCheckable(True)
            toggle.setChecked(eq_on)
            toggle.setFixedWidth(TOGGLE_WIDTH)
            toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle.toggled.connect(
                lambda on: (toggle.setText(t("on") if on else t("off")),
                            self.eqToggled.emit(on)))
            eq_row.addWidget(toggle)
            remove = QPushButton(t("hp_remove_eq"))
            remove.setObjectName("smallButton")
            remove.setCursor(Qt.CursorShape.PointingHandCursor)
            remove.clicked.connect(lambda: (self.hide(), self.eqRemoved.emit()))
            eq_row.addWidget(remove)
        load = QPushButton(t("hp_load_eq"))
        load.setObjectName("smallButton")
        load.setCursor(Qt.CursorShape.PointingHandCursor)
        load.clicked.connect(lambda: (self.hide(), self.loadEq.emit()))
        eq_row.addWidget(load)
        outer.addLayout(eq_row)
        outer.addWidget(self._hint(t("hp_eq_hint")))

        # -- surround ----------------------------------------------------
        outer.addSpacing(4)
        outer.addWidget(self._heading("5.1 · 7.1"))
        outer.addWidget(self._hint(t("hp_surround")))

    @staticmethod
    def _heading(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("mixerApp")
        return label

    @staticmethod
    def _hint(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("subtitle")
        label.setWordWrap(True)
        return label

    def _pick_head(self, key: str):
        for k, btn in self.head_buttons.items():
            btn.setChecked(k == key)
        self.hide()
        if key == "custom" and self.hrir_label.text() == t("hp_no_hrir"):
            self.chooseHrir.emit()
        else:
            self.headPicked.emit(key)

    def _choose_hrir(self):
        self.hide()
        self.chooseHrir.emit()

    def open_below(self, anchor: QWidget):
        pos = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height() + 6))
        self.adjustSize()
        self.move(pos.x() - self.WIDTH, pos.y())
        self.show()
