"""Impulse responses for the convolution stages.

PipeWire's convolver needs real IR files on disk and there is no builtin
reverb or binaural renderer, so both are synthesised here:

* `generate_reverb_ir`  -- the Ambience tail: decaying, low-passed noise,
  decorrelated between channels so the reverb sounds wide, not centred.
* `generate_binaural_ir` -- the 3D Surround cues: a head model that turns
  plain stereo into something the ear reads as coming from speakers in a
  room rather than from inside the head.
"""

from __future__ import annotations

import math
import os
import random
import struct
import wave

SR = 48000


def _decaying_noise(seed: int, length: int, decay_t60: float) -> list[float]:
    rnd = random.Random(seed)
    out = []
    # one-pole low-pass so the tail is dark rather than hissy
    lp = 0.0
    alpha = 0.35
    for i in range(length):
        n = rnd.uniform(-1.0, 1.0)
        lp += alpha * (n - lp)
        env = math.exp(-6.9078 * (i / SR) / decay_t60)  # -60 dB at t60
        out.append(lp * env)
    # short fade-in avoids a click at the very start of the tail
    fade = int(SR * 0.005)
    for i in range(min(fade, length)):
        out[i] *= i / fade
    return out


def _normalise(xs: list[float], peak: float = 0.5) -> list[float]:
    m = max((abs(x) for x in xs), default=0.0)
    if m == 0:
        return xs
    k = peak / m
    return [x * k for x in xs]


# --- binaural (3D Surround) ------------------------------------------------

HEAD_RADIUS_M = 0.0875
SPEED_OF_SOUND = 343.0
SPEAKER_AZIMUTH_DEG = 30.0      # virtual front pair, like a stereo triangle
BINAURAL_TAPS = 2048            # ~43 ms, long enough for the early reflections

# Early reflections, as (delay in ms, level). Two slightly different sets so
# the two ears stay decorrelated -- a perfectly symmetric room collapses the
# image back into the middle of the head.
REFLECTIONS_A = [(9.1, 0.30), (14.3, 0.23), (21.7, 0.17), (29.3, 0.11)]
REFLECTIONS_B = [(11.4, 0.28), (17.1, 0.21), (24.9, 0.15), (33.1, 0.10)]

# A handful of discrete reflections comb-filters badly: with only four taps
# the peaks and notches are metres apart in frequency and audible as
# boxiness. Real rooms have hundreds, which fill the gaps in. Each tap is
# therefore smeared into a short burst of decaying noise instead.
SCATTER_MS = 7.0
SCATTER_DECAY = 0.0035
# How loud the rear speakers and room sit against the front
# cross-feed. Left to itself the scattered room energy ran about
# eight times the front cue, which swamped the image and dragged
# the bass out of the middle; this pins the ratio deliberately.
SPATIAL_TO_FRONT_RATIO = 1.6


def _itd_seconds(azimuth_deg: float) -> float:
    """Woodworth's interaural time difference for a spherical head."""
    t = math.radians(azimuth_deg)
    return (HEAD_RADIUS_M / SPEED_OF_SOUND) * (t + math.sin(t))


def _one_pole_lowpass(xs: list[float], fc: float) -> list[float]:
    a = 1.0 - math.exp(-2.0 * math.pi * fc / SR)
    out, y = [], 0.0
    for x in xs:
        y += a * (x - y)
        out.append(y)
    return out


def _scatter(buf: list[float], seed: int, delay_s: float, gain: float):
    """Place a reflection as a short diffuse burst rather than a single
    spike, so the response between reflections fills in."""
    rnd = random.Random(seed)
    start = int(round(delay_s * SR))
    length = int(SCATTER_MS / 1000.0 * SR)
    lp = 0.0
    for i in range(length):
        j = start + i
        if j >= len(buf):
            break
        lp += 0.45 * (rnd.uniform(-1.0, 1.0) - lp)
        buf[j] += lp * gain * math.exp(-(i / SR) / SCATTER_DECAY)


def _one_pole_highpass(xs: list[float], fc: float) -> list[float]:
    a = math.exp(-2.0 * math.pi * fc / SR)
    out, y, prev = [], 0.0, 0.0
    for x in xs:
        y = a * (y + x - prev)
        prev = x
        out.append(y)
    return out


