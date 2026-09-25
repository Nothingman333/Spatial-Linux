# Changelog

## v1.5.3

- Repository history condensed again. No changes to the app.

## v1.5.2

- The release workflow also clears out the workflow runs of commits that
  are no longer in the repository. No changes to the app.

## v1.5.1

- Repository history condensed into a single commit. No changes to the app.

## v1.5.0

- **The measured head model now ships with the app.** 3D Surround always
  uses the MIT KEMAR measurement; NumPy, h5py and libmysofa are no longer
  needed. PyQt6 is the only dependency. Anyone who had the simpler
  fallback model before gets the measured one automatically.
- The file is built with `tools/build_ir.py`. Credits for the KEMAR data
  (Bill Gardner and Keith Martin, MIT Media Lab) added to the README.

## v1.4.4

- New image at the top of the README.

## v1.4.3

- All documentation is now in English only: README, technical notes,
  changelog and release notes. The app itself still has both English and
  Turkish interfaces.

## v1.4.2

- README: **which Linux distributions it runs on** — any distribution using
  PipeWire 1.0 or newer. With a list of distributions, the ones that are not
  supported, and a command to check. Arch install commands added.
- Release notes explain what the `SHA256SUMS` file is for.

## v1.4.1

- README: **Updating** and **Uninstalling** sections. Downloading the latest
  release as a zip and copying its files over the old ones is enough;
  settings are kept.
- README and release notes state plainly, at the top: Spatial Linux does not
  touch sound drivers or system files, never needs root, and returns the
  sound to the original device when switched off.

## v1.4.0

- **New README**: screenshot first, then features, requirements,
  installation and usage. Technical notes moved to `docs/TECHNICAL.md`.
- Fix: unpacking a new release over an older one left the old Turkish-named
  presets (bas, gece, oyun) in the list, even in English. They are now
  hidden.
- Only the latest release is kept on the Releases page.

## v1.3.1

- The "by Sali" link goes to the repository's new address:
  github.com/Nothingman333/Spatial-Linux.

## v1.3.0

- **ⓘ How to use button**, next to the globe. Clicking it plays the
  introduction again.
- **"How to use" page in the introduction**: four steps, each shown with a
  numbered point that lights up as it arrives.
- Fix: with some system fonts the title was cut off as "SPATIAL LIN".

## v1.2.0

- **New name: Spatial Linux.** The app, window title, menu entry, sound
  device and downloads use the new name. Existing settings and saved presets
  are carried over automatically on first launch, and `install.sh` removes
  the old menu entry.
- **The introduction is now inside the window**: not a separate window, so
  it moves with the app.
- **New defaults**: 3D Surround on (50%, Subwoofer +5 dB, Reverb 100%,
  Treble 0), Ambience 5% / Treble −2 dB.
- **Presets in the selected language**: Flat, Music, Movie, Gaming, Night,
  Bass (Düz, Müzik, Film, Oyun, Gece, Bas in Turkish). The mixed-up file
  names were cleaned up.
- **Power button**: a power symbol instead of the word BOOM. The glow around
  it no longer gets clipped into a square.
- Fix: the Fidelity animation's lyrics stayed in Turkish in the English
  interface.

## v1.1.0

- **Introduction**: an animated intro that plays once on first launch. A
  welcome screen, then pages introducing each mode with its own animation.
  Next / Skip buttons and a language switch.
- **Settings are no longer lost**: every mode's last value, the power
  (BOOM) state and the volume are saved. Saving happens as things change,
  not only on close, so settings survive even if the app is killed or the
  session ends.
- **Treble control in the 3D and Ambience panels** (±6 dB).
- **3D Reverb control**: turns down 3D's rear speakers and room reflections
  on their own. At 100% the sound is exactly the same as before.
- **EQ On / Off**: the equaliser can be bypassed while keeping its curve.
  The Limiter button, which had no audible effect, was removed (the
  protection is always on).
- Ambience now starts at **15%**.
- The **version number** is shown under the title.
- Fix: the speaker labels in the 3D animation stayed in Turkish in the
  English interface.
- Fix: the output device showed as "Unknown" on some systems.

## v1.0.0

First release of BoomLinux: 3D sound enhancement for PipeWire.

- **3D Surround**: binaural rendering with a measured HRTF (MIT KEMAR), rear
  speakers, room, and a Subwoofer (LFE) control.
- **Ambience**, **Fidelity**, **Bass Boost**, **Night Mode**: one mode at a
  time, each mode remembers its last value.
- 10-band equaliser, Pre-Amp, limiter and presets. Settings are kept from
  one session to the next.
- English / Turkish interface.
- The crackle in the treble in 3D is fixed: no clipping, treble flat with
  the midrange.
- The **by Sali** text in the title glows softly and opens the project page.
- Bug fixes: the preset list showed the wrong preset at start-up, a `/` in a
  preset name closed the app, and "Bilinmiyor" ("Unknown") appeared in the
  English interface.
