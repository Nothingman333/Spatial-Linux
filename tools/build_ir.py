"""Build the head-model files that ship with the app.

    python3 tools/build_ir.py

Needs NumPy and h5py, the libmysofa data files (the MIT KEMAR measurement)
and the SADIE II subject D1 set as OpenAL Soft ships it (downloaded here if
it is not already in tools/cache/). Only the machine that builds needs any
of that: the results are written to spatiallinux/data/ and committed, so
users get the measured heads without installing anything.

For each head it writes the 3D Surround cue file (binaural_ir*.wav) and the
file that places the discrete surround channels of 5.1 / 7.1 sources
(surround_ir_*.wav). Unlike the app's own fallback, this refuses to fall
back to the analytic head model: a bundled file must always be measured.
"""

import os
import shutil
import sys
import tempfile
import urllib.request
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from spatiallinux import ir, engine  # noqa: E402
import room  # noqa: E402  (tools/room.py)

SADIE_URL = ("https://raw.githubusercontent.com/kcat/openal-soft/master/"
             "hrtf/Default%20HRTF.mhr")
SADIE_FILE = os.path.join(HERE, "cache", "sadie_ii_d1.mhr")
DATA = os.path.dirname(engine.BUNDLED_BINAURAL_IR)


def front_energy(path):
    """Energy of the two cross-feed channels of a cue file."""
    import numpy as np
    with wave.open(path) as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        ch = raw.reshape(-1, w.getnchannels()).astype(float) / 32000.0
    return float((ch[:, :2] ** 2).sum())


sofa = ir._find_sofa()
if not sofa:
    sys.exit("No SOFA file found (install libmysofa's data files).")
if not os.path.exists(SADIE_FILE):
    os.makedirs(os.path.dirname(SADIE_FILE), exist_ok=True)
    urllib.request.urlretrieve(SADIE_URL, SADIE_FILE)

heads = {"kemar": sofa, "sadie": SADIE_FILE}
os.makedirs(DATA, exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    # the default head, exactly as before
    ir._measured_channels(ir._load_measured_hrirs(sofa))   # raises if unusable
    kemar = ir.generate_binaural_ir(os.path.join(tmp, "binaural_ir.wav"))
    shutil.copyfile(kemar, engine.BUNDLED_BINAURAL_IR)
    reference = front_energy(kemar)

    # the other head, its cross-feed matched to the default's level
    out = ir.generate_binaural_ir(
        os.path.join(tmp, "binaural_ir_sadie.wav"),
        hrirs=ir._load_measured_hrirs(SADIE_FILE),
        front_energy=reference)
    shutil.copyfile(out, os.path.join(DATA, "binaural_ir_sadie.wav"))

    for name, source in heads.items():
        out = ir.generate_surround_ir(
            os.path.join(tmp, f"surround_ir_{name}.wav"),
            ir._load_measured_hrirs(source, ir.SURROUND_SPEAKERS))
        shutil.copyfile(out, os.path.join(DATA, f"surround_ir_{name}.wav"))

# -- virtual speakers in a room ---------------------------------------------
import numpy as np  # noqa: E402

heads_full = {"kemar": room.Head(*ir.load_sofa(sofa)),
              "sadie": room.Head(*ir.load_mhr(SADIE_FILE))}
for room_name, spec in room.ROOMS.items():
    scales = []
    for head_name, head in heads_full.items():
        pairs = room.equalise(room.speaker_pairs(head, room_name), room_name,
                              room.late_tail(room_name))
        d, e = pairs["FL"]
        # the front left speaker, at the default settings, carries the
        # energy of the dry left channel it replaces: direct + early + tail
        late = 10 ** (spec["late_db"] / 10) * (d ** 2).sum()
        k = 1.0 / np.sqrt((d ** 2).sum() + (e ** 2).sum() + late)
        scales.append(k * np.sqrt((d ** 2).sum()))
        room.write_wav(os.path.join(DATA, f"room_{head_name}_{room_name}.wav"),
                       room.room_channels(pairs, k))
    # The tail is fed half the sum of the two downmixed channels, so one
    # channel alone reaches it at half level: that is made up for here.
    # Shared by both heads, at their average direct level.
    g = float(np.mean(scales)) * np.sqrt(2 * 10 ** (spec["late_db"] / 10))
    room.write_wav(os.path.join(DATA, f"room_late_{room_name}.wav"),
                   room.late_tail(room_name) * g)

for f in sorted(os.listdir(DATA)):
    if f.endswith(".wav"):
        print("wrote", os.path.join(DATA, f))
