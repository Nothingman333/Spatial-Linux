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

The sound chain is an explicit **8-in / 2-out graph** (not the mono graph
PipeWire duplicates automatically): the device takes **7.1**, and the stereo
width and cross-feed stages have to work across the channels. Every user
control is wired to a control port that can be written live, so **no
setting rebuilds the graph**: the sound never drops out, and even loading a
preset is seamless. The one exception is the choice of 3D head (below): the
convolvers' files are fixed when the graph starts, so switching heads
restarts it, a moment of silence.

In order, the graph is: the 3D stage (the front pair) and the placement of
the other surround channels → the tone chain (pre-amp, equaliser, bass,
fidelity, subwoofer) → ambience → treble → night mode → headphone
correction → limiter. The tone chain used to come first;
every stage in it is linear and identical on both channels, so moving it
after the 3D stage changes nothing for stereo (checked in a sample-by-sample
simulation of the old and new graphs: the largest difference was 10⁻¹²,
rounding), and it means the surround channels are equalised too.

### Surround sources (5.1 / 7.1)

Before 2.0 the device was stereo, so a game or film playing 5.1 or 7.1 was
folded down to two channels by PipeWire before Spatial Linux ever saw it,
and the rear channels ended up in front. The device now takes 7.1
(`FL FR FC LFE RL RR SL SR`), and each channel is heard from its own place:

- **Front left / right** go through the 3D stage exactly as stereo does.
- **Centre** is added to both ears dry, at −3 dB, like a phantom centre
  between the front pair.
- **LFE** is kept below 120 Hz and added to both ears at −6 dB.
- **Side and back pairs** are convolved with the measured head's responses
  from 100° and 135° (the side pair of 7.1, and between the 110° a 5.1
  source expects and the 150° of a 7.1 back pair), near and far ear, each
  pair scaled to the energy a −3 dB downmix would give it, so switching
  between the two neither jumps nor drops in level.

