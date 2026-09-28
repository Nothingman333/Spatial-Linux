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


def load_sofa(path: str):
    """(ir, positions, rate) from a SOFA file: ir is (measurements, ears,
    taps), positions (measurements, [azimuth, elevation]) in degrees with
    azimuth counter-clockwise from the front."""
    import numpy as np
    import h5py

    with h5py.File(path, "r") as f:
        ir = np.array(f["Data.IR"])
        pos = np.array(f["SourcePosition"])
        rate = float(np.array(f["Data.SamplingRate"]).ravel()[0])
    return ir, pos[:, :2], rate


def load_mhr(path: str):
    """The same from an OpenAL Soft MinPHR03 file (see its core/hrtf_loader
    .cpp), the format its SADIE II set ships in. Its responses are minimum
    phase with the arrival delays stored apart, in quarter samples; they are
    put back here, with a fractional-delay phase shift, so the result is an
    ordinary head-related impulse response again. Only one field and the
    left-ear-only layout are handled -- what that file uses -- and the right
    ear is the mirror image, as OpenAL Soft does it."""
    import numpy as np

    data = open(path, "rb").read()
    if data[:8] != b"MinPHR03":
        raise ValueError("not a MinPHR03 file")
    rate, chan_type, taps, fields = struct.unpack_from("<IBBB", data, 8)
    if chan_type != 0 or fields != 1:
        raise ValueError("unsupported MinPHR03 layout")
    p = 15 + 2                                   # field distance (unused)
    ev_count = data[p]
    p += 1
    az_counts = list(data[p:p + ev_count])
    p += ev_count
    total = sum(az_counts)

    raw = np.frombuffer(data[p:p + total * taps * 3], dtype=np.uint8)
    raw = raw.reshape(total, taps, 3).astype(np.int32)
    p += total * taps * 3
    coeffs = raw[..., 0] | (raw[..., 1] << 8) | (raw[..., 2] << 16)
    coeffs = np.where(coeffs >= 1 << 23, coeffs - (1 << 24), coeffs) / 8388608.0
    delays = np.frombuffer(data[p:p + total], dtype=np.uint8) / 4.0

    # elevations run evenly from straight down to straight up; azimuths
    # evenly from the front, clockwise -- flipped here to the SOFA sense
    positions = []
    for e, n in enumerate(az_counts):
        el = -90.0 + 180.0 * e / (ev_count - 1)
        for a in range(n):
            positions.append(((360.0 - 360.0 * a / n) % 360.0, el))
    positions = np.array(positions)

    length = taps + int(np.ceil(delays.max())) + 8
    n_fft = 1 << int(np.ceil(np.log2(length * 2)))
    freqs = np.fft.rfftfreq(n_fft)

    def placed(i):
        spec = np.fft.rfft(coeffs[i], n_fft) * np.exp(-2j * np.pi * freqs * delays[i])
        return np.fft.irfft(spec, n_fft)[:length]

    left = np.array([placed(i) for i in range(total)])

    # the right ear at azimuth a is the left ear at -a (same elevation)
    right = np.empty_like(left)
    for i, (az, el) in enumerate(positions):
        same = np.where(np.abs(positions[:, 1] - el) < 1e-6)[0]
        delta = ((positions[same, 0] - (360.0 - az) + 180.0) % 360.0) - 180.0
        right[i] = left[same[int(np.argmin(np.abs(delta)))]]
    return np.stack([left, right], axis=1), positions, float(rate)


def _load_measured_hrirs(sofa_path: str, speakers: dict | None = None):
    """Return {speaker: (left_ear, right_ear)} at the graph sample rate.

    The bulk propagation delay common to every measurement is removed while
    the difference between the ears is kept, so what survives is the real
    interaural delay rather than the distance to the loudspeaker.
    """
    loader = load_mhr if sofa_path.endswith(".mhr") else load_sofa
    return _pick_hrirs(*loader(sofa_path), speakers or SPEAKERS)


def _pick_hrirs(ir, pos, src_rate: float, speakers: dict):
    import numpy as np

    horizontal = np.where(np.abs(pos[:, 1]) < 1.0)[0]

    def nearest(azimuth):
        delta = ((pos[horizontal, 0] - azimuth + 180.0) % 360.0) - 180.0
        return horizontal[int(np.argmin(np.abs(delta)))]

    picked = {name: ir[nearest(az)] for name, az in speakers.items()}

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


def generate_binaural_ir(path: str, hrirs: dict | None = None,
                         front_energy: float | None = None) -> str:
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
    analytic head model otherwise. `hrirs` picks another measured head
    instead; `front_energy` then matches its cross-feed level to the
    default head's, so switching heads changes the character of the 3D
    stage, not how strong it is.
    """
    sofa = _find_sofa()
    channels = None
    if hrirs is not None:
        channels = _measured_channels(hrirs)
    elif sofa:
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
    if front_energy is not None:
        mine = sum(v * v for c in channels[:2] for v in c)
        if mine > 0:
            k = math.sqrt(front_energy / mine)
            channels = [[v * k for v in c] for c in channels]

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


# --- discrete surround channels ---------------------------------------------

# Where a 5.1 / 7.1 source's surround channels are heard from, in SOFA
# azimuth: the side pair of 7.1 (and the rear pair of 5.1, which PipeWire
# maps onto the same place) just behind the ears, the back pair further
# round, as ITU-R BS.775 and the 7.1 layouts put them (135: between the
# 110 a 5.1 source expects and the 150 of a 7.1 back pair).
SURROUND_SPEAKERS = {"SL": 100.0, "BL": 135.0}
# Level of each surround channel as heard. A plain downmix to stereo adds
# them at -3 dB (0.707), so rendered at the same energy switching to this
# neither jumps nor drops in level.
SURROUND_CHANNEL_GAIN = 0.7071


def generate_surround_ir(path: str, hrirs: dict) -> str:
    """Write the 4-channel file that places the discrete surround channels:

    ch0: side speaker -> near ear    ch1: side speaker -> far ear
    ch2: back speaker -> near ear    ch3: back speaker -> far ear

    The right-hand speakers use the same channels mirrored (the heads are
    symmetric). `hrirs` must hold "SL" and "BL" pairs (left ear, right ear)
    from _load_measured_hrirs(..., SURROUND_SPEAKERS). Each pair is scaled to
    the energy a -3 dB downmix would give it; the near/far balance, the
    interaural delay and the pinna cues are left exactly as measured.
    """
    channels = []
    for name in ("SL", "BL"):
        near, far = hrirs[name]                # a left speaker: left ear near
        energy = sum(float(v) * float(v) for v in near) + \
            sum(float(v) * float(v) for v in far)
        k = SURROUND_CHANNEL_GAIN / math.sqrt(energy) if energy > 0 else 0.0
        channels += [[float(v) * k for v in near], [float(v) * k for v in far]]

    length = max(len(c) for c in channels)
    channels = [c + [0.0] * (length - len(c)) for c in channels]
    peak = max(max(abs(v) for v in c) for c in channels)
    if peak > 0.99:          # never clip the file; far from happening
        channels = [[v * 0.99 / peak for v in c] for c in channels]

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(4)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(
            struct.pack("<hhhh", *(
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
