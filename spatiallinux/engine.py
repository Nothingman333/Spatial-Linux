"""Spatial Linux audio engine.

Runs a PipeWire filter-chain as a standalone `pipewire -c <conf>` subprocess
that exposes a virtual sink ("Spatial Linux"). Killing that subprocess makes
PipeWire tear down every node/port/link it owns, so audio returns to exactly
its previous state -- that is why the chain runs as its own process rather
than being loaded into the session daemon.

The graph is an explicit 2-in/2-out stereo graph (not the auto-duplicated
mono graph), because the stereo width stage has to work across channels.
Every user-facing control maps to a control port that can be written at
runtime, so nothing here ever needs a graph rebuild -- no audio gaps, and
loading a preset while playing is seamless.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field

from .ir import generate_reverb_ir, generate_binaural_ir

RUNTIME_DIR = os.path.expanduser("~/.local/share/spatiallinux")
STATE_FILE = os.path.join(RUNTIME_DIR, "engine_state.json")
CONF_PATH = os.path.join(RUNTIME_DIR, "chain.conf")
IR_PATH = os.path.join(RUNTIME_DIR, "ambience_ir.wav")
# Versioned: the file is generated once and then reused, so a change to the
# cue design needs a new name or existing installs would keep the old one.
BINAURAL_IR_PATH = os.path.join(RUNTIME_DIR, "binaural_ir_v3.wav")
# The measured-head version of that file, built once with
# tools/build_ir.py and shipped with the app, so nobody has to install
# NumPy, h5py or libmysofa to get it. HRTF data: MIT KEMAR, Bill Gardner and
# Keith Martin, MIT Media Lab, 1994 -- free to use with this credit.
BUNDLED_BINAURAL_IR = os.path.join(os.path.dirname(__file__), "data",
                                   "binaural_ir.wav")


# Inside a Flatpak the PipeWire tools are the host's, run through
# flatpak-spawn: the sandbox has none of its own, and the host's always match
# the PipeWire that is actually running. The files the chain reads must then
# be ones the host can see too -- the data folder is shared for that.
IN_FLATPAK = bool(os.environ.get("FLATPAK_ID"))
HOST = ["flatpak-spawn", "--host"] if IN_FLATPAK else []


def host_command(args: list[str]) -> list[str]:
    """`args` as it must be run to reach the host's PipeWire tools."""
    return HOST + list(args)


def binaural_ir_path() -> str:
    """The cue file the graph loads: the bundled one when present, else one
    generated on this machine (measured if it can be, analytic if not)."""
    if os.path.exists(BUNDLED_BINAURAL_IR):
        if not IN_FLATPAK:
            return BUNDLED_BINAURAL_IR
        # /app is invisible to the host's pipewire; hand it a shared copy
        copy = os.path.join(RUNTIME_DIR, "binaural_ir_bundled.wav")
        if (not os.path.exists(copy)
                or os.path.getsize(copy) != os.path.getsize(BUNDLED_BINAURAL_IR)):
            os.makedirs(RUNTIME_DIR, exist_ok=True)
            shutil.copyfile(BUNDLED_BINAURAL_IR, copy)
        return copy
    if not os.path.exists(BINAURAL_IR_PATH):
        generate_binaural_ir(BINAURAL_IR_PATH)
    return BINAURAL_IR_PATH

SINK_NAME = "spatiallinux_sink"
SINK_DESCRIPTION = "Spatial Linux"

# Classic 10-band ISO graphic EQ.
EQ_BANDS = [32.0, 63.0, 125.0, 250.0, 500.0,
            1000.0, 2000.0, 4000.0, 8000.0, 16000.0]
EQ_Q = 1.41

BASS_FREQ = 110.0

# Fidelity lifts the frequency bands the ear is least sensitive to -- the
# extremes -- rather than only brightening the top, so it reads as "fuller"
# instead of "hissy". The low side gets less, to avoid muddying the mix.
FIDELITY_HI_FREQ = 7500.0
FIDELITY_LO_FREQ = 90.0
FIDELITY_LO_RATIO = 0.6

# Night mode is about listening without fatigue, so raising it takes energy
# OUT of the two ranges that tire the ear -- boomy low end and hard upper
# mids / sibilant treble -- while a power-law shaper (see _build_graph)
# lifts quiet detail so nothing is lost by turning it down. Everything below
# scales with the one slider.
NIGHT_SHAPE_DEPTH = 0.20     # exponent p = 1 - depth * amount
NIGHT_FLOOR_LOG2 = -13.0     # ~-78 dBFS; keeps log2(0) = -inf out of the graph
# The tone shaping is a curve over the equaliser bands themselves: raising
# the slider pulls whatever the user has set progressively further down,
# hardest through the midrange where the ear tires first and gentlest at the
# very top and bottom. At 0 it adds nothing.
NIGHT_EQ_CURVE = [-9.9, -12.0, -12.0, -12.0, -12.0,
                  -12.0, -12.0, -12.0, -11.8, -4.8]