**Stereo does not change.** PipeWire's default (`channelmix.upmix-method =
none`, and no centre or LFE cut-off) keeps a stereo stream on FL/FR of a 7.1
device and leaves the other channels silent (see `channelmix-ops.c`), so
for stereo those paths carry nothing. Someone who has turned on PipeWire's
own upmixing (`psd` or `simple`) will now hear what it produces placed
around them too.

### 3D heads

Heads differ as ears do, so the one that sounds most "in front of you and
outside your head" differs from listener to listener. There are two,
chosen in the Headphones panel:

- **KEMAR** — the MIT KEMAR measurement, the original sound.
- **KU 100** — SADIE II subject D1, a Neumann KU 100 dummy head (University
  of York, Apache License 2.0; see `spatiallinux/data/LICENSE-SADIE-II.txt`).
  It is read from the copy OpenAL Soft ships (`Default HRTF.mhr`, format
  `MinPHR03`): minimum-phase responses with the arrival delays stored apart,
  in quarter samples, which `ir.load_mhr` puts back with a fractional-delay
  phase shift. The right ear is the mirror image of the left, as OpenAL
  Soft does it.

Both go through the same pipeline (diffuse-field equalisation, bulk delay
removed, the same speaker directions), and the KU 100's cross-feed is scaled
to exactly the KEMAR's energy, so switching heads changes the character of
the 3D stage and not its strength. Measured on the built files: the side
speaker reaches the far ear 0.5 ms (KEMAR) / 0.7 ms (KU 100) after the near
one and 13 / 17 dB quieter, as a real head does.

### Your own HRIR file

"Own file" runs every channel through an HRIR file in the **HeSuVi**
layout instead of Spatial Linux's own 3D stage. A 14-channel file uses the
same mapping as PipeWire's own `sink-virtual-surround-7.1-hesuvi.conf` (the
centre at ×2 because HeSuVi splits it in two, the LFE on the centre's
responses at half that). A 7-channel file is HeSuVi's symmetric kind: it
holds FL-L, FL-R, SL-L, SL-R, BL-L, BL-R and FC-L, and the right-hand
speakers use the left-hand ones with the ears swapped. The 3D intensity crossfades between the plain downmix and the
rendered sound. Spatial Linux ships no such files: many of the popular ones
were recorded from commercial virtualisers and carry no licence, so the
listener brings their own. The file is copied into the data folder, where
the (host's) PipeWire can read it.

### Sony noise cancelling

Sony's headphones take commands over a Bluetooth RFCOMM channel of their
own, the one their phone app uses. The protocol is not published; Spatial
Linux follows how Gadgetbridge, the open-source Android companion, talks to
them ([`sony.py`](../spatiallinux/sony.py)), with only Python's own `socket`
module:

- **Finding the headphones.** The Bluetooth outputs PipeWire knows
  (`api.bluez5.address`), the one in use first.
- **Finding the channel.** It is not fixed, so the headphones' SDP server
  (L2CAP PSM 1) is asked where the Sony service is (UUID `956C7B26-…`, or
  `96CC203E-…` on older models): one ServiceSearchAttribute request for the
  protocol descriptor list, parsed by hand rather than depending on
  libbluetooth.
- **Talking.** Frames are `0x3E`, escaped `[type, sequence, length,
  payload, checksum]`, `0x3C`; every command is ACKed with the next sequence
  number, both ways. An init command starts the session, and the length of
  its reply tells protocol v1 (WH-1000XM3/XM4) from v2 (WH-1000XM5,
  WF-1000XM4/XM5, LinkBuds).
- **The setting.** Ambient sound control, `0x68` (set) / `0x66` (get): on
  or off, then noise cancelling or ambient sound, focus on voice, and the
  ambient level (20 of 20).

Every attempt is written to `~/.local/share/spatiallinux/noise-cancelling.log`
(the devices seen, the channel, and what the system reported), for when
the headphones cannot be reached. The card only shows headphones that have
answered; the headphones panel lets them be picked by hand.

It runs in a background thread, once when the app starts (and, while no
headphones have been found, again when the window comes back to the front,
at most every half minute). A glass card in the header shows the mode,
ambient level and Conversation (focus on voice) read from the headphones,
and a spinner while it talks to them; it appears only when they are found.
Noise cancelling itself has no strength field in the command (the
headphones adapt it on their own), so only ambient sound has a slider.

The headphones announce a mode change made with their button, but not one
made by an app, so Spatial Linux confirms each change with a short sound of
its own ([`cues.py`](../spatiallinux/cues.py)): synthesised once with the
standard library into the data folder (a filtered-noise whoosh whose
cut-off closes or opens, and soft bell-like notes falling or rising; two
ticks for off) and played with `pw-play`. Checked against a simulated headset and
the byte sequences known from Gadgetbridge (the init frame is
`3e 0c 00 00 00 00 02 00 00 0e 3c`), not yet against every model.

### Headphone correction

An AutoEQ `ParametricEQ.txt` (the format Equalizer APO reads too) evens out
the headphones' own response. It sits after everything else and before the
limiter, where a correction belongs. To load any file live, the bank has 10
slots, each a peaking, a low-shelf and a high-shelf filter in a row: the
file's filter uses the one of its kind and the other two stay at 0 dB, where
a biquad is exactly transparent. The file's pre-amp is applied first.

### Speakers in a room

The "classic" 3D keeps the direct sound dry and adds cues around it: clear
and close, but still recognisably headphones. The room styles (Studio,
Living room, Cinema) do what headphone virtualisers of the Dolby Atmos for
Headphones kind do instead: they play every channel from a **virtual
speaker in a room**, built in [`tools/room.py`](../tools/room.py):

1. **The direct sound** of each speaker (the 7.1 layout: ±30°, 0°, ±100°,
   ±142°), through the measured head from its direction.
2. **Early reflections** off the walls, floor and ceiling, from the
   image-source method (Allen & Berkley) up to the third order — each one
   rendered with the head's response *from the direction it arrives
   from*, above and below included, which is where the sense of height
   comes from; later ones darker, as real surfaces absorb the highs.
3. **The late reverberation**, which carries no direction, once for all
   channels: decorrelated noise per ear whose highs die away faster than
   its lows, taking over at the room's mixing time.

| Room | Size | Speakers | Reverb time |
|---|---|---|---|
| Studio | 5 × 4.2 × 2.8 m, treated | 1.4 m | 0.25 s |
| Living room | 6 × 4.6 × 2.7 m | 2 m | 0.45 s |
| Cinema | 14 × 10 × 6 m | 4 m | 0.9 s |

Measured, the first versions of this sounded thin and boomy: dummy-head
data is weak in the bass (the MIT KEMAR set is 9 dB down at 63 Hz), and
reflections in the bass made a 6 dB hole at 125 Hz in the living room. So:
the head's responses are made flat below 250 Hz (a clean pulse at each
ear's own arrival time, so the interaural delay stays); reflections and
the tail carry no bass (a 4th-order high-pass at 220 / 150 Hz); the head is
equalised so the front pair of speakers sounds neutral; and each room gets
one overall tone correction, like room correction on real speakers, from
the speakers and reflections as they actually add up. Result, with stereo
pink noise through both ears: within about ±2 dB from 40 Hz to 16 kHz for
every room and both heads — as flat as the classic 3D — and each room is
set to exactly the classic 3D's loudness, so switching compares the sound
and not the level.

In the 3D panel, the intensity is how much of the room is heard with the
speakers (its natural amount at the default 65%; at 0% the mode is off and
the sound is plain), and Reverb sets the tail on its own. The files
(direct sound in channels 0–13, reflections in 14–27, HeSuVi layout, so the
graph wires them like an own HRIR file) are built for both heads.

### How 3D Surround works

The aim is to take the sound out of the headphones and **place it in the
room**. Instead of a synthetic head model, it uses the **real measured HRTF**
data that is already on the system: the MIT KEMAR dummy-head measurement,
libmysofa's default set. Because a real outer ear was measured, it carries
the cues that tell front from back — something no analytic model can
provide.

PipeWire's filter-chain is not built with libmysofa everywhere (there is
often no `sofa` node), so the SOFA file is read in [ir.py](../spatiallinux/ir.py)
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
panel opens or closes (and the panel fades up as it does), the equaliser
curve flows into its new shape when a preset loads, and the power button
floods white from its symbol when switched on and pulses while the engine
is running.

**The header** ([hero.py](../spatiallinux/ui/hero.py)) is a picture of
light streaks that flows: far streaks drifting slowly, near ones faster,
sparks falling through them, a bloom that sways and a band of light that
sweeps across now and then. Each layer is drawn once per size, seamless at
its ends, and then only slid along; a frame costs about 1 ms of drawing,
and the header runs at 30 fps, faster-flowing while Spatial Linux is on.
The glass controls on it are frosted for real: each frame the same layers
are also composed at a quarter of the size, blurred, and painted inside
each glass shape before the control draws itself.

**Choices** ([controls.py](../spatiallinux/ui/controls.py)) -- the mode
tabs, noise cancelling, the headphone options -- are each a glass pill, so
they read as options; the chosen one is a white thumb that slides to the
new choice, its leading edge leaving first and the trailing edge catching
up, and each option's text darkens exactly as far as the thumb covers it.

**The drop-downs** are frosted glass too: the window behind them is read
once as they open, blurred, tinted and drawn as their background. (Reading
it again while open kept the moving picture moving behind the glass, but
each read redrew everything under it and held up the other animations.)
They grow and fade in as they open.

**One clock.** Every animation -- the header, the mode scenes, the byline,
the power button -- runs on one shared timer, so everything that moves is
updated in the same moment and painted in one pass; with a timer each, they
ticked out of step and the window was repainted several times a frame, at
uneven moments, which showed as stutter. Motion is worked out from the real
time since the last frame, so a late frame does not make it hop, and the
header's layers are placed to a fraction of a pixel, so a slow drift does
not move in one-pixel steps.

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
