# Spatial Linux — technical notes

How the app works, and the reasons behind some of its decisions. For
installing and using it, see the [README](../README.md).

## How it works

When it is switched on, the app starts a **separate PipeWire client
process** in the background, as `pipewire -c <conf>`. That process creates a
virtual output device called `Spatial Linux`, makes it the system default,
processes the sound and sends it on to the real hardware.

**When it is switched off**, that process is stopped and the default output
is set back to the device that was in use before. PipeWire automatically
removes every node, port and link whose owner has gone, so nothing is left
behind. This is guaranteed in three places:

- `SpatialEngine.stop()` — a normal shutdown ([engine.py](../spatiallinux/engine.py))
- `app.py` — every exit path, including SIGINT/SIGTERM and **unexpected
  errors**
- `_recover_from_previous_crash()` — even if the app is killed, the next
  launch cleans up whatever was left

The sound chain is an explicit **2-in / 2-out stereo graph** (not the mono
graph PipeWire duplicates automatically), because the stereo width and
cross-feed stages have to work across the channels. Every user control is
wired to a control port that can be written live, so **no setting ever
rebuilds the graph**: the sound never drops out, and even loading a preset
is seamless.

### How 3D Surround works

The aim is to take the sound out of the headphones and **place it in the
room**. Instead of a synthetic head model, it uses the **real measured HRTF**
data that is already on the system: the MIT KEMAR dummy-head measurement,
libmysofa's default set. Because a real outer ear was measured, it carries
the cues that tell front from back — something no analytic model can
provide.

PipeWire's filter-chain is not built with libmysofa in this setup (there is
no `sofa` node), so the SOFA file is read in [ir.py](../spatiallinux/ir.py)
and turned into a 6-channel WAV that the convolver can use. This is done
once, by [`tools/build_ir.py`](../tools/build_ir.py), and the result ships
with the app as `spatiallinux/data/binaural_ir.wav` — so users get the
measured head model without installing NumPy, h5py or libmysofa. (If that
file is ever missing, the app builds one itself: from the measurement when
those packages are present, otherwise from a simpler analytic head model.)
The front cross-feed and the rear speakers + room are kept in separate
channels, so the 3D Reverb slider can turn the room down on its own:

1. **Diffuse-field equalisation** — a raw measurement also contains the
   colouring of the measurement rig itself; in the MIT KEMAR set this showed
   up as a harsh **+18 dB** peak around 3 kHz. Dividing by the average over
   all directions removes this shared colouring and leaves only the
   direction-dependent cues (the response comes down to ±4 dB).
2. **The front speakers** contribute only to the *opposite* ear; the near
   ear keeps the dry signal — this is what keeps the stage transparent.
3. **The rear speakers** (±110°) are rendered to both ears with a delay;
   measured, they arrive at 12.2 ms, so they really come from behind.
4. Because the direct sound stays dry and all the cues arrive later,
   raising the intensity can never put the original signal through a comb
   filter. When it is off, the leak into the other channel is exactly
   **0.000**.

The intensity was tuned by measurement. The strength of the effect comes
from three separate paths, and since they can cancel each other out they
were balanced separately:

- **Width** is applied not to the whole side signal but only to the *added
  part* (`side + highpass(side × (width−1))`). At width 1 the chain is
  therefore exactly transparent, and above it the added width is filtered
  so the bass stays in the centre. Splitting the side signal and boosting
  its upper half did not work: no crossover is sharp enough, and at the
  widths this mode reaches, the leftover bass came through strongly enough
  to hollow out the low end.
- **The cross-feed** makes the image more solid but pulls the two channels
  towards each other; **the rear speakers and the room** only add
  envelopment. That is why they have separate gains — it is how the effect
  gets stronger without collapsing towards mono.
- **The bass is filtered out completely** in the rear and room paths
  (220 Hz, two poles). Bass carries almost no directional information;
  sending it around the head only widens and hollows the low end.
- Room reflections are placed as **short diffuse bursts** rather than
  discrete taps. Four discrete reflections made an obvious comb filter; the
  hundreds of reflections in a real room fill in the gaps.
- The rear/room energy is **pinned as a ratio** of the front cue. Left to
  itself it ran to eight times the front and swamped the image.

The treble stays flat relative to the midrange (±0.3 dB). 3D also carries
**3% reverb** of its own — too little to hear as reverb, but it helps the
image sit outside the head.

#### Why the crackle in the treble went away

The treble used to be too far forward in 3D, with a faint crackle.
Measuring it turned up three causes:

- **Clipping.** 3D adds energy to the sound. On a loudly mastered song the
  peaks rose to **+4 dBFS** and hit the limiter. Because the limiter is a
  hard clamp, this turned into a crackle heard in the treble (815 clipped
  samples in 8 seconds). 3D now lowers its own level as it rises (−4 dB at
  full intensity): clipping is **zero**.
- **Air shelf.** A +2.5 dB shelf at 9 kHz tilted the treble upwards
  (+2.6 dB at 16 kHz at full intensity). It was removed; the image is not
  dull without it.
