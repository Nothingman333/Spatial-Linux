import json
import os
import shutil
from dataclasses import asdict, fields

from .engine import EngineState

PRESET_DIR = os.path.expanduser("~/.local/share/spatiallinux/presets")
BUILTIN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "presets")
SESSION_FILE = os.path.expanduser("~/.local/share/spatiallinux/session.json")
# Things about the app rather than the sound: whether the intro has been
# shown, whether the engine was on, the volume, the preset last picked.
SETTINGS_FILE = os.path.expanduser("~/.local/share/spatiallinux/settings.json")


OLD_DATA_DIR = os.path.expanduser("~/.local/share/boomlinux")
DATA_DIR = os.path.dirname(SESSION_FILE)


def migrate_old_data():
    """The app used to be called BoomLinux and kept its data under that
    name. Carry the session, settings and saved presets over once, so the
    rename does not throw away anyone's settings. The old folder is left in
    place; nothing is deleted."""
    if os.path.exists(DATA_DIR) or not os.path.isdir(OLD_DATA_DIR):
        return
    os.makedirs(PRESET_DIR, exist_ok=True)
    for name in ("session.json", "settings.json"):
        src = os.path.join(OLD_DATA_DIR, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(DATA_DIR, name))
    old_presets = os.path.join(OLD_DATA_DIR, "presets")
    if os.path.isdir(old_presets):
        for f in os.listdir(old_presets):
            if f.endswith(".json"):
                shutil.copy2(os.path.join(old_presets, f), PRESET_DIR)


def _ensure_dir():
    os.makedirs(PRESET_DIR, exist_ok=True)


# Built-in presets once had Turkish file names. Unpacking a new release over
# an old one leaves those files next to their renamed copies, and the list
# then showed "bas" beside "Bass" even in English -- so in the built-in
# folder these old names are ignored. (A preset the user saved under one of
# these names lives in PRESET_DIR and is still listed.)
LEGACY_BUILTINS = {"bas": "bass", "gece": "night", "oyun": "gaming"}


def list_presets() -> list[str]:
    _ensure_dir()
    names = set()
    if os.path.isdir(BUILTIN_DIR):
        names.update(f[:-5] for f in os.listdir(BUILTIN_DIR)
                     if f.endswith(".json") and f[:-5] not in LEGACY_BUILTINS)
    if os.path.isdir(PRESET_DIR):
        names.update(f[:-5] for f in os.listdir(PRESET_DIR) if f.endswith(".json"))
    return sorted(names)


def save_preset(name: str, state: EngineState):
    _ensure_dir()
    with open(os.path.join(PRESET_DIR, f"{name}.json"), "w") as f:
        json.dump(asdict(state), f, indent=2)


def _from_dict(data: dict) -> EngineState:
    """Unknown keys are ignored and missing ones keep their defaults, so a
    file written by an older version of the app still loads."""
    known = {f.name for f in fields(EngineState)}
    return EngineState(**{k: v for k, v in data.items() if k in known})


def _write_json(path: str, data: dict):
    """Write via a temporary file and rename it into place: the session is
    now saved while the app runs, and being killed mid-write must never
    leave a half-written file that would lose every setting."""
    _ensure_dir()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass


def save_session(state: EngineState):
    """Remember the current settings so they come back next launch."""
    _write_json(SESSION_FILE, asdict(state))


def load_settings() -> dict:
    try:
        with open(SETTINGS_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(settings: dict):
    _write_json(SETTINGS_FILE, settings)


def load_session() -> EngineState | None:
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE) as f:
            return _from_dict(json.load(f))
    except (OSError, ValueError, TypeError):
        return None


def clear_session():
    try:
        os.remove(SESSION_FILE)
    except OSError:
        pass


def load_preset(name: str) -> EngineState:
    """User presets shadow built-ins of the same name."""
    for d in (PRESET_DIR, BUILTIN_DIR):
        path = os.path.join(d, f"{name}.json")
        if os.path.exists(path):
            with open(path) as f:
                return _from_dict(json.load(f))
    raise FileNotFoundError(name)
