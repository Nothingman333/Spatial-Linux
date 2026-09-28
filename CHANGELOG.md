# Changelog

## v2.0.0-beta.5

- **A sound for every noise-cancelling change.** Sony's headphones stay
  silent when the mode is changed from an app, so Spatial Linux plays its
  own: a whoosh closing down with two falling notes for noise cancelling,
  the same whoosh opening up with three rising notes for ambient sound, and
  two short ticks for off. Made by Spatial Linux itself, no sound files
  from elsewhere.
- **Ambient sound strength.** In ambient sound, a slider sets how much of
  the outside comes in (1–20, as in Sony's app), and **Focus on voice**
  lets voices through more than other sounds. Both are remembered. Noise
  cancelling has no strength setting: the headphones adjust it themselves
  and take no setting for it (Sony's app has none either); the panel says
  so.
- **Older releases are kept.** Publishing a new version no longer removes
  the previous ones; they can be cleared out on purpose later.

## v2.0.0-beta.4

- **Noise cancelling for Sony headphones.** With Sony headphones connected
  (WH-1000XM5 and relatives), the headphones panel shows their noise
  cancelling: **Noise cancelling / Ambient sound / Off**, the same setting
  as in Sony's phone app, read from the headphones when the panel opens.
  It talks to them directly over Bluetooth, the way the Sony app does,
  following Gadgetbridge's open implementation of Sony's protocol; nothing
  to install. Everything happens in the background, so the window never
  waits on Bluetooth.
- The Flatpak may now open Bluetooth connections (for the above).

## v2.0.0-beta.3

- **Own HRIR file: 7-channel files work too.** HeSuVi ships two kinds: 14
  channels, and 7 channels for symmetric heads (one side stored, the other
  its mirror image). Only the 14-channel kind was accepted, so many of
  HeSuVi's files were refused with "it has 7 channels". Both load now.
- **Clearer headphones panel.** "Own file" is one choice: picking it the
  first time asks for the file. The file in use, with a "Change file…"
  button, shows only while it is the choice; the separate "Choose HRIR
  file" row, which looked like a second, different option, is gone. The
  message for a wrong file now says what the right one looks like.

## v2.0.0-beta.2

- **Speakers in a room.** A new kind of 3D, chosen in the headphones panel:
  **Studio**, **Living room** or **Cinema**. Instead of headphones you hear
  speakers in front of you in that room: each speaker, and each reflection
  off the walls, floor and ceiling, from its own direction through the
  measured head (the floor and ceiling are where the sense of height comes
  from), then the room's own reverb. This is how Dolby Atmos for Headphones
  and similar virtualisers take sound out of your head. It works for stereo
  and for 5.1 / 7.1, with either head.
- Tuned by measurement to sound **neutral** (within about ±2 dB from 40 Hz
  to 16 kHz on music, as flat as the classic 3D) and to be **exactly as
  loud** as the classic 3D, so switching compares the sound, not the level.
- In a room, the 3D intensity is how much of the room you hear with the
  speakers, and Reverb sets the room's tail.
- The **3D sound** choice (Classic, Studio, Living room, Cinema, Own file)
  and the **3D head** are now two separate rows in the headphones panel.
- The A/B button is gone.

## v2.0.0-beta.1

A test release of the next big version. The stable 1.10.4 stays available
as **Latest** on the Releases page. Built on a research round comparing
the open ways to get closest to Dolby Atmos for Headphones on Linux; this
beta takes the parts that fit Spatial Linux today.

- **Real 5.1 / 7.1 surround.** The Spatial Linux device now takes 7.1, so a
  game or film playing surround reaches it with every channel apart instead
  of already folded into stereo. The centre is heard in the middle, the
  side and back channels from beside and behind you, each through the
  measured head from its own direction. **Stereo sounds exactly as
  before** (checked sample by sample against 1.10.4).
- **Choose the 3D head.** Next to the MIT KEMAR head there is now a
  Neumann KU 100 (SADIE II, University of York). Heads differ like ears
  do: pick the one that puts the sound most clearly in front of you. Both
  are matched in strength, so switching changes the character, not the
  amount.
- **Your own HRIR file.** Load a 14-channel HRIR file in the HeSuVi layout
  and every channel runs through it. Spatial Linux ships none of those
  files; many were recorded from commercial virtualisers and carry no
  licence.
- **Headphone correction.** Load the AutoEQ `ParametricEQ.txt` for your
  headphone model (autoeq.app) to even out its own sound, On / Off at any
  time, without a gap.
- **A/B.** Hold the new A/B button to hear the original sound without any
  processing; let go to hear Spatial Linux again.
- All of these are in the new **headphones button** in the header. They
  belong to you and your headphones, not to a sound, so they are kept in
  the settings rather than in presets.
- Switching the 3D head restarts the sound for a moment; everything else
  still changes live.

## v1.10.4

- **Steadier sound under load**: the audio processing now asks for
  real-time priority, as PipeWire's own services do, so a busy system
  (a game, a compile) is less likely to cause crackles or dropouts.
- **Never processed twice**: switching on while another Spatial Linux (the
  normal version and the Flatpak side by side) is already on used to route
  one into the other, applying every effect twice. It now says so instead.
- Commands to PipeWire are sent from a background thread, so the window
  never waits on them. This matters most in the Flatpak, where each one
  goes through `flatpak-spawn`.

## v1.10.3

- Fix: the Flatpak did not play the introduction on its first start if
  the normal version had been used before, because the two share their
  settings. The Flatpak now remembers the introduction on its own.

## v1.10.2

- README: the "Which Linux?" table now has a column each for the normal
  download and the Flatpak, instead of a separate list above it. No
  changes to the app.

## v1.10.1

- README: the "Which Linux?" section now lists both ways to install,
  the normal download and the Flatpak, and no longer says Bazzite needs a
  container. No changes to the app.

## v1.10.0

- **Flatpak.** Each release now also has `spatiallinux.flatpak`: install it
  with `flatpak install --user spatiallinux.flatpak`. PyQt6 is inside, so
  nothing is downloaded at first start. It drives your PipeWire with the
  system's own tools (through `flatpak-spawn`) and shares its settings with
  the normal version.
- **A real progress window for the one-time download** of PyQt6 when
  Spatial Linux is started from the menu (kdialog on KDE, zenity on GNOME):
  percentage and which file is downloading. In a terminal, a progress bar.
- Fix: the logo beside the name was cropped on HiDPI (scaled) screens.

## v1.9.0

- **Installs the same way everywhere, Bazzite included — no container.**
  If the system has no PyQt6, Spatial Linux downloads it once (about 90 MB)
  into its own folder (`~/.local/share/spatiallinux/pyenv`) and runs from
  there: no root, no sudo, nothing installed system-wide. `install.sh` does
  this step with a progress bar, so the first start from the menu is
  instant; started from the menu instead, it shows a notification while it
  gets ready. A system PyQt6, where there is one, is still used first.
- On the host, Qt now picks its display backend itself (native Wayland);
  XWayland is only forced inside a distrobox container, where the native
  backend left the window unmapped.

## v1.8.1

- **Bazzite / immutable systems**: the "needs PyQt6" message used to
  suggest `apt` and `dnf`, which cannot install anything on these hosts.
  It now explains the distrobox steps. `install.sh` run on such a host
  without PyQt6 stops with the same steps instead of creating a menu entry
  that cannot start. The README has the steps written out.

## v1.8.0

- **New logo**: headphones with a glowing orb of sound between the ear
  cups and a ring orbiting it. Shown beside the name in the app, as the
  window and task-bar icon, in the application menu (run `install.sh`
  again to update the menu entry) and on the project page.
- **License**: Spatial Linux is now formally free software under the GNU
  General Public License v3.0 or later (`LICENSE`).

## v1.7.1

- README: per-app volume control is now described up front, in the
  highlights and in the usage steps. No changes to the app.

## v1.7.0

- **Subwoofer, Reverb and Clarity can be switched off** in the 3D panel,
  each with its own On / Off button. Off bypasses that effect completely;
  the slider keeps its value (dimmed) and switching back on returns to it.
  The on / off choice is remembered and saved in presets.

## v1.6.0

Everything from the three betas, now stable:

- **App volumes**: a panel with a volume slider and mute button for every
  app playing sound, from the new mixer button in the header.
- **Clarity in 3D Surround**, with its own value, separate from Fidelity.
- **No more stutter while dragging sliders**: changes are sent together,
  one command per drag instead of over a hundred.
- **Much less CPU in the background**: animations pause while Spatial Linux
  is not the active window.
- Your saved volume is kept when switching on; switching off gives an
  automatic default output back exactly as it was; the app opens even when
  a tool is missing and says what to install.
- **New 3D defaults** (first launch and the Defaults button): intensity 65%,
  Subwoofer +3 dB, Reverb 25%, Treble −1 dB, Clarity +5 dB. Your own saved
  settings are not changed.

## v1.6.0-beta.3

- **App volumes.** A new button in the header (three little faders, next
  to the globe) opens a panel listing every app that is playing sound, each
  with its own volume slider and mute button. Keep a game's voice chat
  quiet and your browser loud without leaving Spatial Linux. The list
  updates by itself while the panel is open, works whether Spatial Linux is
  switched on or not, and reading it never freezes the window.

## v1.6.0-beta.2

- **Clarity in 3D Surround.** The 3D panel has a Clarity slider, the same
  lift of the deepest lows and finest highs as the Fidelity mode, with its
  own remembered value. It starts at 0 dB, so the 3D sound does not change
  until you raise it; the Fidelity mode keeps its own setting.

## v1.6.0-beta.1

A test release. It fixes problems found by going through the whole app.

- **No more stutter while dragging sliders.** Every slider step used to
  start its own background command: one drag of a slider ran over a
  hundred of them, the volume slider a hundred, one EQ point fifty, each
  briefly freezing the window. Changes are now gathered and sent together,
  at most every 30 ms: one command per drag, and switching modes or
  loading a preset takes four instead of nine to fourteen.
- **Much less CPU in the background.** An open mode panel's animation
  used about 15% of a CPU core all the time, even behind a game. All
  animations now pause while Spatial Linux is not the active window or is
  minimised, and continue when you come back.
- **Your volume is kept.** Switching on used to replace the saved volume
  with the virtual device's own level.
- **Truly leaves no trace.** On systems where the output device had never
  been picked by hand, switching off saved the previous device as a manual
  choice in the system settings. Now the automatic choice is simply given
  back.
- **Opens even if a tool is missing.** If one of the PipeWire command-line
  tools (or `pgrep`) was missing, the app did not open at all, without any
  message. It now opens, and the power button explains what to install.
- **Clearer start-up problems.** Started from the menu without PyQt6, the
  app failed silently; it now shows a notification saying what to
  install. It also no longer forces XWayland when there is none.

## v1.5.6

- The maintainer's release notes moved out of the README into
  `docs/RELEASING.md`. No changes to the app.

## v1.5.5

- README: says plainly that Spatial Linux is a Boom 3D alternative for
  Linux, so people searching for that can find it, with a note that it is
  not affiliated with Boom 3D. No changes to the app.

## v1.5.4

- Support link: a Ko-fi button in the README and a Sponsor button on
  GitHub. No changes to the app.

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