def _place(buf: list[float], delay_s: float, gain: float):
    i = int(round(delay_s * SR))
    if 0 <= i < len(buf):
        buf[i] += gain


def _contralateral(azimuth_deg: float, reflections) -> list[float]:
    """What the FAR ear hears from one virtual speaker: the same sound, a
    fraction of a millisecond late, quieter, and with the highs rolled off
    because the head is in the way."""
    buf = [0.0] * BINAURAL_TAPS
    _place(buf, _itd_seconds(azimuth_deg), 0.72)
    for ms, level in reflections:
        _place(buf, ms / 1000.0, level * 0.45)
    # head shadow: the far ear loses high frequencies
    return _one_pole_lowpass(buf, 1100.0)


def _ipsilateral_room(reflections) -> list[float]:
    """What the NEAR ear hears beyond the direct sound: room reflections
    only. The direct path stays dry in the graph, so mixing this in can
    never comb-filter the original signal -- it only ever adds later energy,
    which is exactly how a real room behaves."""
    buf = [0.0] * BINAURAL_TAPS
    for ms, level in reflections:
        _place(buf, ms / 1000.0, level)
    return _one_pole_lowpass(buf, 3800.0)


# Measured HRTFs, if the system ships them. libmysofa's default set is the
# MIT KEMAR dummy-head measurement -- real ears, so it carries the pinna
# cues that tell front from behind, which no analytic head model provides.
SOFA_CANDIDATES = [
    "/usr/share/libmysofa/default.sofa",
    "/usr/share/libmysofa/MIT_KEMAR_normal_pinna.sofa",
]

# Low frequencies are left out of the rear and room paths entirely. Bass has
# almost no directional information for the ear to use, and feeding it round
# the head only widens and hollows the low end -- the exact fault the width
# stage is already careful to avoid.
SPATIAL_HIGHPASS_HZ = 220.0

# Virtual speaker layout, in SOFA azimuth (counter-clockwise, 0 = front).
SPEAKERS = {"FL": 30.0, "FR": 330.0, "RL": 110.0, "RR": 250.0}
# The far-ear (cross-feed) path makes the image more solid but also
# pulls the channels together; the rear speakers and the room only ever
# add envelopment. Raising them separately is how the effect gets
# stronger without collapsing towards mono.
CONTRA_GAIN = 0.55
REAR_GAIN = 1.05
REAR_DELAY_MS = {"RL": 12.0, "RR": 14.3}   # slightly different = decorrelated
CUE_LOWPASS_HZ = 8000.0


def _scale_for_headroom(channels, ceiling: float = 0.85):
    """Scale all four channels together so the loudest one just fits in the
    16-bit file. Scaling them as a group preserves the level relationships
    between the ears, which is where the spatial information lives."""
    peak = max((max(abs(v) for v in c) if c else 0.0) for c in channels)
    if peak <= ceiling or peak == 0.0:
        return channels
    k = ceiling / peak
    return [[v * k for v in c] for c in channels]


def _find_sofa() -> str | None:
    for p in SOFA_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def _diffuse_field_equalise(picked: dict, all_horizontal, max_correction_db=12.0):
    """Flatten out the response common to every measurement direction."""
    import numpy as np

    taps = all_horizontal.shape[-1]
    spectra = np.fft.rfft(all_horizontal.reshape(-1, taps), axis=-1)
    diffuse = np.sqrt(np.mean(np.abs(spectra) ** 2, axis=0))
    diffuse[diffuse <= 0] = 1e-9

    correction = diffuse.mean() / diffuse
    limit = 10.0 ** (max_correction_db / 20.0)
    correction = np.clip(correction, 1.0 / limit, limit)

    out = {}
    for name, pair in picked.items():
        eq = np.fft.irfft(np.fft.rfft(pair, axis=-1) * correction, n=taps, axis=-1)
        out[name] = eq
    return out


