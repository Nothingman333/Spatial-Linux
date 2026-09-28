"""Headphones: which measured head the 3D sound uses, the listener's own
HRIR file, and a correction for their headphones (an AutoEQ file).

These belong to the listener and their headphones rather than to a sound,
so they live in the settings, not in presets. The panel only reports what
was picked; the window does the work (file dialogs cannot open from a
popup, which closes the moment another window takes the focus).
"""

from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
)

from . import theme
from .i18n import t, _STRINGS
from .panels import TOGGLE_WIDTH

STYLES = ("classic", "studio", "living", "cinema", "custom")
HEADS = ("kemar", "sadie")


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


class HeadphonesPanel(QFrame):
    """The drop-down. Emits what the listener picked."""

    stylePicked = pyqtSignal(str)         # one of STYLES
    headPicked = pyqtSignal(str)          # "kemar" / "sadie"
    chooseHrir = pyqtSignal()             # wants a file dialog
    loadEq = pyqtSignal()                 # wants a file dialog
    eqToggled = pyqtSignal(bool)
    eqRemoved = pyqtSignal()
    sonyPicked = pyqtSignal(str)          # "nc" / "ambient" / "off"
    sonyLevel = pyqtSignal(int)           # ambient strength, on release
    sonyVoice = pyqtSignal(bool)          # focus on voice

    WIDTH = 540

    def __init__(self, style: str, head: str, hrir_name: str | None,
                 eq_name: str | None, eq_on: bool, sony: dict | None = None,
                 parent=None):
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
        for btn in self.head_buttons.values():
            btn.setEnabled(style != "custom")
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

        # -- Sony noise cancelling -----------------------------------------
        # only once Sony headphones have been found; filled in by the window
        # from a background thread, see set_sony
        self.sony_box = QWidget()
        box = QVBoxLayout(self.sony_box)
        box.setContentsMargins(0, 4, 0, 0)
        box.setSpacing(8)
        self.sony_heading = self._heading(t("sony_title"))
        box.addWidget(self.sony_heading)
        self.sony_buttons = self._choices(
            box, ("nc", "ambient", "off"), None, "sony", self.sonyPicked.emit)

        # ambient sound's strength and focus on voice -- only in that mode;
        # noise cancelling has no strength to set (see sony.py)
        self.sony_ambient_row = QWidget()
        row = QHBoxLayout(self.sony_ambient_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        label = QLabel(t("sony_level"))
        label.setObjectName("subtitle")
        row.addWidget(label)
        self.sony_slider = QSlider(Qt.Orientation.Horizontal)
        self.sony_slider.setRange(1, 20)
        self.sony_slider.valueChanged.connect(
            lambda v: self.sony_level_label.setText(str(v)))
        self.sony_slider.sliderReleased.connect(
            lambda: self.sonyLevel.emit(self.sony_slider.value()))
        row.addWidget(self.sony_slider, 1)
        self.sony_level_label = QLabel("20")
        self.sony_level_label.setObjectName("subtitle")
        self.sony_level_label.setFixedWidth(22)
        row.addWidget(self.sony_level_label)
        self.sony_voice = QPushButton(t("sony_voice"))
        self.sony_voice.setObjectName("smallButton")
        self.sony_voice.setCheckable(True)
        self.sony_voice.setToolTip(t("sony_voice_tip"))
        self.sony_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sony_voice.clicked.connect(lambda on: self.sonyVoice.emit(on))
        self._keep_width(self.sony_voice)
        row.addWidget(self.sony_voice)
        box.addWidget(self.sony_ambient_row)
        self.sony_nc_note = self._hint(t("sony_nc_note"))
        box.addWidget(self.sony_nc_note)

        self.sony_status = self._hint("")
        box.addWidget(self.sony_status)
        box.addWidget(self._hint(t("sony_hint")))
        outer.addWidget(self.sony_box)
        self.set_sony(sony)

        # -- surround ----------------------------------------------------
        outer.addSpacing(4)
        outer.addWidget(self._heading("5.1 · 7.1"))
        outer.addWidget(self._hint(t("hp_surround")))

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
        """A row of buttons, one of them checked."""
        row = QHBoxLayout()
        row.setSpacing(6)
        buttons = {}
        for key in keys:
            btn = QPushButton(t(f"{prefix}_{key}"))
            btn.setObjectName("headChoice")
            btn.setCheckable(True)
            btn.setChecked(key == current)
            tip = f"{prefix}_{key}_tip"
            if tip in _STRINGS:
                btn.setToolTip(t(tip))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _c, k=key: on_pick(k))
            btn.ensurePolished()
            # room for the text in bold, as it is when picked
            bold = btn.font()
            bold.setBold(True)
            from PyQt6.QtGui import QFontMetrics
            btn.setMinimumWidth(QFontMetrics(bold).horizontalAdvance(btn.text()) + 20)
            row.addWidget(btn)
            buttons[key] = btn
        outer.addLayout(row)
        return buttons

    def set_sony(self, sony: dict | None):
        """{name, mode, status} of the Sony headphones, or None to hide the
        section (none found, or not ones that take these commands)."""
        self.sony_box.setVisible(bool(sony))
        if sony:
            self.sony_heading.setText(f"{t('sony_title')} · {sony['name']}")
            busy = sony.get("status") in ("reading", "applying")
            for key, btn in self.sony_buttons.items():
                btn.setChecked(key == sony.get("mode"))
                btn.setEnabled(not busy)
            self.sony_ambient_row.setVisible(sony.get("mode") == "ambient")
            self.sony_ambient_row.setEnabled(not busy)
            self.sony_nc_note.setVisible(sony.get("mode") == "nc")
            if not self.sony_slider.isSliderDown():
                self.sony_slider.blockSignals(True)
                self.sony_slider.setValue(int(sony.get("level") or 20))
                self.sony_slider.blockSignals(False)
                self.sony_level_label.setText(str(self.sony_slider.value()))
            self.sony_voice.setChecked(bool(sony.get("voice")))
            status = sony.get("status")
            self.sony_status.setText(t(f"sony_{status}") if status else "")
            self.sony_status.setVisible(bool(status))
        self.adjustSize()

    def _pick_style(self, key: str):
        for k, btn in self.style_buttons.items():
            btn.setChecked(k == key)
        self.hide()
        if key == "custom" and not self.hrir_name:
            self.chooseHrir.emit()
        else:
            self.stylePicked.emit(key)

    def _pick_head(self, key: str):
        for k, btn in self.head_buttons.items():
            btn.setChecked(k == key)
        self.hide()
        self.headPicked.emit(key)

    def _choose_hrir(self):
        self.hide()
        self.chooseHrir.emit()

    def open_below(self, anchor: QWidget):
        pos = anchor.mapToGlobal(QPoint(anchor.width(), anchor.height() + 6))
        self.adjustSize()
        self.move(pos.x() - self.WIDTH, pos.y())
        self.show()
