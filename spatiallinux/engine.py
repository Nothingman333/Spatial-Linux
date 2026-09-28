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
import threading
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


DATA_DIR = os.path.dirname(BUNDLED_BINAURAL_IR)

# The measured heads the 3D stage can use: (cue file, surround file), both
# built by tools/build_ir.py. SADIE II subject D1 (a Neumann KU 100 dummy
# head): Cal Armstrong, Lewis Thresh and Gavin Kearney, University of York,
# Apache License 2.0; taken from the copy OpenAL Soft ships.
HEADS = {
    "kemar": ("binaural_ir.wav", "surround_ir_kemar.wav"),
    "sadie": ("binaural_ir_sadie.wav", "surround_ir_sadie.wav"),
}
DEFAULT_HEAD = "kemar"


def _data_file(name: str) -> str:
    """A bundled file, where the host's pipewire can read it: /app is
    invisible to it from inside the Flatpak, so there it gets a shared
    copy."""
    path = os.path.join(DATA_DIR, name)
    if not IN_FLATPAK:
        return path
    copy = os.path.join(RUNTIME_DIR, "bundled_" + name)
    if (not os.path.exists(copy)
            or os.path.getsize(copy) != os.path.getsize(path)):
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        shutil.copyfile(path, copy)
    return copy


def binaural_ir_path() -> str:
    """The default head's cue file: the bundled one when present, else one
    generated on this machine (measured if it can be, analytic if not)."""
    if os.path.exists(BUNDLED_BINAURAL_IR):
        return _data_file(os.path.basename(BUNDLED_BINAURAL_IR))
    if not os.path.exists(BINAURAL_IR_PATH):
        generate_binaural_ir(BINAURAL_IR_PATH)
    return BINAURAL_IR_PATH


def head_files(head: str) -> tuple[str, str]:
    """(cue file, surround file) for a head, falling back to the default
    head for anything missing."""
    cue, surround = HEADS.get(head, HEADS[DEFAULT_HEAD])
    if not os.path.exists(os.path.join(DATA_DIR, cue)):
        cue_path = binaural_ir_path()
    else:
        cue_path = _data_file(cue)
    if not os.path.exists(os.path.join(DATA_DIR, surround)):
        surround = HEADS[DEFAULT_HEAD][1]
    return cue_path, _data_file(surround)

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

# The device takes 7.1, so games and films that output surround reach the
# graph with every channel apart instead of already folded into stereo.
# Stereo sources still arrive on FL/FR only: PipeWire's default is not to
# spread stereo over extra channels, so for them nothing changes.
INPUT_POSITIONS = ("FL", "FR", "FC", "LFE", "RL", "RR", "SL", "SR")
INPUT_NODE = {"FL": "inL", "FR": "inR", "FC": "inC", "LFE": "inLFE",
              "RL": "inRL", "RR": "inRR", "SL": "inSL", "SR": "inSR"}
# the levels of PipeWire's own downmix to stereo, so switching between the
# two never jumps in level
DOWNMIX_CENTER = 0.7071
DOWNMIX_SURROUND = 0.7071
DOWNMIX_LFE = 0.5
LFE_CHANNEL_CUTOFF = 120.0

# A user's own HRIR file, HeSuVi layout: for each input, the channels
# holding its response at the (left, right) ear. HeSuVi splits the centre
# between two responses, hence its gain of 2; the LFE reuses the centre's
# at half that, which is the usual -6 dB. From PipeWire's
# sink-virtual-surround-7.1-hesuvi.conf.
HESUVI_CHANNELS = {"FL": (0, 1), "FR": (8, 7), "FC": (6, 13), "LFE": (6, 13),
                   "SL": (2, 3), "SR": (10, 9), "RL": (4, 5), "RR": (12, 11)}
HESUVI_GAIN = {"FC": 2.0}
CUSTOM_HRIR_PATH = os.path.join(RUNTIME_DIR, "custom_hrir.wav")