# Night mode deliberately does NOT lower the limiter ceiling. It used to,
# and the compressor's make-up gain then drove the signal straight into that
# lower clamp: measured at 10% total harmonic distortion, which is precisely
# the harsh edge this mode is supposed to remove. The compression already
# brings peaks down; clamping them again only breaks them.
# The shaper on its own lifts everything, which would make night mode louder
# -- the opposite of restful. Pivoting it about a reference level keeps that
# level put, so quiet detail still rises while loud peaks genuinely fall.
NIGHT_PIVOT = 0.25           # ~-12 dBFS
# The gain must follow the ENVELOPE, not the waveform. Applying the power law
# to individual samples is waveshaping: measured at 8.7% total harmonic
# distortion, which is exactly the hard, scratchy edge it used to have.
# Smoothing the level estimate below the audio band first makes the gain vary
# slowly, so the multiply is clean compression instead of distortion.
NIGHT_ENVELOPE_FREQ = 30.0

# 3D Surround. Two stages:
#
#  1. Frequency-dependent mid/side width. Only the side signal above
#     SURROUND_BASS_SPLIT is widened; below it the side passes through
#     untouched, so bass stays centred instead of going hollow and phasey.
#  2. Binaural rendering. Each input channel is convolved with a synthesised
#     head model (see ir.generate_binaural_ir) that supplies what the ears
#     would actually receive from a pair of speakers in a room: the far ear
#     gets the sound an interaural delay late, quieter and with the highs
#     shadowed by the head, and both ears get early room reflections. Those
#     cues are what let the brain place the sound outside the head.
#
#     Only the *cues* are convolved -- the direct sound stays dry -- so at
#     zero the stage is bit-transparent, and raising it only ever adds later
#     arrivals, never a comb filter on the original signal.
SURROUND_BASS_SPLIT = 200.0
# Kept deliberately small: mid/side widening writes the opposite polarity
# into the other channel, which partly cancels the binaural cross-feed
# below. The head model does the spatial work; width only seasons it.
SURROUND_MAX_WIDTH = 1.20     # width = 1 + amount * this
SURROUND_MAX_CUE = 1.0        # how much of the head model is mixed in

# There used to be a +2.5 dB "air" shelf at 9 kHz here, to make up for the
# head shadow darkening the image. Measured, the image was never dark -- the
# direct sound stays dry and full-range -- so the shelf only tilted the top
# up (+2.6 dB at 16 kHz at full intensity) and made the treble sound harsh.

# The cues add energy, and on a loud master the extra peaks ran up to +4 dBFS
# into the limiter, whose hard clamp turned them into a faint crackle in the
# treble. The 3D path therefore trims itself as it rises; at this depth the
# peaks of a modern loud master stay at or below where they went in.
SURROUND_HEADROOM_DB = 4.0     # trim at full intensity, scaled by the amount

# A touch of the room, folded into the 3D mode itself. Far too little to
# hear as reverb -- just enough to stop the image sounding anechoic.
SURROUND_REVERB = 0.03

# LFE / subwoofer trim available while 3D Surround is engaged.
SURROUND_LFE_FREQ = 90.0

# Treble trim offered by the 3D and Ambience panels. It sits after the
# reverb, so in Ambience it shapes the room's tail too.
TREBLE_FREQ = 5000.0
TREBLE_RANGE_DB = 6.0

LIMITER_CEILING = 1.0
LIMITER_OFF = 10.0     # clamp wide enough to be a pass-through

CHANNELS = ("L", "R")
OPPOSITE = {"L": "R", "R": "L"}


@dataclass
class EngineState:
    preamp: float = 0.0       # dB, -12..+12
    eq: list = field(default_factory=lambda: [0.0] * len(EQ_BANDS))
    bass: float = 0.0         # dB, 0..12
    fidelity: float = 0.0     # dB, 0..10
    surround: float = 0.0     # 0..1 3D width + binaural cue depth
    lfe: float = 0.0          # dB, subwoofer trim used with 3D
    ambience: float = 0.0     # 0..1 reverb wet amount
    treble: float = 0.0       # dB, -6..+6, set by the 3D / Ambience panels
    room: float = 1.0         # 0..1 how much of 3D's rear speakers and room
    eq_enabled: bool = True   # False bypasses the user's EQ (night curve stays)
    night: float = 0.0        # 0..1 night-mode strength
    limiter: bool = True
    active: str | None = None  # which single effect is engaged, if any
    language: str = ""         # interface language, remembered per session
    # every mode's last value, not just the active one's, so switching
    # modes after a restart or a preset load comes back where it was left
    modes: dict = field(default_factory=dict)

    def __post_init__(self):
        # Night mode used to be a checkbox; presets saved then still load.
        if isinstance(self.night, bool):
            self.night = 0.6 if self.night else 0.0

    def normalised_eq(self) -> list:
        """EQ list padded/truncated to the current band count, so presets
        written against an older band layout still load."""
        vals = list(self.eq or [])
        if len(vals) < len(EQ_BANDS):
            vals += [0.0] * (len(EQ_BANDS) - len(vals))
        return vals[:len(EQ_BANDS)]


# The command-line tools the engine drives. A missing one used to raise
# straight out of the window's constructor, so the app did not open at all.
REQUIRED_TOOLS = ("pipewire", "pw-cli", "pw-dump", "pw-metadata", "wpctl")


