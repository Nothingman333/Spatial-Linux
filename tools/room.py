"""Virtual speakers in a room, for the "room" 3D styles.

Build-time only (NumPy, SciPy); tools/build_ir.py writes the results into
spatiallinux/data/. What a pair of good speakers in a real room sounds like
at the ears is, in order of arrival:

  1. the direct sound from each speaker, from its direction;
  2. early reflections off the walls, floor and ceiling -- each from its own
     direction, above and below included, a little later and darker;
  3. the late, diffuse reverberation of the room.

Measured heads give (1) and (2) their directional cues: every reflection is
rendered with the head's response from the direction it arrives from. That
is how headphone virtualisers of the Dolby Atmos for Headphones kind place
sound outside the head, and the floor and ceiling reflections are what give
the sense of height. (3) carries no direction, so it is rendered once, from
the sum of all channels, as a decorrelated stereo tail.

Geometry: x forward, y left, z up, metres. Rooms are shoeboxes; reflections
come from the image-source method (Allen & Berkley 1979) up to MAX_ORDER.
"""

from __future__ import annotations

import numpy as np

SR = 48000
C = 343.0                     # speed of sound, m/s

# The speakers of a 7.1 layout (azimuth, counter-clockwise from the front),
# at ear height, all the same distance away.
SPEAKER_AZ = {"FL": 30.0, "FR": -30.0, "FC": 0.0, "SL": 100.0, "SR": -100.0,
              "BL": 142.0, "BR": -142.0}

# name: dimensions (x, y, z), listener position, speaker distance, wall
# reflection coefficient, high-frequency loss per reflection (-3 dB point),
# reverberation time (s), when the late tail takes over (s after the direct
# sound), its level against the direct sound (dB), and how long the early
# reflections are kept for (s) -- by then the tail has taken over.
ROOMS = {
    "studio": dict(dims=(5.0, 4.2, 2.8), listener=(2.6, 2.1, 1.2), distance=1.4,
                   beta=0.55, hf_cut=5000.0, t60=0.25, mix_time=0.020,
                   late_db=-12.0, early_len=0.060),
    "living": dict(dims=(6.0, 4.6, 2.7), listener=(2.5, 2.3, 1.1), distance=2.0,
                   beta=0.72, hf_cut=6500.0, t60=0.45, mix_time=0.035,
                   late_db=-8.0, early_len=0.080),
    "cinema": dict(dims=(14.0, 10.0, 6.0), listener=(6.0, 5.0, 1.2), distance=4.0,
                   beta=0.80, hf_cut=7000.0, t60=0.90, mix_time=0.060,
                   late_db=-5.0, early_len=0.110),
}
MAX_ORDER = 3
N_FFT = 1 << 14               # > the longest early part + an HRIR, at 48 kHz


# Below this the head's responses are made flat. Direction is heard from
# the time difference between the ears down there, not from the spectrum,
# and dummy-head measurements are thin in the bass (the MIT KEMAR set is
# 9 dB down at 63 Hz): left as measured, every virtual speaker lost its low
# end.
LF_FLAT_HZ = 250.0
# Tonal balance: the head is equalised so the front pair of speakers --
# where almost all of any stereo recording is -- sounds neutral, their two
# ears averaged, smoothed over a third of an octave and limited to this
# many dB either way. What differs between directions and between the ears
# (the cues) is untouched.
FRONT_EQ_LIMIT_DB = 8.0
# Reflections and the tail carry no bass: low frequencies bouncing round a
# small room are what makes it boom (the image model put a 6 dB hole at
# 125 Hz in the living room), and they add nothing to the sense of space.
REFLECTION_HIGHPASS_HZ = 220.0
TAIL_HIGHPASS_HZ = 150.0


def _smooth_third_octave(freqs, power):
    out = np.empty_like(power)
    for i, f in enumerate(freqs):
        if f <= 0:
            out[i] = power[i]
            continue
        m = (freqs >= f / 2 ** (1 / 6)) & (freqs <= f * 2 ** (1 / 6))
        out[i] = power[m].mean()
    return out