# Headphone correction (an AutoEQ "ParametricEQ.txt"): this many filters,
# each slot able to be any of these kinds.
HP_EQ_SLOTS = 10
HP_EQ_KINDS = {"p": "bq_peaking", "l": "bq_lowshelf", "h": "bq_highshelf"}
AUTOEQ_KINDS = {"PK": "p", "PEQ": "p", "LS": "l", "LSC": "l", "HS": "h",
                "HSC": "h"}


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


class AlreadyRunning(RuntimeError):
    """Another Spatial Linux is already switched on."""


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


def _sr_gains(amount: float, custom: bool) -> dict:
    """Gains of the sr mixers, input number -> gain.

    Own 3D: 1 the front pair (direct), 2 its cues, 3 the centre, 4 the LFE
    channel, 5-8 the surround channels; everything but the cues follows the
    same headroom trim, so the channels stay balanced as the 3D rises.
    Custom HRIR: 1 the plain downmix, 2 the rendered sound, crossfaded."""
    if custom:
        a = _clamp01(amount)
        return {1: 1.0 - a, 2: a, 3: 0.0, 4: 0.0,
                5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0}
    direct, cue = _surround_gains(amount)
    return {1: direct, 2: cue, 3: DOWNMIX_CENTER * direct,
            4: DOWNMIX_LFE * direct, 5: direct, 6: direct, 7: direct, 8: direct}


def _ab_gains(bypass: bool) -> dict:
    """The output mixer: processed sound, or the plain original."""
    return {"Gain 1": 0.0 if bypass else 1.0, "Gain 2": 1.0 if bypass else 0.0}


def _hp_eq_params(eq: dict | None) -> dict:
    """Every control of the headphone-correction bank, for `eq` (as
    parse_autoeq returns it) or, with None, all transparent."""
    filters = list((eq or {}).get("filters") or [])[:HP_EQ_SLOTS]
    pre = _db_to_lin(float((eq or {}).get("preamp", 0.0))) if eq else 1.0
    params = {}
    for ch in CHANNELS:
        params[f"hpg{ch}:Mult"] = pre
        for i in range(HP_EQ_SLOTS):
            f = filters[i] if i < len(filters) else None
            for kind in HP_EQ_KINDS:
                name = f"hp{kind}{i}{ch}"
                used = f is not None and f["kind"] == kind
                params[f"{name}:Freq"] = f["freq"] if used else 1000.0
                params[f"{name}:Q"] = f["q"] if used else 0.7
                params[f"{name}:Gain"] = f["gain"] if used else 0.0
    return params


def parse_autoeq(text: str) -> dict:
    """An AutoEQ ParametricEQ.txt (also what Equalizer APO reads):

        Preamp: -6.4 dB
        Filter 1: ON LSC Fc 105 Hz Gain 5.5 dB Q 0.70
        Filter 2: ON PK Fc 2500 Hz Gain -3.1 dB Q 1.41

    -> {"preamp": dB, "filters": [{kind, freq, gain, q}], "skipped": n}.
    Peaking and shelf filters are used (all AutoEQ produces); anything
    else is counted in "skipped". Raises ValueError if nothing usable."""
    preamp, filters, skipped = 0.0, [], 0
    for line in text.splitlines():
        words = line.replace(":", " : ").split()
        if not words:
            continue
        if words[0].lower() == "preamp":
            try:
                preamp = float(words[2])
            except (IndexError, ValueError):
                pass
            continue
        if words[0].lower() != "filter" or "ON" not in words:
            continue
        try:
            kind = words[words.index("ON") + 1].upper()
            freq = float(words[words.index("Fc") + 1])
            gain = float(words[words.index("Gain") + 1])
            q = float(words[words.index("Q") + 1]) if "Q" in words else 0.7
        except (IndexError, ValueError):
            skipped += 1
            continue
        if kind not in AUTOEQ_KINDS or not 10.0 <= freq <= 22000.0:
            skipped += 1
            continue
        filters.append({"kind": AUTOEQ_KINDS[kind], "freq": freq,
                        "gain": max(-24.0, min(24.0, gain)),
                        "q": max(0.1, min(20.0, q))})
    if not filters:
        raise ValueError("no filters found")
    skipped += max(0, len(filters) - HP_EQ_SLOTS)
    return {"preamp": max(-30.0, min(10.0, preamp)),
            "filters": filters[:HP_EQ_SLOTS], "skipped": skipped}