def missing_tools() -> list[str]:
    if not IN_FLATPAK:
        return [t for t in REQUIRED_TOOLS if shutil.which(t) is None]
    if shutil.which("flatpak-spawn") is None:
        return ["flatpak-spawn"]
    out = _run("sh", "-c", " ".join(
        f"command -v {t} >/dev/null || echo {t};" for t in REQUIRED_TOOLS))
    return [t for t in out.stdout.split() if t]


def _run(*args, **kw):
    """Run a command; a missing or failing tool gives an empty result rather
    than an exception, so one absent utility cannot take the app down."""
    try:
        return subprocess.run(host_command(args), capture_output=True,
                              text=True, **kw)
    except OSError:
        return subprocess.CompletedProcess(args, 127, "", "")


def _sh(cmd: list[str]) -> str:
    return _run(*cmd).stdout.strip()


def _pw_dump_objects() -> list:
    """pw-dump can emit a trailing JSON value after the main array when the
    graph mutates mid-dump; decode only the first complete value."""
    text = _sh(["pw-dump"])
    if not text:
        return []
    try:
        obj, _ = json.JSONDecoder().raw_decode(text)
        return obj if isinstance(obj, list) else []
    except json.JSONDecodeError:
        return []


def _db_to_lin(db: float) -> float:
    return 10.0 ** (db / 20.0)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _width_from_surround(amount: float) -> float:
    """0 -> 1.0 (transparent), 1 -> widest."""
    return 1.0 + _clamp01(amount) * SURROUND_MAX_WIDTH


def _surround_gains(amount: float) -> tuple[float, float]:
    """(direct, cue) gains for the 3D mixer: the cue depth, and the headroom
    trim that keeps the added energy out of the limiter."""
    a = _clamp01(amount)
    trim = _db_to_lin(-SURROUND_HEADROOM_DB * a)
    return trim, a * SURROUND_MAX_CUE * trim


def _night_eq(state: "EngineState") -> list:
    """The band gains actually sent to the graph: what the user dialled in,
    plus the night-mode curve scaled by its slider."""
    n = _clamp01(state.night)
    user = (state.normalised_eq() if state.eq_enabled
            else [0.0] * len(EQ_BANDS))
    return [g + NIGHT_EQ_CURVE[i] * n for i, g in enumerate(user)]


def _night_exponent(amount: float) -> float:
    """Power-law exponent for the night-mode shaper. 1.0 is transparent;
    below 1.0 lifts quiet material more than loud material."""
    return 1.0 - _clamp01(amount) * NIGHT_SHAPE_DEPTH


def _night_makeup(amount: float) -> float:
    """Gain that pins the shaper at NIGHT_PIVOT, so the overall level stays
    where it was and the compression works in both directions."""
    return NIGHT_PIVOT ** (1.0 - _night_exponent(amount))


