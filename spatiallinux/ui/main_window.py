import json
import math
import os
from dataclasses import asdict

from PyQt6.QtCore import Qt, QTimer, QVariantAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSlider, QPushButton, QComboBox, QInputDialog, QMessageBox,
)

from .. import presets, __version__
from .. import engine as engine_mod
from ..engine import SpatialEngine, EQ_BANDS
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QDesktopServices, QPainterPath, QLinearGradient,
    QIcon, QPixmap,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QUrl, QRectF, QPointF

from . import theme
from . import i18n
from .i18n import t
from .eq_curve import EQCurve
from .panels import SurroundPanel, SliderPanel
from .art import BassHeadArt, LipsArt, NightBreathArt, AmbienceArt, FrameTimer
from .intro import IntroOverlay
from .mixer import MixerButton, MixerPanel


LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "data", "spatiallinux.svg")


class Panel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")


class FeatureButton(QPushButton):
    def __init__(self, glyph: str, label: str, parent=None):
        super().__init__(f"{glyph}\n{label}", parent)
        self.setObjectName("feature")
        self.setCheckable(True)
        self.setMinimumSize(112, 66)


class GlobeButton(QPushButton):
    """Language switch. The globe is drawn rather than set as an emoji --
    the installed fonts have no glyph for it and it renders as a blank box."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("globe")
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(theme.TEXT)
        pen = QPen(c)
        pen.setWidthF(1.3)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        r = 8.0
        cx, cy = self.width() / 2, self.height() / 2
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
        for k in (0.45, 0.95):                 # meridians
            w = r * k
            p.drawEllipse(QRectF(cx - w, cy - r, w * 2, r * 2))


class BylineLink(QLabel):
    """"by Sali" in the title bar: a link to the project page that glows
    softly -- a slow breath, with a glint that sweeps across it now and then.
    Hovering lights it fully. It runs at a low frame rate and only while
    visible, so it costs next to nothing."""

    FRAME_MS = 50            # 20 fps is plenty for a slow shimmer
    BREATH_S = 3.2           # one full brighten/dim cycle
    GLINT_EVERY_S = 4.5      # a glint crosses the text this often
    GLINT_S = 0.9            # ...and takes this long to do it

    def __init__(self, text: str, url: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("byline")
        self._url = url
        self._t = 0.0
        self._hover = False
        self._timer = FrameTimer(self, self.FRAME_MS, self._tick)
        self._timer.want(True)
        if url:
            self.setToolTip(url)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _tick(self):
        self._t += self.FRAME_MS / 1000.0
        self.update()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._timer.shown(True)

    def hideEvent(self, ev):
        self._timer.shown(False)
        super().hideEvent(ev)

    def enterEvent(self, ev):
        self._hover = True
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._hover = False
        self.update()
        super().leaveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if (self._url and ev.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(ev.position().toPoint())):
            QDesktopServices.openUrl(QUrl(self._url))
        super().mouseReleaseEvent(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = self.font()
        fm = self.fontMetrics()
        r = self.contentsRect()
        path = QPainterPath()
        path.addText(QPointF(r.left(), r.bottom() - fm.descent()),
                     font, self.text())

        breath = 0.5 - 0.5 * math.cos(2 * math.pi * self._t / self.BREATH_S)
        glow = 1.0 if self._hover else 0.25 + 0.5 * breath

        # halo: the same letters stroked wide and faint, then a little tighter
        p.setBrush(Qt.BrushStyle.NoBrush)
        for width, alpha in ((4.0, 38), (2.2, 70)):
            c = QColor(theme.ACCENT2)
            c.setAlpha(int(alpha * glow))
            pen = QPen(c)
            pen.setWidthF(width)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawPath(path)

        # the letters themselves, tinted from faint grey toward the accent
        base = QColor(theme.TEXT_FAINT)
        lit = QColor(theme.ACCENT2)
        mix = glow

        def blend(k):
            return QColor(int(base.red() + (lit.red() - base.red()) * k),
                          int(base.green() + (lit.green() - base.green()) * k),
                          int(base.blue() + (lit.blue() - base.blue()) * k))

        fill = QLinearGradient(r.left(), 0, r.right(), 0)
        fill.setColorAt(0.0, blend(mix))
        fill.setColorAt(1.0, blend(mix))
        # a narrow glint sliding left to right every few seconds
        g = (self._t % self.GLINT_EVERY_S) / self.GLINT_S
        if 0.0 <= g <= 1.0 and not self._hover:
            centre = -0.2 + 1.4 * g
            for pos, k in ((centre - 0.18, mix), (centre, 1.0),
                           (centre + 0.18, mix)):
                if 0.0 < pos < 1.0:
                    c = QColor(theme.TEXT) if k == 1.0 else blend(k)
                    fill.setColorAt(pos, c)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawPath(path)
        p.end()


class InfoButton(GlobeButton):
    """"How to use": a drawn i in a ring, beside the globe. Opens the
    introduction again."""

    def paintEvent(self, ev):
        QPushButton.paintEvent(self, ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(theme.TEXT))
        pen.setWidthF(1.3)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy, r = self.width() / 2, self.height() / 2, 8.0
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(cx, cy - 1.0), QPointF(cx, cy + 4.2))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.TEXT))
        p.drawEllipse(QPointF(cx, cy - 4.0), 1.2, 1.2)
        p.end()


class PowerButton(QPushButton):
    """Power button: a drawn power symbol, with a halo that breathes while
    the engine is running. The pill sits inset from the widget's edge (see
    MARGIN and the stylesheet) so the halo has room to glow; drawn past the
    edge it used to be clipped into a hard square."""

    MARGIN = 6

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setObjectName("power")
        self.setCheckable(True)
        self._phase = 0.0
        self._timer = FrameTimer(self, 33, self._tick)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, on: bool):
        self._timer.want(on)
        self.update()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._timer.shown(True)

    def hideEvent(self, ev):
        self._timer.shown(False)
        super().hideEvent(ev)

    def _tick(self):
        self._phase = (self._phase + 0.02) % 1.0
        self.update()

    def paintEvent(self, ev):
        if self.isChecked():
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            pulse = 0.5 + 0.5 * math.sin(self._phase * 2 * math.pi)
            p.setPen(Qt.PenStyle.NoPen)
            m = self.MARGIN
            pill = QRectF(self.rect()).adjusted(m, m, -m, -m)
            for ring in range(3):
                spread = min(m, 1 + ring * 1.5 + 2.5 * pulse)
                colour = QColor(theme.ACCENT2)
                colour.setAlpha(int(46 * (1 - ring / 3) * (0.4 + 0.6 * pulse)))
                p.setBrush(colour)
                r = pill.adjusted(-spread, -spread, spread, spread)
                p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
            p.end()
        super().paintEvent(ev)

        # the power symbol: a ring open at the top, and a stroke through it
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("white") if self.isChecked() else QColor(theme.TEXT))
        pen.setWidthF(2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        cx, cy, r = self.width() / 2, self.height() / 2 + 1, 8.0
        # Qt angles run anticlockwise from 3 o'clock: leave 60-120 deg (the top) open
        p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), 60 * 16, -300 * 16)
        p.drawLine(QPointF(cx, cy - r - 2), QPointF(cx, cy - 1))
        p.end()


class MainWindow(QMainWindow):
    BASE_HEIGHT = 560

    # key, glyph, label
    FEATURES = [
        ("surround", "◎"), ("ambience", "≈"), ("fidelity", "✦"),
        ("bass", "◍"), ("night", "☾"),
    ]

    # The project page the "by Sali" byline opens. The repository is private
    # for now, so it only opens for accounts that have access to it.
    GITHUB_URL = "https://github.com/Nothingman333/Spatial-Linux"

    # Where a feature's slider starts the first time it is selected, so that
    # picking a mode is immediately audible instead of a no-op at zero.
    DEFAULTS = {"surround": 0.65, "ambience": 0.05,
                "fidelity": 5.0, "bass": 6.0, "night": 0.5,
                # the extra controls inside the 3D and Ambience panels
                "surround_lfe": 3.0, "surround_treble": -1.0,
                "surround_room": 0.25, "ambience_treble": -2.0,
                # Fidelity's clarity lift, offered inside 3D as well
                "surround_clarity": 5.0,
                # whether each optional 3D extra is switched on (1) or off (0)
                "surround_lfe_on": 1.0, "surround_room_on": 1.0,
                "surround_clarity_on": 1.0}

    # the 3D extras that can be switched off, each keeping its value
    OPTIONAL_EXTRAS = ("surround_lfe", "surround_room", "surround_clarity")

    # the mode a first launch (and the Defaults button) comes up in
    DEFAULT_ACTIVE = "surround"

    # built-in presets, shown under a name in the interface language
    BUILTIN_PRESETS = ("flat", "music", "movie", "gaming", "night", "bass")

    # modes whose panel carries a treble slider
    TREBLE_MODES = ("surround", "ambience")

    # how often the settings are checked and, if changed, written to disk
    AUTOSAVE_MS = 2000
    # longest a control change waits before it is sent to the engine
    FLUSH_MS = 30

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spatial Linux")
        # No fixed minimum width: an explicit one overrides what the layout
        # needs, and with a wider system font the header needs more than
        # 860 px -- the window then squeezed it and cut the title to
        # "SPATIAL LIN". The layout's own minimum is always enough.
        self.resize(880, self.BASE_HEIGHT)

        self.engine = SpatialEngine()
        # control changes are gathered and sent together, at most every
        # FLUSH_MS, instead of one external command per slider step
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(self.FLUSH_MS)
        self._flush_timer.timeout.connect(self.engine.flush)
        self.engine.defer = self._schedule_flush
        self.settings = presets.load_settings()
        session = presets.load_session()
        if session is not None and session.language:
            i18n.set_language(session.language)
        self.state = session or self._factory_state()
        self._panel = None
        # set while the combo is being repopulated, so rebuilding the list
        # does not look like the user picking a preset
        self._loading_preset = False
        # Last value the user chose per feature. Only the active feature's
        # value is ever sent to the engine; the rest are held here so that
        # coming back to a mode restores where you left it.
        self._remembered = dict(self.DEFAULTS)

        # drives the window/panel height when a mode panel slides in or out
        self._height_anim = QVariantAnimation(self)
        self._height_anim.setDuration(260)
        self._height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._height_anim.valueChanged.connect(self._on_height_step)

        self._build_ui()
        self._adopt_state(self.state)
        self._refresh_output_label()
        vol = self.settings.get("volume")
        if isinstance(vol, int):
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(max(0, min(100, vol)))
            self.volume_slider.blockSignals(False)
            self.volume_label.setText(str(self.volume_slider.value()))

        # Settings are written as they change, not only on a clean close:
        # a logout or a kill never reaches closeEvent, and that used to
        # throw away everything set since the last launch.
        self._saved_snapshot = None
        self._autosave = QTimer(self)
        self._autosave.setInterval(self.AUTOSAVE_MS)
        self._autosave.timeout.connect(self._save_if_changed)
        self._autosave.start()

        # after the window is on screen: the intro (first run only), then
        # the engine back on if it was on when the app was last closed
        QTimer.singleShot(250, self._after_show)

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        outer.addWidget(self._build_header())
        outer.addWidget(self._build_feature_row())

        self.detail_holder = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_holder)
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_holder.setVisible(False)
        self.detail_holder.setMaximumHeight(0)
        outer.addWidget(self.detail_holder)

        self.eq_panel = self._build_eq_panel()
        self.eq_panel.setMinimumHeight(290)
        outer.addWidget(self.eq_panel, 1)
        self._outer_spacing = outer.spacing()

    # -- header -------------------------------------------------------------
    def _build_header(self) -> QWidget:
        header = Panel()
        lay = QHBoxLayout(header)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(14)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel("SPATIAL LINUX")
        title.setObjectName("title")
        # Never let the layout squeeze the name: with wider system fonts it
        # used to be cut down to "SPATIAL LIN".
        title.ensurePolished()
        title.setMinimumWidth(
            title.fontMetrics().horizontalAdvance(title.text()) + 6)
        title_row.addWidget(title)
        self.byline = BylineLink("by Sali", self.GITHUB_URL)
        title_row.addWidget(self.byline, 0, Qt.AlignmentFlag.AlignBottom)
        title_row.addStretch()
        title_box.addLayout(title_row)
        self.subtitle = QLabel(t("subtitle"))
        self.subtitle.setObjectName("subtitle")
        title_box.addWidget(self.subtitle)
        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setObjectName("version")
        title_box.addWidget(self.version_label)
        # the app's logo beside its name
        logo = QLabel()
        logo.setObjectName("logo")
        size = 46
        # Drawn straight from the SVG at the screen's own scale. Asking
        # QIcon for a pixmap already scaled for the screen and then scaling
        # it again made it twice too big on HiDPI screens, and cropped.
        ratio = self.devicePixelRatioF() or 1.0
        pix = QPixmap(round(size * ratio), round(size * ratio))
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        QSvgRenderer(LOGO_PATH).render(painter)
        painter.end()
        pix.setDevicePixelRatio(ratio)
        logo.setPixmap(pix)
        logo.setFixedSize(size, size)
        lay.addWidget(logo, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(title_box)

        self.power_btn = PowerButton()
        self.power_btn.setFixedSize(78 + 2 * PowerButton.MARGIN,
                                    38 + 2 * PowerButton.MARGIN)
        self.power_btn.setToolTip(t("power_tip"))
        self.power_btn.clicked.connect(self._on_power_toggled)
        lay.addWidget(self.power_btn)

        vol_box = QVBoxLayout()
        vol_box.setSpacing(2)
        vol_head = self.vol_head = QLabel(t("volume"))
        vol_head.setObjectName("section")
        vol_box.addWidget(vol_head)
        vol_row = QHBoxLayout()
        vol_row.setSpacing(10)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        vol_row.addWidget(self.volume_slider)
        self.volume_label = QLabel("100")
        self.volume_label.setObjectName("subtitle")
        self.volume_label.setFixedWidth(34)
        vol_row.addWidget(self.volume_label)
        vol_box.addLayout(vol_row)
        lay.addLayout(vol_box)

        pre_box = QVBoxLayout()
        pre_box.setSpacing(2)
        pre_head = self.pre_head = QLabel(t("preamp"))
        pre_head.setObjectName("section")
        pre_box.addWidget(pre_head)
        pre_row = QHBoxLayout()
        pre_row.setSpacing(10)
        self.preamp_slider = QSlider(Qt.Orientation.Horizontal)
        self.preamp_slider.setRange(-12, 12)
        self.preamp_slider.setValue(0)
        self.preamp_slider.setFixedWidth(100)
        self.preamp_slider.valueChanged.connect(self._on_preamp_changed)
        pre_row.addWidget(self.preamp_slider)
        self.preamp_label = QLabel("0 dB")
        self.preamp_label.setObjectName("subtitle")
        self.preamp_label.setFixedWidth(46)
        pre_row.addWidget(self.preamp_label)
        pre_box.addLayout(pre_row)
        lay.addLayout(pre_box)

        lay.addStretch()

        out_box = QVBoxLayout()
        out_box.setSpacing(2)
        out_head = self.out_head = QLabel(t("output"))
        out_head.setObjectName("section")
        out_head.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.output_label = QLabel("—")
        self.output_label.setObjectName("pill")
        out_box.addWidget(out_head)
        out_box.addWidget(self.output_label, alignment=Qt.AlignmentFlag.AlignRight)
        lay.addLayout(out_box)

        # per-app volumes, in a drop-down panel
        self.mixer_btn = MixerButton()
        self.mixer_btn.setToolTip(t("mixer_tip"))
        self.mixer_btn.clicked.connect(self._open_mixer)
        lay.addWidget(self.mixer_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self._mixer = None

        self.lang_btn = GlobeButton()
        self.lang_btn.setToolTip(t("language_tip"))
        self.lang_btn.clicked.connect(self._toggle_language)
        lay.addWidget(self.lang_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.info_btn = InfoButton()
        self.info_btn.setToolTip(t("info_tip"))
        self.info_btn.clicked.connect(lambda: self._show_intro())
        lay.addWidget(self.info_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return header

    # -- feature row -------------------------------------------------------
    def _build_feature_row(self) -> QWidget:
        panel = Panel()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.feature_buttons = {}
        for key, glyph in self.FEATURES:
            btn = FeatureButton(glyph, t(key))
            btn.clicked.connect(lambda _c, k=key: self._on_feature_clicked(k))
            row.addWidget(btn)
            self.feature_buttons[key] = btn
        lay.addLayout(row)

        note = self.mode_note = QLabel(t("one_mode_note"))
        note.setObjectName("subtitle")
        lay.addWidget(note)
        return panel

    # -- EQ panel -----------------------------------------------------------
    def _build_eq_panel(self) -> QWidget:
        panel = Panel()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(20, 14, 20, 16)

        top = QHBoxLayout()
        label = self.eq_head = QLabel(t("equaliser"))
        label.setObjectName("section")
        top.addWidget(label)
        top.addStretch()

        # choosing a preset switches to it straight away -- there is no
        # separate "load" step to forget
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(140)
        # The restored session is not any one preset. Showing the first name
        # in the list would claim it is loaded -- and, being already current,
        # picking it would then do nothing.
        self._fill_presets(None)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_index)
        top.addWidget(self.preset_combo)

        self.save_btn = QPushButton(t("save"))
        self.save_btn.clicked.connect(self._on_save_preset)
        top.addWidget(self.save_btn)

        self.eq_reset_btn = QPushButton(t("reset_eq"))
        self.eq_reset_btn.clicked.connect(self._on_reset_eq)
        top.addWidget(self.eq_reset_btn)

        self.default_btn = QPushButton(t("defaults"))
        self.default_btn.setToolTip(t("defaults_tip"))
        self.default_btn.clicked.connect(self._on_restore_defaults)
        top.addWidget(self.default_btn)
        lay.addLayout(top)

        self.eq_curve = EQCurve(EQ_BANDS)
        self.eq_curve.bandChanged.connect(self._on_eq_changed)
        lay.addWidget(self.eq_curve, 1)

        bottom = QHBoxLayout()
        # The old Limiter switch lived here. It clamped the output at full
        # scale -- exactly where the sound card clips anyway -- so switching
        # it made no audible difference. The clamp still runs, always on;
        # the slot now holds something that does something.
        eq_lbl = self.eq_toggle_head = QLabel(t("eq"))
        eq_lbl.setObjectName("section")
        bottom.addWidget(eq_lbl)
        self.eq_btn = QPushButton(t("on"))
        self.eq_btn.setCheckable(True)
        self.eq_btn.setChecked(True)
        self.eq_btn.setToolTip(t("eq_tip"))
        self.eq_btn.clicked.connect(self._on_eq_toggled)
        bottom.addWidget(self.eq_btn)
        eq_hint = self.eq_hint = QLabel(t("eq_hint"))
        eq_hint.setObjectName("subtitle")
        bottom.addSpacing(14)
        bottom.addWidget(eq_hint)
        bottom.addStretch()
        self.status_label = QLabel(t("status_off"))
        self.status_label.setObjectName("subtitle")
        bottom.addWidget(self.status_label)
        lay.addLayout(bottom)

        return panel

    # -- engine plumbing for the one active effect -------------------------
    def _apply_amount(self, key: str, value: float):
        """Send one feature's value to the engine (also updates state)."""
        if key == "surround":
            self.engine.set_surround(value, self.state)
        elif key == "ambience":
            self.engine.set_ambience(value, self.state)
        elif key == "fidelity":
            self.engine.set_fidelity(value, self.state)
        elif key == "bass":
            self.engine.set_bass(value, self.state)
        elif key == "night":
            self.engine.set_night(value, self.state)

    def _apply_exclusive(self, active: str | None):
        """Engage exactly one effect and silence every other one."""
        for key, _glyph in self.FEATURES:
            self._apply_amount(key, self._remembered[key] if key == active else 0.0)
        if active == "surround":
            # a trace of room, folded into 3D itself -- far below the level
            # you would hear as reverb, but it helps the image sit outside
            # the head. The Reverb slider turns it down with the rest.
            self.engine.set_ambience(
                engine_mod.SURROUND_REVERB * self._remembered["surround"]
                * self._effective("surround_room"),
                self.state)
            # 3D's own Clarity slider drives the same shelves as Fidelity;
            # the loop above has just zeroed them for the inactive mode
            self.engine.set_fidelity(self._effective("surround_clarity"),
                                     self.state)
        self.engine.set_room(self._effective("surround_room"), self.state)
        self.engine.set_treble(
            self._remembered[f"{active}_treble"]
            if active in self.TREBLE_MODES else 0.0,
            self.state)
        # the subwoofer trim belongs to the 3D mode, so it comes and goes with it
        self.engine.set_lfe(
            self._effective("surround_lfe") if active == "surround" else 0.0,
            self.state)
        self.state.active = active
        self._refresh_feature_buttons()

    def _effective(self, key: str) -> float:
        """An optional 3D extra's value as the engine should get it: its
        remembered value while switched on, nothing while off."""
        if self._remembered.get(f"{key}_on", 1.0):
            return self._remembered[key]
        return 0.0

    def _on_extra_toggled(self, key: str, on: bool):
        self._remembered[f"{key}_on"] = 1.0 if on else 0.0
        if self.state.active == "surround":
            self._apply_exclusive("surround")

    def _refresh_feature_buttons(self):
        for key, btn in self.feature_buttons.items():
            on = self.state.active == key
            btn.setChecked(on)
            btn.setProperty("active", on)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # -- state <-> widgets --------------------------------------------------
    def _adopt_state(self, state):
        """Take a freshly loaded state as the current one: remember each
        feature's amount, engage only the one it marks active."""
        self.state = state
        state.limiter = True          # see the note where the EQ switch is built
        self._remembered = {
            "surround": state.surround or self.DEFAULTS["surround"],
            # while 3D is engaged, `ambience` only holds its faint built-in
            # room trace, not a level the user chose for Ambience
            "ambience": (0.0 if state.active == "surround" else state.ambience)
                        or self.DEFAULTS["ambience"],
            # while 3D is engaged, `fidelity` holds 3D's Clarity, not a
            # level chosen in the Fidelity mode
            "fidelity": (0.0 if state.active == "surround" else state.fidelity)
                        or self.DEFAULTS["fidelity"],
            "surround_clarity": (state.fidelity if state.active == "surround"
                                 else self.DEFAULTS["surround_clarity"]),
            "bass": state.bass or self.DEFAULTS["bass"],
            "night": state.night or self.DEFAULTS["night"],
            # the 3D-only controls mean something only in a state saved
            # with 3D engaged; otherwise they are just the defaults
            "surround_lfe": (state.lfe if state.active == "surround"
                             else self.DEFAULTS["surround_lfe"]),
            "surround_room": (state.room if state.active == "surround"
                              else self.DEFAULTS["surround_room"]),
            "surround_treble": (state.treble if state.active == "surround"
                                else self.DEFAULTS["surround_treble"]),
            "ambience_treble": (state.treble if state.active == "ambience"
                                else self.DEFAULTS["ambience_treble"]),
        }
        # anything the state has no word on (a setting newer than the file,
        # such as the 3D extras' on/off) starts at its default
        for key, value in self.DEFAULTS.items():
            self._remembered.setdefault(key, value)
        # Newer sessions and presets carry every mode's value, not only the
        # active one's; take those where present.
        for key, value in (state.modes or {}).items():
            if key in self._remembered and isinstance(value, (int, float)):
                self._remembered[key] = float(value)
        active = state.active if state.active in self.FEATURE_KEYS else None

        self.eq_curve.setGains(state.normalised_eq(), animate=True)
        self.eq_btn.setChecked(state.eq_enabled)
        self.eq_btn.setText(t("on") if state.eq_enabled else t("off"))
        self.eq_curve.setEnabled(state.eq_enabled)
        self.preamp_slider.blockSignals(True)
        self.preamp_slider.setValue(int(state.preamp))
        self.preamp_slider.blockSignals(False)
        self.preamp_label.setText(f"{int(state.preamp):+d} dB")

        self._close_panel_widget()
        self._apply_exclusive(active)
        if active:
            self._open_panel(active)
        else:
            self.detail_holder.setVisible(False)
            self._fit_window(0, animate=False)

    def _toggle_language(self):
        i18n.set_language("tr" if i18n.language() == "en" else "en")
        self._retranslate()

    def _retranslate(self):
        """Re-label everything in place; no restart, nothing loses its value."""
        self.subtitle.setText(t("subtitle"))
        self.vol_head.setText(t("volume"))
        self.pre_head.setText(t("preamp"))
        self.out_head.setText(t("output"))
        self.lang_btn.setToolTip(t("language_tip"))
        self.info_btn.setToolTip(t("info_tip"))
        self.mixer_btn.setToolTip(t("mixer_tip"))
        self.mode_note.setText(t("one_mode_note"))
        self.eq_head.setText(t("equaliser"))
        self.eq_hint.setText(t("eq_hint"))
        self.save_btn.setText(t("save"))
        self.eq_reset_btn.setText(t("reset_eq"))
        self.default_btn.setText(t("defaults"))
        self.default_btn.setToolTip(t("defaults_tip"))
        self.eq_toggle_head.setText(t("eq"))
        self.eq_btn.setText(t("on") if self.state.eq_enabled else t("off"))
        self.eq_btn.setToolTip(t("eq_tip"))
        self.status_label.setText(t("status_on") if self.engine.running
                                  else t("status_off"))
        for key, glyph in self.FEATURES:
            self.feature_buttons[key].setText(f"{glyph}\n{t(key)}")
        if self._active_key():
            self._open_panel(self._active_key())   # rebuild with new labels
        self._refresh_output_label()
        self._fill_presets(self.preset_combo.currentData())
        self.power_btn.setToolTip(t("power_tip"))

    def _active_key(self):
        return self.state.active if self.state.active in self.FEATURE_KEYS else None

    FEATURE_KEYS = tuple(k for k, _g in FEATURES)

    def _refresh_output_label(self):
        self.output_label.setText(self.engine.current_output_label()
                                  or t("unknown_output"))

    # -- power / volume -----------------------------------------------------
    def _open_mixer(self):
        # rebuilt each time, so its labels follow the current language
        if self._mixer is not None:
            self._mixer.deleteLater()
        self._mixer = MixerPanel(self.engine, self)
        self._mixer.open_below(self.mixer_btn)

    def _schedule_flush(self):
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _on_power_toggled(self, checked: bool):
        if checked:
            missing = engine_mod.missing_tools()
            if missing:
                self.power_btn.setChecked(False)
                QMessageBox.critical(self, "Spatial Linux",
                                     f"{t('tools_missing')}\n\n"
                                     + ", ".join(missing))
                return
            try:
                self.engine.start(self.state)
            except engine_mod.AlreadyRunning:
                self.power_btn.setChecked(False)
                QMessageBox.warning(self, "Spatial Linux", t("already_running"))
                return
            except Exception as e:
                self.power_btn.setChecked(False)
                QMessageBox.critical(self, "Spatial Linux", f"{t('engine_failed')}\n{e}")
                return
            self.status_label.setText(t("status_on"))
            # The slider holds the volume the user chose (and it is saved
            # with the settings); give it to the new device rather than
            # letting the device's own level overwrite it, as it used to.
            self.engine.set_volume(self.volume_slider.value())
            self.engine.flush()
        else:
            self.engine.stop()
            self.status_label.setText(t("status_off"))
        self._refresh_output_label()

    def _on_volume_changed(self, value: int):
        self.volume_label.setText(str(value))
        self.engine.set_volume(value)

    def _on_preamp_changed(self, value: int):
        self.preamp_label.setText(f"{value:+d} dB")
        self.engine.set_preamp(float(value), self.state)

    # -- feature selection --------------------------------------------------
    def _on_feature_clicked(self, key: str):
        if self.state.active == key:
            self._deactivate()
        else:
            self._apply_exclusive(key)
            self._open_panel(key)

    def _deactivate(self):
        self._apply_exclusive(None)
        self._close_panel_widget()
        self.detail_holder.setVisible(False)
        self._fit_window(0)

    def _open_panel(self, key: str):
        self._close_panel_widget()
        amount = self._remembered[key]

        if key == "surround":
            p = SurroundPanel(amount, self._remembered["surround_lfe"],
                              bool(self._remembered["surround_lfe_on"]))
            p.lfeChanged.connect(self._on_lfe_changed)
            p.lfeToggled.connect(
                lambda on: self._on_extra_toggled("surround_lfe", on))
            p.add_slider_row(t("reverb_3d"), 0, 100,
                             self._remembered["surround_room"] * 100, "%", 0,
                             self._on_room_changed,
                             toggle=(bool(self._remembered["surround_room_on"]),
                                     lambda on: self._on_extra_toggled(
                                         "surround_room", on)))
        elif key == "ambience":
            p = SliderPanel(t("ambience"), t("room"), 0, 100, amount * 100,
                            "%", t("ambience_hint"), art=AmbienceArt())
        elif key == "fidelity":
            p = SliderPanel(t("fidelity"), t("clarity"), 0, 10, amount, " dB",
                            t("fidelity_hint"), decimals=1, art=LipsArt())
        elif key == "bass":
            p = SliderPanel(t("bass"), t("low_end"), 0, 12, amount, " dB",
                            t("bass_hint"), decimals=1, art=BassHeadArt())
        else:  # night
            p = SliderPanel(t("night"), t("balance"), 0, 100, amount * 100,
                            "%", t("night_hint"), art=NightBreathArt())

        if key in self.TREBLE_MODES:
            r = engine_mod.TREBLE_RANGE_DB
            p.add_slider_row(t("treble"), -r, r,
                             self._remembered[f"{key}_treble"], " dB", 1,
                             lambda v, k=key: self._on_treble_changed(k, v),
                             signed=True)
        if key == "surround":
            p.add_slider_row(t("clarity"), 0, 10,
                             self._remembered["surround_clarity"], " dB", 1,
                             self._on_surround_clarity,
                             toggle=(bool(self._remembered["surround_clarity_on"]),
                                     lambda on: self._on_extra_toggled(
                                         "surround_clarity", on)))
        p.valueChanged.connect(lambda v, k=key: self._on_amount_changed(k, v))
        self._panel = p
        self.detail_layout.addWidget(p)
        self.detail_holder.setVisible(True)
        self._fit_window(p.height())

    # Panels that show a percentage emit 0-100 while the engine wants 0-1.
    # (SurroundPanel already emits 0-1, and the dB panels emit dB.)
    PERCENT_PANELS = ("ambience", "night")

    def _on_amount_changed(self, key: str, raw: float):
        value = raw / 100.0 if key in self.PERCENT_PANELS else raw
        self._remembered[key] = value
        if self.state.active == key:
            self._apply_amount(key, value)

    def _on_treble_changed(self, key: str, value: float):
        self._remembered[f"{key}_treble"] = value
        if self.state.active == key:
            self.engine.set_treble(value, self.state)

    def _on_surround_clarity(self, value: float):
        self._remembered["surround_clarity"] = value
        if self.state.active == "surround":
            self.engine.set_fidelity(self._effective("surround_clarity"),
                                     self.state)

    def _on_room_changed(self, percent: float):
        self._remembered["surround_room"] = percent / 100.0
        room = self._effective("surround_room")
        self.engine.set_room(room, self.state)
        if self.state.active == "surround":
            self.engine.set_ambience(
                engine_mod.SURROUND_REVERB * self._remembered["surround"] * room,
                self.state)

    def _on_lfe_changed(self, value: float):
        self._remembered["surround_lfe"] = value
        if self.state.active == "surround":
            self.engine.set_lfe(self._effective("surround_lfe"), self.state)

    def _close_panel_widget(self):
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self._panel = None

    def _on_height_step(self, value):
        h = int(value)
        self.detail_holder.setMaximumHeight(max(0, h - self._outer_spacing))
        self.setMinimumHeight(self.BASE_HEIGHT + h)
        self.setMaximumHeight(self.BASE_HEIGHT + h)
        self.resize(self.width(), self.BASE_HEIGHT + h)

    def _fit_window(self, panel_height: int, animate: bool = True):
        """Grow or shrink the window to fit the open mode panel."""
        target = panel_height + self._outer_spacing if panel_height else 0
        self._height_anim.stop()
        if not animate:
            self._on_height_step(target)
            return
        start = max(0, self.height() - self.BASE_HEIGHT)
        if start == target:
            self._on_height_step(target)
            return
        self._height_anim.setStartValue(float(start))
        self._height_anim.setEndValue(float(target))
        self._height_anim.start()

    # -- equaliser / limiter ------------------------------------------------
    def _on_eq_changed(self, index: int, gain: float):
        self.engine.set_eq_band(index, gain, self.state)

    def _on_eq_toggled(self, checked: bool):
        self.eq_btn.setText(t("on") if checked else t("off"))
        self.eq_curve.setEnabled(checked)
        self.engine.set_eq_enabled(checked, self.state)

    def _on_reset_eq(self):
        for i in range(len(EQ_BANDS)):
            self.engine.set_eq_band(i, 0.0, self.state)
        self.eq_curve.setGains(self.state.normalised_eq())

    # -- presets ------------------------------------------------------------
    def _factory_state(self):
        """What a first launch and the Defaults button start from: flat EQ,
        no pre-amp, 3D engaged, and every mode at its DEFAULTS value."""
        state = presets.load_preset("flat")
        state.active = self.DEFAULT_ACTIVE
        state.modes = dict(self.DEFAULTS)
        state.language = i18n.language()
        return state

    def _preset_label(self, key: str) -> str:
        return t(f"preset_{key}") if key in self.BUILTIN_PRESETS else key

    def _fill_presets(self, select: str | None):
        """(Re)build the preset list with names in the current language.
        Each entry carries its file name, which is what gets loaded."""
        self._loading_preset = True
        try:
            self.preset_combo.clear()
            keys = presets.list_presets()
            builtin = [k for k in self.BUILTIN_PRESETS if k in keys]
            own = sorted((k for k in keys if k not in self.BUILTIN_PRESETS),
                         key=str.lower)
            for key in builtin + own:
                self.preset_combo.addItem(self._preset_label(key), key)
            self.preset_combo.setPlaceholderText(t("preset_ph"))
            self.preset_combo.setCurrentIndex(
                self.preset_combo.findData(select) if select else -1)
        finally:
            self._loading_preset = False

    def _on_restore_defaults(self):
        """Back to factory settings -- and forget the remembered session so a
        restart comes up the same way."""
        if QMessageBox.question(self, t("defaults"), t("confirm_defaults")
                                ) != QMessageBox.StandardButton.Yes:
            return
        presets.clear_session()
        self._adopt_state(self._factory_state())
        self.engine.apply_all(self.state)
        self._fill_presets(None)

    def _on_preset_index(self, index: int):
        if self._loading_preset or index < 0:
            return
        self._on_preset_selected(self.preset_combo.itemData(index))

    def _on_preset_selected(self, name: str):
        if not name:
            return
        try:
            loaded = presets.load_preset(name)
        except (FileNotFoundError, TypeError, ValueError) as e:
            QMessageBox.warning(self, "Spatial Linux", f"{t('preset_failed')}\n{e}")
            return
        self._adopt_state(loaded)
        # everything is live-settable, so this needs no restart and no gap
        self.engine.apply_all(self.state)

    def _on_save_preset(self):
        name, ok = QInputDialog.getText(self, t("save_preset"), t("name"))
        name = name.strip()
        if not ok or not name:
            return
        # the name becomes a file name; a slash would point outside the
        # preset folder and a leading dot would hide the file
        if "/" in name or "\\" in name or name.startswith("."):
            QMessageBox.warning(self, "Spatial Linux", t("bad_preset_name"))
            return
        self.state.modes = dict(self._remembered)
        try:
            presets.save_preset(name, self.state)
        except OSError as e:
            QMessageBox.warning(self, "Spatial Linux", f"{t('save_failed')}\n{e}")
            return
        self._fill_presets(name)

    # -- lifecycle ------------------------------------------------------------
    # -- startup / persistence -------------------------------------------------
    # The Flatpak shares its settings with the normal version, so it keeps
    # its own "seen" flag: installing it still plays the intro once.
    INTRO_KEY = "intro_seen_flatpak" if engine_mod.IN_FLATPAK else "intro_seen"

    def _after_show(self):
        if not self.settings.get(self.INTRO_KEY):
            self._show_intro(first_run=True)
        else:
            self._after_intro()

    def _show_intro(self, first_run: bool = False):
        """The introduction, over the whole window: once on the first run,
        and again whenever the i button is pressed."""
        if getattr(self, "_intro", None) is not None:
            return
        self._intro = IntroOverlay(self)
        if first_run:
            self._intro.finished.connect(self._after_intro)
        else:
            self._intro.finished.connect(lambda: setattr(self, "_intro", None))
        self._intro.show()

    def _after_intro(self):
        self._intro = None
        if not self.settings.get(self.INTRO_KEY):
            self.settings[self.INTRO_KEY] = True
            self._save_if_changed()
        if self.settings.get("power") and not self.power_btn.isChecked():
            self.power_btn.click()

    def _snapshot(self):
        self.state.language = i18n.language()
        self.state.modes = dict(self._remembered)
        self.settings["power"] = self.power_btn.isChecked()
        self.settings["volume"] = self.volume_slider.value()
        return json.dumps([asdict(self.state), self.settings], sort_keys=True)

    def _save_if_changed(self):
        snap = self._snapshot()
        if snap != self._saved_snapshot:
            presets.save_session(self.state)
            presets.save_settings(self.settings)
            self._saved_snapshot = snap

    def closeEvent(self, ev):
        self._flush_timer.stop()
        self._autosave.stop()
        self._save_if_changed()
        self.engine.stop()
        super().closeEvent(ev)