class Head:
    """A measured head: every direction, on the graph's sample rate, flat
    in the bass, equalised so the front speakers sound neutral, with the
    delay common to all of them removed and the level set so the front's
    two ears together carry unit energy."""

    def __init__(self, ir, pos, rate: float):
        from scipy.signal import resample_poly

        ir = np.asarray(ir, dtype=float)
        if rate != SR:
            from math import gcd
            g = gcd(int(SR), int(rate))
            ir = resample_poly(ir, int(SR) // g, int(rate) // g, axis=-1)
        taps = ir.shape[-1]

        # room to work in the frequency domain without wrapping round
        n_fft = 1 << int(np.ceil(np.log2(taps * 2)))
        spec = np.fft.rfft(ir, n_fft, axis=-1)
        freqs = np.fft.rfftfreq(n_fft, 1 / SR)

        # Flat below LF_FLAT_HZ: each response's level there, arriving when
        # that ear's sound does -- a clean pulse, so the interaural delay
        # stays and nothing smears out in time -- crossfaded into the
        # measurement over the octave above.
        peak = np.abs(ir).max(axis=-1, keepdims=True)
        arrival = np.argmax(np.abs(ir) > 0.1 * peak, axis=-1)[..., None]
        k = int(np.searchsorted(freqs, LF_FLAT_HZ))
        level = np.abs(spec[..., k:k + 1])
        clean = level * np.exp(-2j * np.pi * freqs * arrival / SR)
        w = np.clip((np.log2(freqs + 1e-9) - np.log2(LF_FLAT_HZ / 2)), 0.0, 1.0)
        w = 0.5 - 0.5 * np.cos(np.pi * w)          # 0 below f/2, 1 above f
        spec = spec * w + clean * (1.0 - w)

        # neutral front pair
        az = np.asarray(pos)[:, 0] % 360.0
        el = np.asarray(pos)[:, 1]
        front = []
        for target in (30.0, 330.0):
            d = np.abs(((az - target + 180.0) % 360.0) - 180.0) + np.abs(el) * 2
            front.append(int(np.argmin(d)))
        power = np.mean(np.abs(spec[front]) ** 2, axis=(0, 1))
        power = _smooth_third_octave(freqs, power)
        power[power <= 0] = 1e-12
        limit = 10 ** (FRONT_EQ_LIMIT_DB / 20)
        correction = np.clip(np.sqrt(power.mean() / power), 1 / limit, limit)
        ir = np.fft.irfft(spec * correction, n=n_fft, axis=-1)[..., :taps + 64]

        peak = np.abs(ir).max(axis=-1, keepdims=True)
        onsets = np.argmax(np.abs(ir) > 0.1 * peak, axis=-1)
        ir = ir[..., max(0, int(onsets.min()) - 4):]

        self.ir = ir
        self.az = np.radians(np.asarray(pos)[:, 0])
        self.el = np.radians(np.asarray(pos)[:, 1])
        self.dirs = np.stack([np.cos(self.el) * np.cos(self.az),
                              np.cos(self.el) * np.sin(self.az),
                              np.sin(self.el)], axis=1)
        front = self.at(np.array([1.0, 0.0, 0.0]))
        self.ir = self.ir / np.sqrt((front ** 2).sum())

    def at(self, direction) -> np.ndarray:
        """(2, taps): the nearest measured direction's response."""
        d = np.asarray(direction, dtype=float)
        d = d / np.linalg.norm(d)
        return self.ir[int(np.argmax(self.dirs @ d))]


def _images(room: dict, source: np.ndarray):
    """(position, reflection order) of every image of `source` up to
    MAX_ORDER, the source itself included (order 0)."""
    dims = np.asarray(room["dims"])
    out = []
    rng = range(-2, 3)
    for nx in rng:
        for ny in rng:
            for nz in rng:
                for ux in (0, 1):
                    for uy in (0, 1):
                        for uz in (0, 1):
                            n = np.array([nx, ny, nz])
                            u = np.array([ux, uy, uz])
                            order = int(np.sum(np.abs(n - u) + np.abs(n)))
                            if order > MAX_ORDER:
                                continue
                            pos = (1 - 2 * u) * source + 2 * n * dims
                            out.append((pos, order))
    return out


def speaker_pairs(head: Head, room_name: str):
    """{speaker: (direct (2, n), early (2, n))} for one room: the direct
    sound and the early reflections, each as the two ears hear them."""
    room = ROOMS[room_name]
    listener = np.asarray(room["listener"])
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    length = int(room["early_len"] * SR)
    out = {}
    for name, az in SPEAKER_AZ.items():
        a = np.radians(az)
        src = listener + room["distance"] * np.array([np.cos(a), np.sin(a), 0.0])
        direct = np.zeros((2, freqs.size), dtype=complex)
        early = np.zeros((2, freqs.size), dtype=complex)
        for pos, order in _images(room, src):
            vec = pos - listener
            r = float(np.linalg.norm(vec))
            delay = (r - room["distance"]) / C
            if delay > room["early_len"] - 0.01:
                continue
            gain = room["distance"] / r * room["beta"] ** order
            lp = (1.0 / np.sqrt(1.0 + (freqs / room["hf_cut"]) ** 2)) ** order
            if order:
                f4 = (freqs / REFLECTION_HIGHPASS_HZ) ** 4
                lp = lp * f4 / np.sqrt(1.0 + f4 ** 2)       # 4th-order high-pass
            spec = np.fft.rfft(head.at(vec), N_FFT, axis=-1)
            spec = spec * gain * lp * np.exp(-2j * np.pi * freqs * delay)
            if order == 0:
                direct += spec
            else:
                early += spec
        d = np.fft.irfft(direct, N_FFT, axis=-1)[:, :head.ir.shape[-1] + 8]
        e = np.fft.irfft(early, N_FFT, axis=-1)[:, :length]
        # the early file ends in a short fade, where the tail takes over
        fade = int(0.01 * SR)
        e[:, -fade:] *= np.linspace(1.0, 0.0, fade)
        out[name] = (d, e)
    return out


def equalise(pairs: dict, room_name: str, tail: np.ndarray) -> dict:
    """Tone-correct a room as a whole, so what reaches the ears from the
    front pair -- speakers, reflections and tail together -- is neutral, as
    room correction does for real speakers. Without it the reflections,
    which carry no bass, tilt the bigger rooms thin and bright. One curve,
    the same for every speaker and both ears (the cues are left alone),
    smoothed over a third of an octave and limited to +-8 dB."""
    room = ROOMS[room_name]
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    tail_power = np.mean(np.abs(np.fft.rfft(tail, N_FFT, axis=-1)) ** 2, axis=0)
    power = np.zeros(freqs.size)
    for spk in ("FL", "FR"):
        d, e = pairs[spk]
        # speaker and reflections add up as they really do, dips and all;
        # the tail is diffuse, so its energy simply adds
        n = max(d.shape[-1], e.shape[-1])
        both = np.zeros((2, n))
        both[:, :d.shape[-1]] += d
        both[:, :e.shape[-1]] += e
        coherent = np.abs(np.fft.rfft(both, N_FFT, axis=-1)) ** 2
        late = tail_power * (10 ** (room["late_db"] / 10) * (d ** 2).sum())
        power += coherent.mean(axis=0) + late
    band = (freqs > 40) & (freqs < 16000)
    power = _smooth_third_octave(freqs, power)
    power[power <= 0] = 1e-12
    target = power[band].mean()
    corr = np.clip(np.sqrt(target / power), 10 ** (-8 / 20), 10 ** (8 / 20))
    corr[freqs <= 40] = corr[np.argmax(freqs > 40)]
    corr[freqs >= 16000] = corr[np.argmax(freqs >= 16000) - 1]
    out = {}
    for spk, (d, e) in pairs.items():
        dd = np.fft.irfft(np.fft.rfft(d, N_FFT, axis=-1) * corr, N_FFT, axis=-1)
        ee = np.fft.irfft(np.fft.rfft(e, N_FFT, axis=-1) * corr, N_FFT, axis=-1)
        # the correction is short; a little room either side for its ringing
        out[spk] = (dd[:, :d.shape[-1] + 256], ee[:, :e.shape[-1]])
    return out


def late_tail(room_name: str, seed: int = 11) -> np.ndarray:
    """(2, n) diffuse tail: decorrelated noise per ear, its highs dying
    away faster than its lows as in a real room, starting at the room's
    mixing time with a short fade-in. Unit energy per ear."""
    room = ROOMS[room_name]
    t60 = room["t60"]
    n = int((room["mix_time"] + t60 * 1.2) * SR)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    out = np.zeros((2, n))
    freqs = np.fft.rfftfreq(n, 1 / SR)
    # three bands, the top one decaying twice as fast as the bottom
    bands = ((TAIL_HIGHPASS_HZ, 500, 1.15), (500, 4000, 1.0),
             (4000, SR / 2 + 1, 0.55))
    for ear in range(2):
        for lo, hi, k in bands:
            noise = np.fft.rfft(rng.standard_normal(n))
            noise[(freqs < lo) | (freqs >= hi)] = 0
            band = np.fft.irfft(noise, n)
            out[ear] += band * np.exp(-6.9078 * t / (t60 * k))
    start = int(room["mix_time"] * SR)
    ramp = int(0.012 * SR)
    env = np.zeros(n)
    env[start:start + ramp] = np.linspace(0.0, 1.0, ramp)
    env[start + ramp:] = 1.0
    out *= env
    out /= np.sqrt((out ** 2).sum(axis=1, keepdims=True))
    return out


# The 14-channel layout HeSuVi uses (and the graph reads): for each
# channel, (speaker, ear 0 = left / 1 = right). HeSuVi splits the centre in
# two; the graph doubles it back.
HESUVI_LAYOUT = [("FL", 0), ("FL", 1), ("SL", 0), ("SL", 1), ("BL", 0),
                 ("BL", 1), ("FC", 0), ("FR", 1), ("FR", 0), ("SR", 1),
                 ("SR", 0), ("BR", 1), ("BR", 0), ("FC", 1)]


def room_channels(pairs: dict, scale: float) -> np.ndarray:
    """(28, n): the direct sound in HeSuVi layout (channels 0-13), then the
    early reflections in the same layout (14-27)."""
    n = max(max(d.shape[-1], e.shape[-1]) for d, e in pairs.values())
    out = np.zeros((28, n))
    for part in (0, 1):
        for i, (spk, ear) in enumerate(HESUVI_LAYOUT):
            resp = pairs[spk][part][ear] * scale
            if spk == "FC":
                resp = resp * 0.5
            out[part * 14 + i, :resp.size] = resp
    return out


def write_wav(path: str, channels: np.ndarray):
    """16-bit WAV; the caller has made sure it fits."""
    import wave
    peak = np.abs(channels).max()
    if peak > 0.99:
        raise ValueError(f"{path}: peak {peak:.2f} would clip")
    data = np.round(channels.T * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(channels.shape[0])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