class SpatialEngine:
    def __init__(self):
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        self.proc: subprocess.Popen | None = None
        self.sink_id: int | None = None
        self._prev_default_name: str | None = None
        self._prev_default_desc: str | None = None
        # whether that previous default was one the user picked by hand;
        # if not, it was the session manager's own choice and the right way
        # to give it back is to clear ours, not to pin theirs
        self._prev_configured = False
        # Live control changes are gathered here and sent together (see
        # flush); `defer`, when set by the interface, schedules that flush.
        self._pending: dict = {}
        self._pending_volume: float | None = None
        # per-app stream changes for the mixer: {node id: volume %} and
        # {node id: muted}; these work whether the engine is on or not
        self._pending_streams: dict[int, float] = {}
        self._pending_mutes: dict[int, bool] = {}
        self.defer = None
        self._recover_from_previous_crash()

    # -- crash safety -----------------------------------------------------
    def _recover_from_previous_crash(self):
        for line in _sh(["pgrep", "-af", "pipewire -c " + CONF_PATH]).splitlines():
            try:
                pid = int(line.split()[0])
                if IN_FLATPAK:                   # a host process: kill it there
                    _run("kill", "-TERM", str(pid))
                else:
                    os.kill(pid, signal.SIGTERM)
            except (ValueError, IndexError, ProcessLookupError):
                pass

        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE) as f:
                    saved = json.load(f)
                self._give_back_default(saved.get("prev_default_name"),
                                        saved.get("prev_configured", True))
            except Exception:
                pass
            finally:
                try:
                    os.remove(STATE_FILE)
                except OSError:
                    pass

    # -- default sink bookkeeping ------------------------------------------
    def _current_default_sink_name(self) -> str | None:
        return self._current_default_sink()[0]

    def _current_default_sink(self) -> tuple[str | None, bool]:
        """(name, chosen_by_hand) of the default output."""
        """The sink audio goes to by default. `default.configured.audio.sink`
        only exists once someone has picked a device by hand; on a system
        where nobody ever has, only the session manager's own choice,
        `default.audio.sink`, is there -- and reading just the first made
        the output show as unknown."""
        found = {}
        for line in _sh(["pw-metadata", "-n", "default"]).splitlines():
            for key in ("default.configured.audio.sink", "default.audio.sink"):
                if f"key:'{key}'" in line and "value:" in line:
                    try:
                        raw = (line.split("value:", 1)[1].split("type:")[0]
                               .strip().strip("'"))
                        found[key] = json.loads(raw).get("name")
                    except Exception:
                        pass
        configured = found.get("default.configured.audio.sink")
        return (configured or found.get("default.audio.sink"),
                configured is not None)

    def _find_node_id_by_name(self, name: str) -> int | None:
        for o in _pw_dump_objects():
            props = (o.get("info") or {}).get("props") or {}
            if props.get("node.name") == name:
                return o["id"]
        return None

    def _restore_default_sink_by_name(self, name: str):
        node_id = self._find_node_id_by_name(name)
        if node_id is not None:
            _run("wpctl", "set-default", str(node_id))

    def _give_back_default(self, name: str | None, configured: bool):
        """Return the default output to what it was before we took it. If
        the user had picked it by hand, pick it again; if the session manager
        had chosen it, clear our choice so it chooses again -- restoring it
        by name would turn its automatic choice into a manual one, a change
        to the user's settings that would outlive the app."""
        if name and configured:
            self._restore_default_sink_by_name(name)
        else:
            _run("wpctl", "clear-default")

    def _describe_sink(self, name: str | None) -> str | None:
        if not name:
            return None
        for o in _pw_dump_objects():
            props = (o.get("info") or {}).get("props") or {}
            if props.get("node.name") == name:
                return props.get("node.description") or props.get("node.nick") or name
        return None

    def current_output_label(self) -> str | None:
        """Where audio physically ends up. While the engine runs the real
        device is no longer the default sink, so we report the description
        captured at start-up rather than re-resolving it (the lookup can race
        with the default-sink switch and fall back to the raw node name).
        None when it cannot be told; the interface words that itself."""
        if self.running:
            return self._prev_default_desc or self._prev_default_name
        name = self._current_default_sink_name()
        return self._describe_sink(name) or name

    # -- graph construction -------------------------------------------------
    def _build_graph(self, state: EngineState) -> dict:
        nodes, links = [], []
        n = _clamp01(state.night)
        eq_gains = _night_eq(state)
        lo, hi = self._clamp_range(state)
        width = _width_from_surround(state.surround)
        direct, cue = _surround_gains(state.surround)
        dry, wet = self._ambience_mix(state)

        def link(a, b):
            links.append({"output": a, "input": b})

        # ---- per-channel tone chain -------------------------------------
        chain_out = {}
        for ch in CHANNELS:
            seq = []
            nodes.append({"type": "builtin", "name": f"pre{ch}", "label": "linear",
                          "control": {"Mult": _db_to_lin(state.preamp), "Add": 0.0}})
            seq.append(f"pre{ch}")

            for i, (freq, gain) in enumerate(zip(EQ_BANDS, eq_gains)):
                name = f"b{i}{ch}"
                nodes.append({"type": "builtin", "name": name, "label": "bq_peaking",
                              "control": {"Freq": freq, "Q": EQ_Q, "Gain": gain}})
                seq.append(name)

            nodes.append({"type": "builtin", "name": f"bass{ch}", "label": "bq_lowshelf",
                          "control": {"Freq": BASS_FREQ, "Q": 0.7, "Gain": state.bass}})
            seq.append(f"bass{ch}")

            nodes.append({"type": "builtin", "name": f"fid{ch}", "label": "bq_highshelf",
                          "control": {"Freq": FIDELITY_HI_FREQ, "Q": 0.7,
                                      "Gain": state.fidelity}})
            seq.append(f"fid{ch}")

            nodes.append({"type": "builtin", "name": f"fidlo{ch}", "label": "bq_lowshelf",
                          "control": {"Freq": FIDELITY_LO_FREQ, "Q": 0.7,
                                      "Gain": state.fidelity * FIDELITY_LO_RATIO}})
            seq.append(f"fidlo{ch}")

            for a, b in zip(seq, seq[1:]):
                link(f"{a}:Out", f"{b}:In")
            chain_out[ch] = f"{seq[-1]}:Out"

        # ---- 3D Surround, stage 1: bass-preserving mid/side width --------
        # Only the *added* width is filtered, never the original side signal:
        #
        #   side_out = side + highpass(side * (width - 1))
        #
        # At width 1 the added term is exactly zero, so the stage is
        # bit-transparent; above it, the extra width is high-passed and the
        # bass stays where it was. Splitting the side signal instead and
        # scaling the upper half does not work -- no split is sharp enough,
        # and at the widths this mode now reaches the leftover low end came
        # through hard enough to hollow out the bass.
        nodes += [
            {"type": "builtin", "name": "mid", "label": "mixer",
             "control": {"Gain 1": 0.5, "Gain 2": 0.5}},
            {"type": "builtin", "name": "invR", "label": "invert"},
            {"type": "builtin", "name": "side", "label": "mixer",
             "control": {"Gain 1": 0.5, "Gain 2": 0.5}},
            {"type": "builtin", "name": "wid", "label": "linear",
             "control": {"Mult": width - 1.0, "Add": 0.0}},
            {"type": "builtin", "name": "sdhp", "label": "bq_highpass",
             "control": {"Freq": SURROUND_BASS_SPLIT, "Q": 0.707, "Gain": 0.0}},
            {"type": "builtin", "name": "sdm", "label": "mixer",
             "control": {"Gain 1": 1.0, "Gain 2": 1.0}},
            {"type": "builtin", "name": "invS", "label": "invert"},
            {"type": "builtin", "name": "wL", "label": "mixer",
             "control": {"Gain 1": 1.0, "Gain 2": 1.0}},
            {"type": "builtin", "name": "wR", "label": "mixer",
             "control": {"Gain 1": 1.0, "Gain 2": 1.0}},
        ]
        link(chain_out["L"], "mid:In 1")
        link(chain_out["R"], "mid:In 2")
        link(chain_out["L"], "side:In 1")
        link(chain_out["R"], "invR:In")
        link("invR:Out", "side:In 2")
        link("side:Out", "wid:In")          # the added width only
        link("wid:Out", "sdhp:In")
        link("side:Out", "sdm:In 1")        # the original side, untouched
        link("sdhp:Out", "sdm:In 2")
        link("sdm:Out", "invS:In")
        link("mid:Out", "wL:In 1")
        link("sdm:Out", "wL:In 2")
        link("mid:Out", "wR:In 1")
        link("invS:Out", "wR:In 2")

        # ---- 3D Surround, stage 2: binaural head model -------------------
        # Six convolutions (layout in ir.generate_binaural_ir): each input
        # across the head to the far ear, plus the rear speakers and room
        # kept separate so the Reverb slider can scale them on their own.
        for name, source, channel in (("fLR", "L", 0), ("fRL", "R", 1),
                                      ("rLR", "L", 2), ("rLL", "L", 3),
                                      ("rRL", "R", 4), ("rRR", "R", 5)):
            nodes.append({
                "type": "builtin", "name": name, "label": "convolver",
                "config": {"filename": binaural_ir_path(), "channel": channel,
                           "gain": 1.0},
            })
            link(f"w{source}:Out", f"{name}:In")

        # sum the cues arriving at each ear, then add them to the dry signal
        room = _clamp01(state.room)
        for ear, own, other, front in (("L", "rLL", "rRL", "fRL"),
                                       ("R", "rRR", "rLR", "fLR")):
            nodes.append({"type": "builtin", "name": f"cue{ear}",
                          "label": "mixer",
                          "control": {"Gain 1": room, "Gain 2": room,
                                      "Gain 3": 1.0}})
            link(f"{own}:Out", f"cue{ear}:In 1")     # rear + room, own side
            link(f"{other}:Out", f"cue{ear}:In 2")   # rear, other side
            link(f"{front}:Out", f"cue{ear}:In 3")   # across the head

        for ch in CHANNELS:
            nodes.append({
                "type": "builtin", "name": f"sr{ch}", "label": "mixer",
                "control": {"Gain 1": direct, "Gain 2": cue},
            })
            link(f"w{ch}:Out", f"sr{ch}:In 1")
            link(f"cue{ch}:Out", f"sr{ch}:In 2")

        # LFE trim, belonging to the 3D mode
        for ch in CHANNELS:
            nodes.append({
                "type": "builtin", "name": f"lfe{ch}", "label": "bq_lowshelf",
                "control": {"Freq": SURROUND_LFE_FREQ, "Q": 0.7,
                            "Gain": state.lfe},
            })
            link(f"sr{ch}:Out", f"lfe{ch}:In")

        # ---- ambience (convolution reverb, wet/dry via mixer gains) ------
        for idx, ch in enumerate(CHANNELS):
            src = f"lfe{ch}:Out"
            nodes.append({
                "type": "builtin", "name": f"cv{ch}", "label": "convolver",
                "config": {"filename": IR_PATH, "channel": idx, "gain": 1.0},
            })
            nodes.append({
                "type": "builtin", "name": f"am{ch}", "label": "mixer",
                "control": {"Gain 1": dry, "Gain 2": wet},
            })
            link(src, f"cv{ch}:In")
            link(src, f"am{ch}:In 1")
            link(f"cv{ch}:Out", f"am{ch}:In 2")

        # ---- treble trim (3D / Ambience panels) -------------------------
        for ch in CHANNELS:
            nodes.append({"type": "builtin", "name": f"tre{ch}",
                          "label": "bq_highshelf",
                          "control": {"Freq": TREBLE_FREQ, "Q": 0.7,
                                      "Gain": state.treble}})
            link(f"am{ch}:Out", f"tre{ch}:In")

        # ---- night mode compressor --------------------------------------
        # log2|x| -> clamp -> smooth -> scale by (p-1) -> exp2 gives a gain
        # that tracks the signal's level rather than its waveform; multiplying
        # the signal by it restores the sign for free. The clamp keeps
        # log2(0) = -inf out of the multiply (inf * 0 would be NaN).
        p = _night_exponent(state.night)
        for ch in CHANNELS:
            src = f"tre{ch}:Out"
            nodes += [
                {"type": "builtin", "name": f"nlg{ch}", "label": "log",
                 "control": {"Base": 2.0, "M1": 1.0, "M2": 1.0}},
                {"type": "builtin", "name": f"ncl{ch}", "label": "clamp",
                 "control": {"Min": NIGHT_FLOOR_LOG2, "Max": 0.0}},
                {"type": "builtin", "name": f"nlp{ch}", "label": "bq_lowpass",
                 "control": {"Freq": NIGHT_ENVELOPE_FREQ, "Q": 0.707, "Gain": 0.0}},
                {"type": "builtin", "name": f"nsc{ch}", "label": "linear",
                 "control": {"Mult": p - 1.0, "Add": 0.0}},
                {"type": "builtin", "name": f"nex{ch}", "label": "exp",
                 "control": {"Base": 2.0}},
                {"type": "builtin", "name": f"nml{ch}", "label": "mult"},
            ]
            link(src, f"nlg{ch}:In")
            link(f"nlg{ch}:Out", f"ncl{ch}:In")
            link(f"ncl{ch}:Out", f"nlp{ch}:In")
            link(f"nlp{ch}:Out", f"nsc{ch}:In")
            link(f"nsc{ch}:Out", f"nex{ch}:In")
            link(src, f"nml{ch}:In 1")
            link(f"nex{ch}:Out", f"nml{ch}:In 2")

            nodes.append({"type": "builtin", "name": f"ngc{ch}", "label": "linear",
                          "control": {"Mult": _night_makeup(state.night),
                                      "Add": 0.0}})
            link(f"nml{ch}:Out", f"ngc{ch}:In")

            nodes.append({"type": "builtin", "name": f"lim{ch}", "label": "clamp",
                          "control": {"Min": lo, "Max": hi}})
            link(f"ngc{ch}:Out", f"lim{ch}:In")

        return {
            "nodes": nodes,
            "links": links,
            "inputs": [f"pre{ch}:In" for ch in CHANNELS],
            "outputs": [f"lim{ch}:Out" for ch in CHANNELS],
        }

    @staticmethod
    def _clamp_range(state: EngineState) -> tuple[float, float]:
        if state.limiter:
            return (-LIMITER_CEILING, LIMITER_CEILING)
        return (-LIMITER_OFF, LIMITER_OFF)

    @staticmethod
    def _ambience_mix(state: EngineState) -> tuple[float, float]:
        """Dry/wet split. The wet coefficient is calibrated (by measuring the
        convolver's output level against its input) so that fully wet lands
        at roughly unity overall rather than overloading the limiter."""
        a = max(0.0, min(1.0, state.ambience))
        return (1.0 - 0.5 * a, a * 0.15)

    def _build_conf(self, state: EngineState) -> str:
        args = {
            "node.description": SINK_DESCRIPTION,
            "media.name": SINK_DESCRIPTION,
            "filter.graph": self._build_graph(state),
            "capture.props": {
                "node.name": SINK_NAME,
                "node.description": SINK_DESCRIPTION,
                "media.class": "Audio/Sink",
                "audio.channels": 2,
                "audio.position": ["FL", "FR"],
            },
            "playback.props": {
                "node.name": f"{SINK_NAME}.playback",
                "node.passive": True,
                "audio.channels": 2,
                "audio.position": ["FL", "FR"],
            },
        }
        return f"""\
context.properties = {{
    log.level = 2
}}
context.spa-libs = {{
    audio.convert.* = audioconvert/libspa-audioconvert
    support.*       = support/libspa-support
}}
context.modules = [
    {{ name = libpipewire-module-protocol-native }}
    {{ name = libpipewire-module-client-node }}
    {{ name = libpipewire-module-adapter }}
    {{ name = libpipewire-module-filter-chain
        args = {json.dumps(args)}
    }}
]
"""

    # -- lifecycle ------------------------------------------------------
    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, state: EngineState):
        if self.running:
            self.stop()

        if not os.path.exists(IR_PATH):
            generate_reverb_ir(IR_PATH)

        self._pending.clear()
        self._pending_volume = None
        prev_name, prev_configured = self._current_default_sink()
        if prev_name == SINK_NAME:
            # A previous run was killed before it could restore the default,
            # leaving it pointing at our own (now gone) sink. Recording that
            # as "previous" would make stop() restore a broken default, so
            # fall back to letting the session manager pick.
            prev_name = None
        self._prev_default_name = prev_name
        self._prev_configured = prev_configured and prev_name is not None
        # resolve the friendly name now, while it is still the default sink
        self._prev_default_desc = self._describe_sink(prev_name)
        with open(STATE_FILE, "w") as f:
            json.dump({"prev_default_name": prev_name,
                       "prev_configured": self._prev_configured}, f)

        with open(CONF_PATH, "w") as f:
            f.write(self._build_conf(state))

        # (in a Flatpak, flatpak-spawn passes our terminate() on to the host
        # process, so stopping works the same way)
        self.proc = subprocess.Popen(
            host_command(["pipewire", "-c", CONF_PATH]),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self.sink_id = None
        for _ in range(60):
            if self.proc.poll() is not None:
                self.proc = None
                raise RuntimeError("filter-chain process exited immediately")
            sid = self._find_node_id_by_name(SINK_NAME)
            if sid is not None:
                self.sink_id = sid
                break
            time.sleep(0.1)

        if self.sink_id is None:
            self.stop()
            raise RuntimeError("the Spatial Linux sink never appeared")

        _run("wpctl", "set-default", str(self.sink_id))

    def stop(self):
        self._pending.clear()
        self._pending_volume = None
        if self._prev_default_name or self.sink_id is not None:
            # With no known previous device, clearing lets the session
            # manager re-pick real hardware instead of staying pinned to the
            # sink we are about to destroy.
            self._give_back_default(self._prev_default_name,
                                    self._prev_configured)
        self._prev_default_name = None
        self._prev_default_desc = None
        self._prev_configured = False

        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                try:
                    self.proc.wait(timeout=3)
                except Exception:
                    pass
            except Exception:
                pass
            self.proc = None

        self.sink_id = None
        if os.path.exists(STATE_FILE):
            try:
                os.remove(STATE_FILE)
            except OSError:
                pass

    # -- live control updates (never needs a rebuild) --------------------
    # A Props update carries its parameters in a fixed-size POD, and past
    # roughly 25 of them the whole message is dropped -- pw-cli still exits 0,
    # so the failure is completely silent. That is what made loading a preset
    # change the interface without changing the sound. Chunking keeps every
    # message well inside the limit.
    MAX_PARAMS_PER_CALL = 16

    # Every change used to be its own pw-cli process: dragging one slider
    # started over a hundred of them, each blocking the interface for a few
    # milliseconds. Changes are now merged (the latest value of each control
    # wins) and sent together when the interface calls flush(), at most a few
    # dozen times a second. Without `defer` they are sent at once.
    def _set_props(self, params: dict):
        if self.sink_id is None:
            return
        self._pending.update(params)
        if self.defer is not None:
            self.defer()
        else:
            self.flush()

    def flush(self):
        """Send everything gathered since the last flush."""
        for node, pct in self._pending_streams.items():
            _run("wpctl", "set-volume", str(node), f"{pct / 100:.3f}")
        for node, muted in self._pending_mutes.items():
            _run("wpctl", "set-mute", str(node), "1" if muted else "0")
        self._pending_streams.clear()
        self._pending_mutes.clear()
        if self.sink_id is None:
            self._pending.clear()
            self._pending_volume = None
            return
        if self._pending_volume is not None:
            _run("wpctl", "set-volume", str(self.sink_id),
                 f"{self._pending_volume / 100:.3f}")
            self._pending_volume = None
        items = list(self._pending.items())
        self._pending.clear()
        for start in range(0, len(items), self.MAX_PARAMS_PER_CALL):
            chunk = items[start:start + self.MAX_PARAMS_PER_CALL]
            body = " ".join(f'"{k}" {v}' for k, v in chunk)
            _run("pw-cli", "set-param", str(self.sink_id), "Props",
                 "{ params = [ " + body + " ] }")

    def set_preamp(self, db: float, state: EngineState | None = None):
        if state is not None:
            state.preamp = db
        self._set_props({f"pre{ch}:Mult": _db_to_lin(db) for ch in CHANNELS})

    def set_eq_band(self, index: int, gain_db: float, state: EngineState | None = None):
        if state is not None:
            eq = state.normalised_eq()
            eq[index] = gain_db
            state.eq = eq
            gain_db = _night_eq(state)[index]
        self._set_props({f"b{index}{ch}:Gain": gain_db for ch in CHANNELS})

    def set_bass(self, gain_db: float, state: EngineState | None = None):
        if state is not None:
            state.bass = gain_db
        self._set_props({f"bass{ch}:Gain": gain_db for ch in CHANNELS})

    def set_fidelity(self, gain_db: float, state: EngineState | None = None):
        if state is not None:
            state.fidelity = gain_db
        self._set_props({f"fid{ch}:Gain": gain_db for ch in CHANNELS} |
                        {f"fidlo{ch}:Gain": gain_db * FIDELITY_LO_RATIO
                         for ch in CHANNELS})

    def set_surround(self, amount: float, state: EngineState | None = None):
        if state is not None:
            state.surround = amount
        direct, cue = _surround_gains(amount)
        self._set_props({"wid:Mult": _width_from_surround(amount) - 1.0} |
                        {f"sr{ch}:Gain 1": direct for ch in CHANNELS} |
                        {f"sr{ch}:Gain 2": cue for ch in CHANNELS})

    def set_treble(self, gain_db: float, state: EngineState | None = None):
        gain_db = max(-TREBLE_RANGE_DB, min(TREBLE_RANGE_DB, gain_db))
        if state is not None:
            state.treble = gain_db
        self._set_props({f"tre{ch}:Gain": gain_db for ch in CHANNELS})

    def set_room(self, amount: float, state: EngineState | None = None):
        amount = _clamp01(amount)
        if state is not None:
            state.room = amount
        self._set_props({f"cue{ch}:Gain {i}": amount
                         for ch in CHANNELS for i in (1, 2)})

    def set_eq_enabled(self, enabled: bool, state: EngineState):
        state.eq_enabled = enabled
        self._set_props({f"b{i}{ch}:Gain": g
                         for ch in CHANNELS for i, g in enumerate(_night_eq(state))})

    def set_lfe(self, gain_db: float, state: EngineState | None = None):
        if state is not None:
            state.lfe = gain_db
        self._set_props({f"lfe{ch}:Gain": gain_db for ch in CHANNELS})

    def set_ambience(self, amount: float, state: EngineState | None = None):
        if state is not None:
            state.ambience = amount
        probe = state if state is not None else EngineState(ambience=amount)
        dry, wet = self._ambience_mix(probe)
        self._set_props({f"am{ch}:Gain 1": dry for ch in CHANNELS} |
                        {f"am{ch}:Gain 2": wet for ch in CHANNELS})

    def set_night(self, amount: float, state: EngineState):
        state.night = _clamp01(amount)
        n = state.night
        lo, hi = self._clamp_range(state)
        params = {f"b{i}{ch}:Gain": g
                  for ch in CHANNELS for i, g in enumerate(_night_eq(state))}
        params |= {f"nsc{ch}:Mult": _night_exponent(n) - 1.0 for ch in CHANNELS}
        params |= {f"ngc{ch}:Mult": _night_makeup(n) for ch in CHANNELS}
        params |= {f"lim{ch}:Min": lo for ch in CHANNELS}
        params |= {f"lim{ch}:Max": hi for ch in CHANNELS}
        self._set_props(params)

    def set_limiter(self, enabled: bool, state: EngineState):
        state.limiter = enabled
        lo, hi = self._clamp_range(state)
        self._set_props({f"lim{ch}:Min": lo for ch in CHANNELS} |
                        {f"lim{ch}:Max": hi for ch in CHANNELS})

    def apply_all(self, state: EngineState):
        """Push an entire state to a running graph -- used when loading a
        preset, so it takes effect without restarting (and without a gap)."""
        if self.sink_id is None:
            return
        n = _clamp01(state.night)
        dry, wet = self._ambience_mix(state)
        lo, hi = self._clamp_range(state)
        direct, cue = _surround_gains(state.surround)

        params: dict = {"wid:Mult": _width_from_surround(state.surround) - 1.0}
        for ch in CHANNELS:
            params[f"pre{ch}:Mult"] = _db_to_lin(state.preamp)
            for i, g in enumerate(_night_eq(state)):
                params[f"b{i}{ch}:Gain"] = g
            params[f"bass{ch}:Gain"] = state.bass
            params[f"fid{ch}:Gain"] = state.fidelity
            params[f"fidlo{ch}:Gain"] = state.fidelity * FIDELITY_LO_RATIO
            params[f"nsc{ch}:Mult"] = _night_exponent(n) - 1.0
            params[f"ngc{ch}:Mult"] = _night_makeup(n)
            params[f"sr{ch}:Gain 1"] = direct
            params[f"sr{ch}:Gain 2"] = cue
            params[f"lfe{ch}:Gain"] = state.lfe
            params[f"tre{ch}:Gain"] = state.treble
            params[f"cue{ch}:Gain 1"] = _clamp01(state.room)
            params[f"cue{ch}:Gain 2"] = _clamp01(state.room)
            params[f"am{ch}:Gain 1"] = dry
            params[f"am{ch}:Gain 2"] = wet
            params[f"lim{ch}:Min"] = lo
            params[f"lim{ch}:Max"] = hi
        self._set_props(params)

    # -- volume ------------------------------------------------------------
    def set_volume(self, pct: float):
        if self.sink_id is None:
            return
        self._pending_volume = max(0.0, min(150.0, pct))
        if self.defer is not None:
            self.defer()
        else:
            self.flush()

    # -- per-app volumes (the mixer) ----------------------------------------
    def set_stream_volume(self, node_id: int, pct: float):
        self._pending_streams[node_id] = max(0.0, min(150.0, pct))
        self._request_flush()

    def set_stream_mute(self, node_id: int, muted: bool):
        self._pending_mutes[node_id] = muted
        self._request_flush()

    def _request_flush(self):
        if self.defer is not None:
            self.defer()
        else:
            self.flush()

    def get_volume(self) -> int | None:
        if self.sink_id is None:
            return None
        out = _sh(["wpctl", "get-volume", str(self.sink_id)])
        try:
            return int(round(float(out.split()[1].replace(",", ".")) * 100))
        except Exception:
            return None


def parse_streams(objects: list) -> list[dict]:
    """The apps currently playing sound, from a pw-dump listing.

    Each is {id, app, media, volume, muted}, volume in percent on the same
    scale desktop mixers and wpctl use. PipeWire stores stream volumes
    linearly; mixers show their cube root, so that is taken here. Spatial
    Linux's own nodes are left out."""
    streams = []
    for o in objects:
        if o.get("type") != "PipeWire:Interface:Node":
            continue
        info = o.get("info") or {}
        props = info.get("props") or {}
        if props.get("media.class") != "Stream/Output/Audio":
            continue
        name = props.get("node.name") or ""
        if name.startswith(SINK_NAME):
            continue
        volume, muted = 100.0, False
        for p in (info.get("params") or {}).get("Props") or []:
            vols = p.get("channelVolumes")
            if vols:
                linear = sum(vols) / len(vols)
                volume = round(max(0.0, linear) ** (1.0 / 3.0) * 100.0)
                muted = bool(p.get("mute", False))
                break
        streams.append({
            "id": o.get("id"),
            "app": (props.get("application.name") or props.get("node.description")
                    or name or "?"),
            "media": props.get("media.name") or "",
            "volume": volume,
            "muted": muted,
        })
    streams.sort(key=lambda s: (s["app"].lower(), s["id"]))
    return streams
