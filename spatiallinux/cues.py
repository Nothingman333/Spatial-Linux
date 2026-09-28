"""Short sounds that confirm a noise-cancelling change.

Sony's headphones announce a change made with their button, but stay silent
when it comes from an app -- so Spatial Linux plays its own. Each one says
what happened:

* noise cancelling: a whoosh closing down, from bright to dark, the outside
  fading away, with two notes falling -- sealed in;
* ambient sound: the same whoosh opening up and three notes rising -- the
  room coming back in;
* off: two short, neutral ticks.

Synthesised here (standard library only), written once into the data
folder, and played with PipeWire's own pw-play on the host.
"""

from __future__ import annotations

import math
import os
import random
import struct
import subprocess
import threading
import wave

SR = 48000
PEAK = 0.35                      # well below full scale: a hint, not an alarm
VERSION = 1                      # bump when the sounds change


def _tone(freq: float, start: float, length: float, level: float,
          out: list[float]):
    """A soft bell-like note: a sine with a touch of its octave, a 5 ms
    attack and an exponential fade."""
    n0, n = int(start * SR), int(length * SR)
    for i in range(n):
        t = i / SR
        env = min(1.0, t / 0.005) * math.exp(-t * 7.0 / length)
        v = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(4 * math.pi * freq * t)
        if n0 + i < len(out):
            out[n0 + i] += level * env * v


def _whoosh(length: float, f_from: float, f_to: float, level: float,
            out: list[float], seed: int):
    """Noise through a low-pass whose cutoff glides from f_from to f_to,
    swelling in and out: air rushing, closing or opening."""
    rnd = random.Random(seed)
    n = int(length * SR)
    lp1 = lp2 = 0.0
    for i in range(min(n, len(out))):
        x = i / n
        cutoff = f_from * (f_to / f_from) ** x
        a = 1.0 - math.exp(-2 * math.pi * cutoff / SR)
        lp1 += a * (rnd.uniform(-1, 1) - lp1)
        lp2 += a * (lp1 - lp2)
        env = math.sin(math.pi * x) ** 2
        out[i] += level * env * lp2 * 3.0


def _render(kind: str) -> list[float]:
    if kind == "nc":
        out = [0.0] * int(0.75 * SR)
        _whoosh(0.55, 7000.0, 250.0, 1.0, out, 3)
        _tone(784.0, 0.18, 0.35, 0.45, out)       # G5
        _tone(523.25, 0.34, 0.40, 0.45, out)      # C5
    elif kind == "ambient":
        out = [0.0] * int(0.75 * SR)
        _whoosh(0.55, 250.0, 7000.0, 1.0, out, 5)
        _tone(523.25, 0.14, 0.30, 0.40, out)      # C5
        _tone(659.25, 0.26, 0.30, 0.40, out)      # E5
        _tone(783.99, 0.38, 0.36, 0.40, out)      # G5
    else:
        out = [0.0] * int(0.35 * SR)
        _tone(587.33, 0.00, 0.12, 0.5, out)       # D5, twice
        _tone(587.33, 0.13, 0.16, 0.5, out)
    peak = max(abs(v) for v in out) or 1.0
    return [v * PEAK / peak for v in out]


def path(kind: str, folder: str) -> str:
    """The cue's file, made on first use."""
    p = os.path.join(folder, f"cue_{kind}_v{VERSION}.wav")
    if not os.path.exists(p):
        os.makedirs(folder, exist_ok=True)
        samples = _render(kind)
        tmp = p + ".tmp"
        with wave.open(tmp, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(b"".join(struct.pack("<h", int(v * 32767))
                                   for v in samples))
        os.replace(tmp, p)
    return p


def play(kind: str, folder: str, host_command):
    """Play a cue in the background, through the default output."""
    def run():
        try:
            file = path(kind, folder)
            for player in (["pw-play", file], ["paplay", file]):
                try:
                    subprocess.run(host_command(player), timeout=5,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, check=True)
                    return
                except (OSError, subprocess.SubprocessError):
                    continue
        except OSError:
            pass
    threading.Thread(target=run, daemon=True).start()