def _load_measured_hrirs(sofa_path: str):
    """Return {speaker: (left_ear, right_ear)} at the graph sample rate.

    The bulk propagation delay common to every measurement is removed while
    the difference between the ears is kept, so what survives is the real
    interaural delay rather than the distance to the loudspeaker.
    """
    import numpy as np
    import h5py

    with h5py.File(sofa_path, "r") as f:
        ir = np.array(f["Data.IR"])              # (measurements, ears, taps)
        pos = np.array(f["SourcePosition"])
        src_rate = float(np.array(f["Data.SamplingRate"]).ravel()[0])

    horizontal = np.where(np.abs(pos[:, 1]) < 1.0)[0]

    def nearest(azimuth):
        delta = ((pos[horizontal, 0] - azimuth + 180.0) % 360.0) - 180.0
        return horizontal[int(np.argmin(np.abs(delta)))]

    picked = {name: ir[nearest(az)] for name, az in SPEAKERS.items()}

    # Raw HRTF measurements carry the response of the measurement rig itself
    # -- for the MIT KEMAR set that is a pronounced few-dB-per-octave lift
    # through the presence region, which would come out as harshness. Divide
    # every response by the average across all directions ("diffuse field"),
    # which cancels what is common to all of them and leaves only the
    # direction-dependent cues, which is the part we actually want.
    picked = _diffuse_field_equalise(picked, ir[horizontal])

    def onset(h):
        peak = np.max(np.abs(h))
        above = np.where(np.abs(h) > peak * 0.1)[0]
        return int(above[0]) if len(above) else 0

    bulk = min(onset(pair[ear]) for pair in picked.values() for ear in (0, 1))

    out = {}
    for name, pair in picked.items():
        ears = []
        for ear in (0, 1):
            h = pair[ear][bulk:]
            if src_rate != SR:                   # resample onto the graph rate
                n_out = int(round(len(h) * SR / src_rate))
                h = np.interp(np.arange(n_out) * src_rate / SR,
                              np.arange(len(h)), h)
            ears.append(h.astype(float))
        out[name] = tuple(ears)
    return out


def _delayed_into(buf: list[float], h, delay_ms: float, gain: float):
    start = int(round(delay_ms / 1000.0 * SR))
    for i, v in enumerate(h):
        j = start + i
        if j >= len(buf):
            break
        buf[j] += float(v) * gain


def _measured_channels(hrirs):
    """Lay the measured responses out into the six cue channels (see
    generate_binaural_ir for the layout).

    Front speakers contribute only their *far-ear* response: the near ear
    already has the dry signal, and leaving it dry is what keeps the stage
    transparent at zero. Rear speakers contribute to both ears, delayed, so
    they only ever add late energy.
    """
    ch = [[0.0] * BINAURAL_TAPS for _ in range(4)]

    _delayed_into(ch[0], hrirs["FL"][1], 0.0, CONTRA_GAIN)  # L -> right ear
    _delayed_into(ch[2], hrirs["FR"][0], 0.0, CONTRA_GAIN)  # R -> left ear

    # rear speakers and room go into their own buffers so they can be
    # high-passed without touching the front cross-feed
    spatial = [[0.0] * BINAURAL_TAPS for _ in range(4)]
    _delayed_into(spatial[1], hrirs["RL"][0], REAR_DELAY_MS["RL"], REAR_GAIN)
    _delayed_into(spatial[0], hrirs["RL"][1], REAR_DELAY_MS["RL"], REAR_GAIN)
    _delayed_into(spatial[3], hrirs["RR"][1], REAR_DELAY_MS["RR"], REAR_GAIN)
    _delayed_into(spatial[2], hrirs["RR"][0], REAR_DELAY_MS["RR"], REAR_GAIN)

    # a little room on top; measured HRTFs are anechoic, and without any
    # reflections the image stays stubbornly inside the head
    for idx, (buf, refl) in enumerate(((spatial[1], REFLECTIONS_A),
                                       (spatial[3], REFLECTIONS_B))):
        for k, (ms, level) in enumerate(refl):
            _scatter(buf, 7000 + idx * 100 + k, ms / 1000.0, level * 2.2)

    # two poles, so the low end really is gone rather than merely quieter
    spatial = [_one_pole_highpass(
                   _one_pole_highpass(c, SPATIAL_HIGHPASS_HZ),
                   SPATIAL_HIGHPASS_HZ)
               for c in spatial]

    front_energy = sum(sum(v * v for v in c) for c in ch)
    spatial_energy = sum(sum(v * v for v in c) for c in spatial)
    if spatial_energy > 0 and front_energy > 0:
        k = math.sqrt(front_energy / spatial_energy) * SPATIAL_TO_FRONT_RATIO
        spatial = [[v * k for v in c] for c in spatial]

    return [ch[0], ch[2]] + spatial


