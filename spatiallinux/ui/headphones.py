"""Headphones: which measured head the 3D sound uses, the listener's own
HRIR file, and a correction for their headphones (an AutoEQ file). (Noise
cancelling moved to the main window: see noise.py.)

These belong to the listener and their headphones rather than to a sound,
so they live in the settings, not in presets. The panel only reports what
was picked; the window does the work (file dialogs cannot open from a
popup, which closes the moment another window takes the focus).
"""

from PyQt6.QtCore import Qt, QPoint, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
)

from . import theme
from .i18n import t, _STRINGS
from .panels import TOGGLE_WIDTH
from .controls import ChoiceStrip, ChoiceButton, GlassIconButton, GlassPopup

STYLES = ("classic", "studio", "living", "cinema", "custom")
HEADS = ("kemar", "sadie")


class HeadphonesButton(GlassIconButton):
    """Header button that opens the panel: a drawn pair of headphones."""

    def draw_icon(self, p: QPainter, cx: float, cy: float):
        pen = QPen(QColor(theme.TEXT))
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cy += 1
        band = QPainterPath()
        band.moveTo(cx - 7, cy + 2)
        band.cubicTo(cx - 7, cy - 10, cx + 7, cy - 10, cx + 7, cy + 2)
        p.drawPath(band)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.TEXT))
        for x in (cx - 8.5, cx + 5.0):
            p.drawRoundedRect(QRectF(x, cy, 3.5, 7), 1.5, 1.5)