- **Comb filter.** Above 8 kHz the cross-feed interfered with the dry sound
  and produced dense ripple of +6/−14 dB, heard as a metallic sizzle. The
  cues are now filtered above 8 kHz, and the ripple comes down to ±2.8 dB
  at the default intensity. The spatial effect stays almost the same (10%
  less).

This is why the sound is slightly quieter with 3D on. Just turn the volume
up — it can now go up without clipping.

The **Subwoofer (LFE)** slider sits inside the 3D panel: it comes on with
the 3D mode and goes off with it.

### How Night Mode works

Night mode is an **equaliser curve**: as the slider rises, your own EQ
settings are pulled further and further down — most in the midrange (where
the ear tires first), least at the very top and bottom. Your EQ itself does
not change; only the value sent to the sound drops, and it comes back
exactly as it was when the mode is switched off.

On top of that there is dynamic softening: an envelope-following
compressor raises quiet sounds and lowers loud ones, so the overall level
goes down without losing detail.

This compressor was fixed twice, both times caught by measurement:

1. **Pinning to a reference.** The power function raised everything, so
   night mode made the sound *louder* — the opposite of its purpose. Now
   −12 dBFS stays fixed: below it goes up, above it comes down.
2. **Envelope following.** The function was applied to individual samples,
   which bends the waveform and so produces **harmonic distortion**.
   Measured: **8.7% THD** — the reason the sound came across as harsh and
   scratchy. The gain now follows the **level** rather than the waveform,
   and the distortion is **0.13%**.

   The same measurement showed that night mode lowering the limiter ceiling
   drove its own gain straight into that ceiling and caused clipping; it no
   longer lowers the ceiling.

### Animations

Every mode has its own scene ([art.py](../spatiallinux/ui/art.py)); all are
drawn as vectors in a neon style: glowing lines on near-black, and figures
filled with translucent light instead of flat colour.

- **3D Surround** — flat rings slowly turn into a glowing sphere and flatten
  again; orbits rotate with points of light travelling along them, and the
  speaker labels spread out as the intensity rises.
- **Bass Boost** — a person in headphones nods to the beat; with every beat,
  waves spread from the headphones and the floor lights up.
- **Fidelity** — lips sing (the syllables are not evenly spaced, like a real
  sentence), the words float upwards, and a clean waveform comes out of the
  mouth.
- **Night Mode** — a figure in headphones breathes out with eyes closed;
  the shoulders sink with a long breath, the breath drifts away, with a
  moon and stars behind.
- **Ambience** — the sound going out into the room and coming back off
  the walls.

Beyond these, the window changes height along a smooth curve when a mode
panel opens or closes, the equaliser curve flows into its new shape when a
preset loads, and the power button pulses while the engine is running.

Qt has no bloom filter; the glow is made the way it is in vector art, by
drawing the same shape in progressively wider and fainter passes and laying
the crisp line on top. This is not cheap — the first version burned **161%
CPU** with one panel open. Measured and brought down to **30%** with a
frame rate per scene (slow scenes at 20 fps), fewer passes, antialiasing
switched off for the blurred passes, and unnecessary radial gradients
removed. With the panel closed the timers stop: **0.0%**.

### Why there is no Spatial Stereo or Pitch

**Spatial Stereo** in Boom 3D looks like a separate feature, but what it
does is widen the stereo image — the same thing as the first stage of 3D
Surround. Rather than two separate buttons that each do half the job, there
is one 3D mode that does it properly.

**Pitch** (pitch shifting) genuinely cannot be done. Real pitch shifting
needs a phase vocoder or time-stretching, and PipeWire's built-in filter set
(biquad, convolver, delay, mixer, clamp, linear, log/exp, mult) has **no**
primitive for it. Rather than a button that does not work, there is none.
If it is ever really wanted, it would need a separate LV2/LADSPA plugin
built on a library such as `rubberband`.

## Presets (file format)

JSON files in `presets/`: `flat`, `music`, `movie`, `gaming`, `night`,
`bass`. In the interface they are named in the selected language (Flat,
Music, Movie, Gaming, Night, Bass in English; Düz, Müzik, Film, Oyun, Gece,
Bas in Turkish). User presets are saved under
`~/.local/share/spatiallinux/presets/` and override a built-in preset of the
same name. Presets written with an older layout still load — unknown fields
are ignored, missing fields keep their defaults, and the old
`night: true/false` is converted to a number automatically. Each preset also
says, in its `active` field, which mode it switches on.

### Settings that silently went missing

Loading a preset changed the interface but not the sound. The reason:
PipeWire's Props message carries its parameters in a fixed-size structure,
and past roughly 25 parameters the whole message is dropped — and since
`pw-cli` still returns success, the failure is **completely silent**.
`apply_all` was sending 51 parameters, so it never worked at all. It was
found by measurement (24 go through, 28 do not), and the parameters are now
sent in chunks of 16.