def _analytic_channels():
    """The same six channels from the spherical-head model, for systems
    without a SOFA file. The contralateral model carries its reflections in
    the same buffer; subtracting the reflection-free version (it is linear)
    leaves those reflections for the room channels."""
    front_a = _contralateral(SPEAKER_AZIMUTH_DEG, [])
    front_b = _contralateral(SPEAKER_AZIMUTH_DEG, [])
    return [
        front_a, front_b,
        [a - b for a, b in zip(_contralateral(SPEAKER_AZIMUTH_DEG, REFLECTIONS_A),
                               front_a)],
        _ipsilateral_room(REFLECTIONS_A),
        [a - b for a, b in zip(_contralateral(SPEAKER_AZIMUTH_DEG, REFLECTIONS_B),
                               front_b)],
        _ipsilateral_room(REFLECTIONS_B),
    ]


def generate_binaural_ir(path: str) -> str:
    """Write the 6-channel cue set used by the 3D Surround stage. The front
    cross-feed and the room are kept apart so the graph can turn the room
    down on its own (the 3D "Reverb" slider):

    ch0: left input  -> right ear, across the head (front speaker)
    ch1: right input -> left ear,  across the head (front speaker)
    ch2: left input  -> right ear, rear speaker
    ch3: left input  -> left ear,  rear speaker + room
    ch4: right input -> left ear,  rear speaker
    ch5: right input -> right ear, rear speaker + room

    Uses measured HRTFs when the system provides them, and falls back to an
    analytic head model otherwise.
    """
    sofa = _find_sofa()
    channels = None
    if sofa:
        try:
            channels = _measured_channels(_load_measured_hrirs(sofa))
        except Exception:
            channels = None      # any trouble -> analytic model below

    if channels is None:
        channels = _analytic_channels()

    # Two poles: above ~8 kHz the cues only comb-filter against the dry
    # signal (measured ripple +6/-14 dB up there), which reads as sizzle
    # rather than direction -- a real head shadows that range anyway.
    channels = [_one_pole_lowpass(_one_pole_lowpass(c, CUE_LOWPASS_HZ),
                                  CUE_LOWPASS_HZ) for c in channels]

    # Headroom is judged on what each ear receives with the room fully up,
    # and the one factor is applied to all six, so the balance between the
    # front and the room -- and between the ears -- survives the scaling.
    f_lr, f_rl, s_lr, s_ll, s_rl, s_rr = channels
    ears = [[a + b for a, b in zip(f_lr, s_lr)], s_ll,
            [a + b for a, b in zip(f_rl, s_rl)], s_rr]
    peak = max(max(abs(v) for v in c) for c in ears)
    k = min(1.0, 0.85 / peak) if peak else 1.0
    channels = [[v * k for v in c] for c in channels]

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(6)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(
            struct.pack("<hhhhhh", *(
                int(max(-1.0, min(1.0, v)) * 32000) for v in frame))
            for frame in zip(*channels)))
    return path


# --- ambience --------------------------------------------------------------

def generate_reverb_ir(path: str, decay_t60: float = 1.4,
                       predelay_ms: float = 18.0) -> str:
    """Write a 2-channel reverb IR to `path`; returns the path."""
    length = int(SR * decay_t60)
    pre = int(SR * predelay_ms / 1000.0)

    left = _normalise(_decaying_noise(1234, length, decay_t60))
    right = _normalise(_decaying_noise(9876, length, decay_t60))
    left = [0.0] * pre + left
    right = [0.0] * pre + right

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(
            struct.pack("<hh",
                        int(max(-1.0, min(1.0, l)) * 32000),
                        int(max(-1.0, min(1.0, r)) * 32000))
            for l, r in zip(left, right)))
    return path
