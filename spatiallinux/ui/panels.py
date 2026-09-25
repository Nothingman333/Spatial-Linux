import math

from PyQt6.QtCore import Qt, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QFrame,
)

from . import theme
from .i18n import t
from .art import SphereArt

PANEL_HEIGHT = 170
ART_PANEL_HEIGHT = 330


class FeaturePanel(QFrame):
    """Base for the panel that appears under the feature row."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setFixedHeight(PANEL_HEIGHT)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(20, 14, 20, 14)

        row = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("section")
        row.addWidget(label)
        row.addStretch()
        self._header_row = row
        self._outer.addLayout(row)

    def body(self) -> QVBoxLayout:
        return self._outer

    # height one extra slider row adds to the panel
    ROW_HEIGHT = 34

    def add_slider_row(self, caption: str, minimum: float, maximum: float,
                       value: float, suffix: str, decimals: int, on_change,
                       signed: bool = False):
        """Add a labelled slider above the panel's hint text, grow the panel
        to fit, and call `on_change(value)` as it moves."""
        scale = 10 ** decimals
        row = QHBoxLayout()
        row.setSpacing(14)
        cap = QLabel(caption.upper())
        cap.setObjectName("section")
        cap.setMinimumWidth(92)
        row.addWidget(cap)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(round(minimum * scale)), int(round(maximum * scale)))
        slider.setValue(int(round(value * scale)))
        row.addWidget(slider, 1)
        sign = "+" if signed else ""

        def fmt(v):
            return f"{v:{sign}.{decimals}f}{suffix}"

        label = QLabel(fmt(value))
        label.setMinimumWidth(66)
        label.setAlignment(Qt.AlignmentFlag.AlignRight |
                           Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(label)

        def changed(raw):
            v = raw / scale
            label.setText(fmt(v))
            on_change(v)

        slider.valueChanged.connect(changed)
        hint = getattr(self, "_hint", None)
        at = self._outer.indexOf(hint) if hint is not None else -1
        if at >= 0:
            self._outer.insertLayout(at, row)
        else:
            self._outer.addLayout(row)
        self.setFixedHeight(self.maximumHeight() + self.ROW_HEIGHT)
        return slider


class SliderPanel(FeaturePanel):
    """A feature driven by one linear slider.

    Values are carried as ints in `scale`ths of a unit so the slider can move
    in fractions (e.g. dB in tenths) without a separate spin box.
    """
    valueChanged = pyqtSignal(float)

    def __init__(self, title: str, caption: str, minimum: float, maximum: float,
                 value: float, suffix: str = "", hint: str = "",
                 decimals: int = 0, art=None, parent=None):
        super().__init__(title, parent)
        self._scale = 10 ** decimals
        self._decimals = decimals
        self._suffix = suffix
        self._span = max(1e-9, maximum - minimum)
        self._min = minimum

        lay = self.body()
        self.art = art
        if art is not None:
            self.setFixedHeight(ART_PANEL_HEIGHT)
            lay.addWidget(art, 1)
        else:
            lay.addStretch()

        row = QHBoxLayout()
        row.setSpacing(14)
        cap = QLabel(caption.upper())
        cap.setObjectName("section")
        cap.setMinimumWidth(80)
        row.addWidget(cap)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(minimum * self._scale), int(maximum * self._scale))
        self.slider.setValue(int(value * self._scale))
        self.slider.valueChanged.connect(self._on_change)
        row.addWidget(self.slider, 1)

        self.value_label = QLabel(self._format(value))
        self.value_label.setMinimumWidth(66)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight |
                                      Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.value_label)
        lay.addLayout(row)

        if hint:
            h = self._hint = QLabel(hint)
            h.setObjectName("subtitle")
            h.setWordWrap(True)
            lay.addWidget(h)
        if self.art is None:
            lay.addStretch()
        self._push_art(value)

    def _push_art(self, value: float):
        if self.art is not None:
            self.art.setAmount((value - self._min) / self._span)

    def _format(self, v: float) -> str:
        return f"{v:.{self._decimals}f}{self._suffix}"

    def _on_change(self, raw: int):
        v = raw / self._scale
        self.value_label.setText(self._format(v))
        self._push_art(v)
        self.valueChanged.emit(v)

    def setValue(self, v: float):
        self.slider.blockSignals(True)
        self.slider.setValue(int(v * self._scale))
        self.slider.blockSignals(False)
        self.value_label.setText(self._format(v))
        self._push_art(v)


class SurroundPanel(FeaturePanel):
    valueChanged = pyqtSignal(float)
    lfeChanged = pyqtSignal(float)

    def __init__(self, amount: float, lfe: float = 0.0, parent=None):
        super().__init__("3D Surround", parent)
        self.setFixedHeight(340)

        self._header_row.addWidget(QLabel(t("intensity")))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(int(amount * 100))
        self.slider.setFixedWidth(190)
        self.slider.valueChanged.connect(self._on_slider)
        self._header_row.addWidget(self.slider)
        self.value_label = QLabel(f"{int(amount * 100)}%")
        self.value_label.setFixedWidth(44)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight |
                                      Qt.AlignmentFlag.AlignVCenter)
        self._header_row.addWidget(self.value_label)

        self.stage = SphereArt()
        self.stage.setMinimumHeight(150)
        self.body().addWidget(self.stage, 1)

        # Subwoofer / LFE trim, part of the 3D mode itself
        lfe_row = QHBoxLayout()
        lfe_row.setSpacing(14)
        lfe_cap = QLabel(t("subwoofer"))
        lfe_cap.setObjectName("section")
        lfe_cap.setMinimumWidth(92)
        lfe_row.addWidget(lfe_cap)
        self.lfe_slider = QSlider(Qt.Orientation.Horizontal)
        self.lfe_slider.setRange(0, 120)          # 0 .. +12.0 dB, in tenths
        self.lfe_slider.setValue(int(lfe * 10))
        self.lfe_slider.valueChanged.connect(self._on_lfe)
        lfe_row.addWidget(self.lfe_slider, 1)
        self.lfe_label = QLabel(f"{lfe:.1f} dB")
        self.lfe_label.setMinimumWidth(66)
        self.lfe_label.setAlignment(Qt.AlignmentFlag.AlignRight |
                                    Qt.AlignmentFlag.AlignVCenter)
        lfe_row.addWidget(self.lfe_label)
        self.body().addLayout(lfe_row)

        hint = self._hint = QLabel(t("surround_hint"))
        hint.setObjectName("subtitle")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        self.body().addWidget(hint)

        self.stage.setAmount(amount)

    def _on_lfe(self, raw: int):
        v = raw / 10.0
        self.lfe_label.setText(f"{v:.1f} dB")
        self.lfeChanged.emit(v)

    def setLfe(self, v: float):
        self.lfe_slider.blockSignals(True)
        self.lfe_slider.setValue(int(v * 10))
        self.lfe_slider.blockSignals(False)
        self.lfe_label.setText(f"{v:.1f} dB")

    def _on_slider(self, v: int):
        self.value_label.setText(f"{v}%")
        self.stage.setAmount(v / 100.0)
        self.valueChanged.emit(v / 100.0)

    def setValue(self, amount: float):
        self.slider.blockSignals(True)
        self.slider.setValue(int(amount * 100))
        self.slider.blockSignals(False)
        self.value_label.setText(f"{int(amount * 100)}%")
        self.stage.setAmount(amount)