def wav_channels(path: str) -> tuple[int, int]:
    """(channels, sample rate) from a WAV file's header. Read by hand
    because the wave module refuses the 32-bit float files HRIR sets often
    are. Raises ValueError for anything that is not a WAV file."""
    with open(path, "rb") as f:
        head = f.read(12)
        if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
            raise ValueError("not a WAV file")
        while True:
            chunk = f.read(8)
            if len(chunk) < 8:
                raise ValueError("no format chunk")
            size = int.from_bytes(chunk[4:8], "little")
            if chunk[:4] == b"fmt ":
                fmt = f.read(size)
                return (int.from_bytes(fmt[2:4], "little"),
                        int.from_bytes(fmt[4:8], "little"))
            f.seek(size + (size & 1), 1)


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
        # flush() hands the sending to a background thread: every command is
        # a new process, and in the Flatpak one that goes through
        # flatpak-spawn, slow enough to stall the window if run from it.
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._sender: threading.Thread | None = None
        # Set by the interface from its settings (they belong to the
        # listener and their headphones, not to presets): which head the 3D
        # stage uses ("kemar", "sadie" or "custom"), the headphone
        # correction and whether it is on, and "Original" (A/B).
        self.head = DEFAULT_HEAD
        self.hp_eq: dict | None = None
        self.hp_eq_on = True
        self.bypass = False
        # the nodes of the running graph; changes aimed at any other are
        # dropped (the custom-HRIR graph has no cue mixers, for one)
        self._node_names: set[str] = set()
        self._recover_from_previous_crash()

    @property
    def custom_hrir(self) -> str:
        return CUSTOM_HRIR_PATH

    def _custom_active(self) -> bool:
        return self.head == "custom" and os.path.exists(CUSTOM_HRIR_PATH)

    def reconfigure(self, state: EngineState):
        """Rebuild the graph with the current head. The convolvers' files
        are fixed when the graph starts, so this restarts it -- a moment of
        silence, fine for a choice made once."""
        if self.running:
            self.stop()
            # PipeWire removes the old device a moment after its process
            # ends; starting before then would take it for another copy
            for _ in range(30):
                if self._find_node_id_by_name(SINK_NAME) is None:
                    break
                time.sleep(0.1)
            self.start(state)

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
        eq_gains = _night_eq(state)
        lo, hi = self._clamp_range(state)
        width = _width_from_surround(state.surround)
        dry, wet = self._ambience_mix(state)
        custom = self._custom_active()

        def link(a, b):
            links.append({"output": a, "input": b})

        # ---- inputs -------------------------------------------------------
        # One copy node per input channel: a graph input can feed only one
        # port, and most of these feed several.
        for pos in INPUT_POSITIONS:
            nodes.append({"type": "builtin", "name": INPUT_NODE[pos],
                          "label": "copy"})
        inp = {pos: f"{INPUT_NODE[pos]}:Out" for pos in INPUT_POSITIONS}

        # The plain stereo downmix a 5.1 / 7.1 source would otherwise get:
        # what "Original" (A/B) plays, and the dry side of a custom HRIR.
        for ch, (side, back) in (("L", ("SL", "RL")), ("R", ("SR", "RR"))):
            nodes.append({"type": "builtin", "name": f"dm{ch}", "label": "mixer",
                          "control": {"Gain 1": 1.0, "Gain 2": DOWNMIX_CENTER,
                                      "Gain 3": DOWNMIX_LFE,
                                      "Gain 4": DOWNMIX_SURROUND,
                                      "Gain 5": DOWNMIX_SURROUND}})
            link(inp["FL" if ch == "L" else "FR"], f"dm{ch}:In 1")
            link(inp["FC"], f"dm{ch}:In 2")
            link(inp["LFE"], f"dm{ch}:In 3")
            link(inp[side], f"dm{ch}:In 4")
            link(inp[back], f"dm{ch}:In 5")

        if custom:
            self._build_custom_hrir(nodes, link, inp)
        else:
            self._build_3d(nodes, link, inp, state, width)

        sr = _sr_gains(state.surround, custom)
        for ch in CHANNELS:
            nodes.append({"type": "builtin", "name": f"sr{ch}", "label": "mixer",
                          "control": {f"Gain {i}": sr[i] for i in range(1, 9)}})
        if custom:
            for ch in CHANNELS:
                link(f"dm{ch}:Out", f"sr{ch}:In 1")
                link(f"hv{ch}:Out", f"sr{ch}:In 2")
        else:
            for ch, near, far in (("L", ("SL", "RL"), ("SR", "RR")),
                                  ("R", ("SR", "RR"), ("SL", "RL"))):
                link(f"w{ch}:Out", f"sr{ch}:In 1")
                link(f"cue{ch}:Out", f"sr{ch}:In 2")
                link(inp["FC"], f"sr{ch}:In 3")
                link("lfelp:Out", f"sr{ch}:In 4")
                link(f"s{near[0]}{ch}:Out", f"sr{ch}:In 5")
                link(f"s{far[0]}{ch}:Out", f"sr{ch}:In 6")
                link(f"s{near[1]}{ch}:Out", f"sr{ch}:In 7")
                link(f"s{far[1]}{ch}:Out", f"sr{ch}:In 8")

        # ---- tone chain ---------------------------------------------------
        # After the 3D stage rather than before it: every stage here is
        # linear and the same on both channels, so for stereo the result is
        # identical, and this way the surround channels of a 5.1 / 7.1
        # source get the equaliser, bass and pre-amp too.
        for ch in CHANNELS:
            seq = [f"sr{ch}"]
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

            # LFE trim, belonging to the 3D mode
            nodes.append({"type": "builtin", "name": f"lfe{ch}", "label": "bq_lowshelf",
                          "control": {"Freq": SURROUND_LFE_FREQ, "Q": 0.7,
                                      "Gain": state.lfe}})
            seq.append(f"lfe{ch}")

            for a, b in zip(seq, seq[1:]):
                link(f"{a}:Out", f"{b}:In")

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

            # headphone correction, then the ceiling, then A/B
            src = self._build_headphone_eq(nodes, link, ch, f"ngc{ch}:Out")
            nodes.append({"type": "builtin", "name": f"lim{ch}", "label": "clamp",
                          "control": {"Min": lo, "Max": hi}})
            link(src, f"lim{ch}:In")
            nodes.append({"type": "builtin", "name": f"out{ch}", "label": "mixer",
                          "control": _ab_gains(self.bypass)})
            link(f"lim{ch}:Out", f"out{ch}:In 1")
            link(f"dm{ch}:Out", f"out{ch}:In 2")

        return {
            "nodes": nodes,
            "links": links,
            "inputs": [f"{INPUT_NODE[pos]}:In" for pos in INPUT_POSITIONS],
            "outputs": [f"out{ch}:Out" for ch in CHANNELS],
        }

    def _build_3d(self, nodes, link, inp, state: EngineState, width: float):
        """Spatial Linux's own 3D stage for the front pair, and the
        measured head placing a 5.1 / 7.1 source's other channels."""
        cue_file, surround_file = head_files(self.head)
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
        link(inp["FL"], "mid:In 1")
        link(inp["FR"], "mid:In 2")
        link(inp["FL"], "side:In 1")
        link(inp["FR"], "invR:In")
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
                "config": {"filename": cue_file, "channel": channel,
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

        # ---- discrete surround channels ----------------------------------
        # A 5.1 / 7.1 source's own surround channels, each heard from where
        # its speaker would be (see ir.generate_surround_ir). Stereo sources
        # leave these channels silent, so for them nothing here changes the
        # sound. The centre joins both ears dry, like the front pair; the
        # LFE channel is kept to its band and added to both.
        for src, near_ear, far_ear, near_ch in (("SL", "L", "R", 0),
                                                 ("SR", "R", "L", 0),
                                                 ("RL", "L", "R", 2),
                                                 ("RR", "R", "L", 2)):
            for ear, channel in ((near_ear, near_ch), (far_ear, near_ch + 1)):
                nodes.append({"type": "builtin", "name": f"s{src}{ear}",
                              "label": "convolver",
                              "config": {"filename": surround_file,
                                         "channel": channel, "gain": 1.0}})
                link(inp[src], f"s{src}{ear}:In")
        nodes.append({"type": "builtin", "name": "lfelp", "label": "bq_lowpass",
                      "control": {"Freq": LFE_CHANNEL_CUTOFF, "Q": 0.707,
                                  "Gain": 0.0}})
        link(inp["LFE"], "lfelp:In")

    def _build_custom_hrir(self, nodes, link, inp):
        """Every channel through the user's own 14-channel HRIR file, laid
        out the HeSuVi way -- the same mapping as PipeWire's own
        sink-virtual-surround-7.1-hesuvi.conf example."""
        path = self.custom_hrir
        for ch in CHANNELS:
            nodes.append({"type": "builtin", "name": f"hv{ch}", "label": "mixer"})
        for i, pos in enumerate(INPUT_POSITIONS):
            for ear, channel in zip(CHANNELS, HESUVI_CHANNELS[pos]):
                name = f"h{pos}{ear}"
                nodes.append({"type": "builtin", "name": name, "label": "convolver",
                              "config": {"filename": path, "channel": channel,
                                         "gain": HESUVI_GAIN.get(pos, 1.0)}})
                link(inp[pos], f"{name}:In")
                link(f"{name}:Out", f"hv{ear}:In {i + 1}")

    def _build_headphone_eq(self, nodes, link, ch, src) -> str:
        """HP_EQ_SLOTS filters of the headphone correction. Each slot is a
        peaking, a low-shelf and a high-shelf filter in a row, of which the
        loaded file's filter uses one and the other two sit at 0 dB -- where
        a biquad is exactly transparent -- so any file can be loaded, and
        switched on and off, while playing, without rebuilding the graph."""
        params = _hp_eq_params(self.hp_eq if self.hp_eq_on else None)
        nodes.append({"type": "builtin", "name": f"hpg{ch}", "label": "linear",
                      "control": {"Mult": params[f"hpg{ch}:Mult"], "Add": 0.0}})
        link(src, f"hpg{ch}:In")
        prev = f"hpg{ch}"
        for i in range(HP_EQ_SLOTS):
            for kind, label in HP_EQ_KINDS.items():
                name = f"hp{kind}{i}{ch}"
                nodes.append({"type": "builtin", "name": name, "label": label,
                              "control": {k: params[f"{name}:{k}"]
                                          for k in ("Freq", "Q", "Gain")}})
                link(f"{prev}:Out", f"{name}:In")
                prev = name
        return f"{prev}:Out"

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
        graph = self._build_graph(state)
        self._node_names = {n["name"] for n in graph["nodes"]}
        args = {
            "node.description": SINK_DESCRIPTION,
            "media.name": SINK_DESCRIPTION,
            "filter.graph": graph,
            "capture.props": {
                "node.name": SINK_NAME,
                "node.description": SINK_DESCRIPTION,
                "media.class": "Audio/Sink",
                "audio.channels": len(INPUT_POSITIONS),
                "audio.position": list(INPUT_POSITIONS),
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
    {{ name = libpipewire-module-rt
        args = {{ nice.level = -11 rt.prio = 88 }}
        flags = [ ifexists nofail ] }}
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

        if self._find_node_id_by_name(SINK_NAME) is not None:
            # another copy (the normal version and the Flatpak side by side)
            # already has its device up; a second one would be routed into
            # the first and process every sound twice
            raise AlreadyRunning()

        if not os.path.exists(IR_PATH):
            generate_reverb_ir(IR_PATH)

        self._drop_pending()
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
        self._drop_pending()
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
        if self._node_names:
            params = {k: v for k, v in params.items()
                      if k.split(":", 1)[0] in self._node_names}
        with self._lock:
            self._pending.update(params)
        if self.defer is not None:
            self.defer()
        else:
            self.flush()

    def _drop_pending(self):
        with self._lock:
            self._pending.clear()
            self._pending_volume = None

    def flush(self):
        """Send everything gathered since the last flush, in the background.
        Changes made while a send is running are merged and go out in the
        next one, so a slow send never builds up a queue."""
        if self._sender is None:
            self._sender = threading.Thread(target=self._send_loop,
                                            name="spatiallinux-sender",
                                            daemon=True)
            self._sender.start()
        self._wake.set()

    def _send_loop(self):
        while True:
            self._wake.wait()
            self._wake.clear()
            try:
                self._send_pending()
            except Exception:
                pass                         # never let the sender die

    def _send_pending(self):
        with self._lock:
            streams, self._pending_streams = self._pending_streams, {}
            mutes, self._pending_mutes = self._pending_mutes, {}
            sink = self.sink_id
            volume, self._pending_volume = self._pending_volume, None
            items = list(self._pending.items())
            self._pending.clear()
        for node, pct in streams.items():
            _run("wpctl", "set-volume", str(node), f"{pct / 100:.3f}")
        for node, muted in mutes.items():
            _run("wpctl", "set-mute", str(node), "1" if muted else "0")
        if sink is None:
            return
        if volume is not None:
            _run("wpctl", "set-volume", str(sink), f"{volume / 100:.3f}")
        for start in range(0, len(items), self.MAX_PARAMS_PER_CALL):
            chunk = items[start:start + self.MAX_PARAMS_PER_CALL]
            body = " ".join(f'"{k}" {v}' for k, v in chunk)
            _run("pw-cli", "set-param", str(sink), "Props",
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
        sr = _sr_gains(amount, self._custom_active())
        self._set_props({"wid:Mult": _width_from_surround(amount) - 1.0} |
                        {f"sr{ch}:Gain {i}": g
                         for ch in CHANNELS for i, g in sr.items()})

    def set_bypass(self, bypass: bool):
        """"Original": the plain source, without any processing (A/B)."""
        self.bypass = bypass
        self._set_props({f"out{ch}:{k}": v for ch in CHANNELS
                         for k, v in _ab_gains(bypass).items()})

    def set_hp_eq(self, eq: dict | None, on: bool):
        """Load, clear or switch the headphone correction, live."""
        self.hp_eq, self.hp_eq_on = eq, on
        self._set_props(_hp_eq_params(eq if on else None))

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
        sr = _sr_gains(state.surround, self._custom_active())

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
            for i, g in sr.items():
                params[f"sr{ch}:Gain {i}"] = g
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
        with self._lock:
            self._pending_volume = max(0.0, min(150.0, pct))
        if self.defer is not None:
            self.defer()
        else:
            self.flush()

    # -- per-app volumes (the mixer) ----------------------------------------
    def set_stream_volume(self, node_id: int, pct: float):
        with self._lock:
            self._pending_streams[node_id] = max(0.0, min(150.0, pct))
        self._request_flush()

    def set_stream_mute(self, node_id: int, muted: bool):
        with self._lock:
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
