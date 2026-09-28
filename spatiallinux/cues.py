"""Short sounds that confirm a noise-cancelling change.

Sony's headphones announce a change made with their button, but stay silent
when it comes from an app -- so Spatial Linux plays its own. Each one says
what happened:

* noise cancelling: a deep, soft thump and a whoosh closing down to dark,
  with two low notes falling -- the outside shut out;
* ambient sound: the whoosh opening up and two notes rising -- the room
  coming back in;
* off: two short, low, neutral ticks.

Kept low and soft on purpose (the first version was found too bright and
too loud): no content above a few kHz, and well under full scale.

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
# about -22 dBFS: a hint, not an alarm. (0.35 at first, then 0.21; both
# were found too loud -- this is 60% below the second.)
PEAK = 0.084
VERSION = 3                      # bump when the sounds change


def _tone(freq: float, start: float, length: float, level: float,
          out: list[float]):
    """A soft, round note: a sine with a trace of its octave, a 12 ms
    attack and an exponential fade."""
    n0, n = int(start * SR), int(length * SR)
    for i in range(n):
        t = i / SR
        env = min(1.0, t / 0.012) * math.exp(-t * 6.0 / length)
        v = math.sin(2 * math.pi * freq * t) + 0.08 * math.sin(4 * math.pi * freq * t)
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


def _thump(start: float, out: list[float], level: float):
    """A deep, soft thud: a sine gliding from 140 Hz down to 55 Hz as it
    dies away -- the "tok" of a door closing on the outside."""
    n0, n = int(start * SR), int(0.28 * SR)
    phase = 0.0
    for i in range(n):
        t = i / SR
        freq = 55.0 + 85.0 * math.exp(-t / 0.05)
        phase += 2 * math.pi * freq / SR
        env = min(1.0, t / 0.004) * math.exp(-t / 0.07)
        if n0 + i < len(out):
            out[n0 + i] += level * env * math.sin(phase)


def _render(kind: str) -> list[float]:
    if kind == "nc":
        out = [0.0] * int(0.8 * SR)
        _whoosh(0.45, 2500.0, 120.0, 0.7, out, 3)
        _thump(0.30, out, 1.0)
        _tone(329.63, 0.30, 0.40, 0.30, out)      # E4
        _tone(220.00, 0.42, 0.40, 0.30, out)      # A3
    elif kind == "ambient":
        out = [0.0] * int(0.75 * SR)
        _whoosh(0.50, 150.0, 2500.0, 0.7, out, 5)
        _tone(392.00, 0.20, 0.35, 0.35, out)      # G4
        _tone(523.25, 0.34, 0.40, 0.35, out)      # C5
    else:
        out = [0.0] * int(0.35 * SR)
        _tone(293.66, 0.00, 0.12, 0.5, out)       # D4, twice
        _tone(293.66, 0.13, 0.16, 0.5, out)
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
