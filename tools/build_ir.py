"""Build the 3D Surround cue file that ships with the app.

    python3 tools/build_ir.py

Needs NumPy, h5py and the libmysofa data files (the MIT KEMAR measurement)
-- only here, on the machine that builds it. The result is written to
spatiallinux/data/binaural_ir.wav and committed, so users get the measured
head model without installing any of that.

Unlike the app's own fallback, this refuses to fall back to the analytic
head model: a bundled file must always be the measured one.
"""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spatiallinux import ir, engine  # noqa: E402

sofa = ir._find_sofa()
if not sofa:
    sys.exit("No SOFA file found (install libmysofa's data files).")
ir._measured_channels(ir._load_measured_hrirs(sofa))   # raises if unusable

with tempfile.TemporaryDirectory() as tmp:
    out = ir.generate_binaural_ir(os.path.join(tmp, "binaural_ir.wav"))
    os.makedirs(os.path.dirname(engine.BUNDLED_BINAURAL_IR), exist_ok=True)
    shutil.copyfile(out, engine.BUNDLED_BINAURAL_IR)
print("wrote", engine.BUNDLED_BINAURAL_IR, "from", sofa)
