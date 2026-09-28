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

for f in sorted(os.listdir(DATA)):
    if f.endswith(".wav"):
        print("wrote", os.path.join(DATA, f))