class Spinner(QWidget):
    """A small turning arc: something is being read or sent."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._angle = 0
        from PyQt6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._turn)

    def _turn(self):
        self._angle = (self._angle + 12) % 360
        self.update()

    def setVisible(self, on: bool):
        super().setVisible(on)
        if on:
            self._timer.start()
        else:
            self._timer.stop()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(theme.ACCENT2))
        pen.setWidthF(2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(QRectF(2, 2, 12, 12), -self._angle * 16, 100 * 16)
        p.end()


class HeadphonesPanel(GlassPopup):
    """The drop-down. Emits what the listener picked."""

    stylePicked = pyqtSignal(str)         # one of STYLES
    headPicked = pyqtSignal(str)          # "kemar" / "sadie"
    chooseHrir = pyqtSignal()             # wants a file dialog
    loadEq = pyqtSignal()                 # wants a file dialog
    eqToggled = pyqtSignal(bool)
    eqRemoved = pyqtSignal()
    sonyDevice = pyqtSignal(str)          # address, or "" for automatic
    sonyRetry = pyqtSignal()
    sonyPicked = pyqtSignal(str)          # "nc" / "ambient" / "off"
    sonyLevel = pyqtSignal(int)           # ambient strength, on release
    sonyVoice = pyqtSignal(bool)          # Conversation

    WIDTH = 540

    def __init__(self, style: str, head: str, hrir_name: str | None,
                 eq_name: str | None, eq_on: bool, nc: dict | None = None,
                 parent=None):
        super().__init__(parent)
        self.setFixedWidth(self.WIDTH)

        outer = QVBoxLayout(self.body)
        outer.setContentsMargins(20, 16, 20, 18)
        outer.setSpacing(8)

        title = QLabel(t("hp_title"))
        title.setObjectName("section")
        outer.addWidget(title)

        # -- 3D style ------------------------------------------------------
        outer.addWidget(self._heading(t("hp_style")))
        self.style_buttons = self._choices(
            outer, STYLES, style, "style", self._pick_style)
        self.style_hint = self._hint(t(f"style_{style}_hint"))
        outer.addWidget(self.style_hint)

        # "Own file" is one choice: picking it the first time asks for the
        # file; the file in use, and a way to change it, show only while it
        # is the choice
        self.hrir_name = hrir_name
        if style == "custom" and hrir_name:
            file_row = QHBoxLayout()
            name = QLabel(t("hp_hrir_in_use").format(name=hrir_name))
            name.setObjectName("mixerApp")
            file_row.addWidget(name, 1)
            choose = QPushButton(t("hp_change_hrir"))
            choose.setObjectName("smallButton")
            choose.setCursor(Qt.CursorShape.PointingHandCursor)
            choose.clicked.connect(self._choose_hrir)
            self._keep_width(choose)
            file_row.addWidget(choose)
            outer.addLayout(file_row)

        # -- 3D head ------------------------------------------------------
        outer.addSpacing(4)
        outer.addWidget(self._heading(t("hp_head")))
        self.head_buttons = self._choices(
            outer, HEADS, head, "head", self._pick_head)
        next(iter(self.head_buttons.values())).parentWidget().setEnabled(
            style != "custom")
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
            self._keep_width(remove)
            eq_row.addWidget(remove)
        load = QPushButton(t("hp_load_eq"))
        load.setObjectName("smallButton")
        load.setCursor(Qt.CursorShape.PointingHandCursor)
        load.clicked.connect(lambda: (self.hide(), self.loadEq.emit()))
        self._keep_width(load)
        eq_row.addWidget(load)
        outer.addLayout(eq_row)
        outer.addWidget(self._hint(t("hp_eq_hint")))

        # -- noise cancelling ---------------------------------------------
        # which headphones the card on the main window controls: found on
        # their own, or picked here when they are not
        outer.addSpacing(4)
        outer.addWidget(self._heading(t("hp_nc")))
        # the modes, level and Conversation: shown once the headphones
        # have answered
        from .noise import NoiseCard
        self.nc_card = NoiseCard()
        self.nc_card.setFixedSize(self.WIDTH - 40, NoiseCard.HEIGHT)
        self.nc_card.picked.connect(self.sonyPicked.emit)
        self.nc_card.level.connect(self.sonyLevel.emit)
        self.nc_card.voice.connect(self.sonyVoice.emit)
        self.nc_card.retry.connect(self.sonyRetry.emit)
        outer.addWidget(self.nc_card)
        nc_row = QHBoxLayout()
        nc_row.setSpacing(6)
        self.nc_combo = QComboBox()
        self.nc_combo.setMinimumWidth(220)
        self.nc_combo.activated.connect(self._pick_nc_device)
        nc_row.addWidget(self.nc_combo, 1)
        self.nc_spinner = Spinner()
        nc_row.addWidget(self.nc_spinner)
        self.nc_retry = QPushButton(t("sony_retry"))
        self.nc_retry.setObjectName("smallButton")
        self.nc_retry.setCursor(Qt.CursorShape.PointingHandCursor)
        self.nc_retry.clicked.connect(self.sonyRetry.emit)
        self._keep_width(self.nc_retry)
        nc_row.addWidget(self.nc_retry)
        outer.addLayout(nc_row)
        self.nc_status = self._hint("")
        self.nc_status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(self.nc_status)
        self.set_nc(nc or {})

        # -- surround ----------------------------------------------------
        outer.addSpacing(4)
        outer.addWidget(self._heading("5.1 · 7.1"))
        outer.addWidget(self._hint(t("hp_surround")))

    def set_nc(self, nc: dict):
        """Fill the noise-cancelling section from the window's _nc_status."""
        self.nc_combo.blockSignals(True)
        self.nc_combo.clear()
        self.nc_combo.addItem(t("hp_nc_auto"), "")
        for dev in nc.get("devices") or []:
            self.nc_combo.addItem(dev.get("name") or dev["address"], dev["address"])
        chosen = nc.get("chosen") or ""
        self.nc_combo.setCurrentIndex(max(0, self.nc_combo.findData(chosen)))
        self.nc_combo.blockSignals(False)

        state = nc.get("state") or {}
        searching = bool(nc.get("searching"))
        self.nc_card.set_sony(state if state.get("confirmed") else None)
        status = state.get("status")
        name = state.get("name") or ""
        if not nc.get("available", True):
            text = t("sony_no_bluetooth")
        elif status == "applying":
            text = t("sony_applying")
        elif searching or status == "reading":
            text = t("hp_nc_searching")
        elif state and status is None:
            text = t("hp_nc_found").format(name=name)
            if not state.get("mode"):
                text += " " + t("hp_nc_no_mode")
        elif status == "not_sony":
            text = t("hp_nc_not_sony").format(name=name)
        elif status == "failed":
            text = t("hp_nc_failed").format(name=name)
            if state.get("error"):
                text += f" ({state['error']})"
        else:
            text = t("hp_nc_none")
        self.nc_status.setText(text)
        self.nc_status.setToolTip(t("hp_nc_log").format(path=nc["log"])
                                  if nc.get("log") else "")
        self.nc_spinner.setVisible(searching)
        self.nc_retry.setVisible(not searching and nc.get("available", True))
        self.adjustSize()

    def _pick_nc_device(self, index: int):
        self.sonyDevice.emit(self.nc_combo.itemData(index) or "")

    @staticmethod
    def _keep_width(btn: QPushButton):
        """Never squeezed below its own text by a long label beside it."""
        btn.ensurePolished()
        from PyQt6.QtGui import QFontMetrics
        bold = btn.font()
        bold.setBold(True)          # checked buttons are drawn bold
        btn.setMinimumWidth(max(btn.sizeHint().width(),
                                QFontMetrics(bold).horizontalAdvance(btn.text()) + 24))

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

    @staticmethod
    def _choices(outer, keys, current, prefix, on_pick) -> dict:
        """A strip of options, one of them chosen (see ChoiceStrip)."""
        strip = ChoiceStrip(stretch=True, height=32)
        buttons = {}
        for key in keys:
            btn = strip.add(ChoiceButton(t(f"{prefix}_{key}")))
            btn.setChecked(key == current)
            tip = f"{prefix}_{key}_tip"
            if tip in _STRINGS:
                btn.setToolTip(t(tip))
            btn.clicked.connect(lambda _c, k=key: on_pick(k))
            buttons[key] = btn
        outer.addWidget(strip)
        return buttons

    def _pick_style(self, key: str):
        for k, btn in self.style_buttons.items():
            btn.setChecked(k == key)

        def go():
            self.hide()
            if key == "custom" and not self.hrir_name:
                self.chooseHrir.emit()
            else:
                self.stylePicked.emit(key)
        # let the thumb arrive before the panel goes (and a restart of the
        # sound holds the window up for a moment)
        QTimer.singleShot(280, go)

    def _pick_head(self, key: str):
        for k, btn in self.head_buttons.items():
            btn.setChecked(k == key)
        QTimer.singleShot(280, lambda: (self.hide(), self.headPicked.emit(key)))

    def _choose_hrir(self):
        self.hide()
        self.chooseHrir.emit()

    def open_below(self, anchor: QWidget):
        pos = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height() + 8))
        self.adjustSize()
        self.move(pos.x() - self.WIDTH, pos.y())
        self.show()
