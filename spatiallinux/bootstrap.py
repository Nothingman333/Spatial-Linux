"""Fetch PyQt6 into Spatial Linux's private Python environment, reporting
progress as it goes.

Runs with the system Python, before PyQt6 exists, so it uses the standard
library only. pip on its own cannot report download progress in a form
another program can read (its machine-readable progress needs pip 24.1+,
newer than many systems ship), so the work is split:

  1. pip resolves what is needed without downloading it (--dry-run --report)
  2. the files are downloaded here, with byte-by-byte progress
  3. pip installs them from the downloaded files, offline

Output, one line per update, is either for zenity --progress ("# label"
lines and bare percentages) or a plain text bar for a terminal.

    python3 -m spatiallinux.bootstrap ENV_DIR [--ui zenity|terminal]
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import venv

REQUIREMENT = "PyQt6>=6.5,<7"
CHUNK = 256 * 1024


class Report:
    def __init__(self, ui: str):
        self.ui = ui
        self._last = None

    def label(self, text: str):
        if self.ui == "zenity":
            print(f"# {text}", flush=True)
        else:
            print(f"\n{text}", flush=True)

    def percent(self, pct: float, detail: str = ""):
        pct = max(0, min(100, int(pct)))
        if self.ui == "zenity":
            if pct != self._last:
                print(pct, flush=True)
        else:
            bar = "#" * (pct // 4) + "-" * (25 - pct // 4)
            sys.stdout.write(f"\r  [{bar}] {pct:3d}%  {detail}   ")
            sys.stdout.flush()
        self._last = pct


def _pip(env_dir: str, *args, capture=False):
    py = os.path.join(env_dir, "bin", "python")
    return subprocess.run([py, "-m", "pip", "--disable-pip-version-check", *args],
                          capture_output=capture, text=True)


def _resolve(env_dir: str) -> list[dict]:
    """[{name, url}] of every file the requirement needs, without fetching."""
    out = _pip(env_dir, "install", "--dry-run", "--ignore-installed",
               "--quiet", "--report", "-", REQUIREMENT, capture=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "pip could not resolve PyQt6")
    report = json.loads(out.stdout)
    files = []
    for item in report.get("install", []):
        url = (item.get("download_info") or {}).get("url")
        name = (item.get("metadata") or {}).get("name", "")
        if url:
            files.append({"name": name, "url": url})
    return files


def _size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("Content-Length") or 0)


def main(argv: list[str]) -> int:
    env_dir = argv[0]
    ui = argv[argv.index("--ui") + 1] if "--ui" in argv else "terminal"
    rep = Report(ui)

    rep.label("Preparing…")
    rep.percent(1)
    if os.path.exists(env_dir):
        shutil.rmtree(env_dir)
    venv.create(env_dir, with_pip=True)
    rep.percent(3)

    try:
        files = _resolve(env_dir)
        sizes = [_size(f["url"]) for f in files]
    except Exception as e:                      # old pip, or no network yet
        # Fall back to a plain install: no byte progress, but it still works
        # on a pip too old for --report.
        rep.label("Downloading PyQt6…")
        rep.percent(10)
        ok = _pip(env_dir, "install", "--quiet", REQUIREMENT).returncode == 0
        if not ok:
            print(f"\nerror: {e}", file=sys.stderr)
            return 1
        rep.percent(100)
        return 0

    total = sum(sizes) or 1
    done = 0
    with tempfile.TemporaryDirectory() as tmp:
        for f, size in zip(files, sizes):
            amount = (f"{size / 1e6:.0f} MB" if size >= 1e6
                      else f"{max(1, size // 1000)} KB")
            rep.label(f"Downloading {f['name']} ({amount})…")
            dest = os.path.join(tmp, os.path.basename(f["url"].split("#")[0]))
            with urllib.request.urlopen(f["url"], timeout=60) as r, \
                    open(dest, "wb") as out:
                while True:
                    chunk = r.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    # downloading is 3..90%, installing the rest
                    rep.percent(3 + 87 * done / total,
                                f"{done / 1e6:.0f} of {total / 1e6:.0f} MB")
        rep.label("Installing…")
        rep.percent(92)
        res = _pip(env_dir, "install", "--quiet", "--no-index",
                   "--find-links", tmp, REQUIREMENT)
        if res.returncode != 0:
            return 1
    rep.label("Done")
    rep.percent(100)
    if ui != "zenity":
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
