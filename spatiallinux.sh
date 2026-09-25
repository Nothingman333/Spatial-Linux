#!/usr/bin/env bash
# Start Spatial Linux.
#
# The one thing it needs besides PipeWire is PyQt6. If the system Python
# has it, that is used. If not -- as on Bazzite and other immutable systems,
# where apt and dnf cannot install anything on the host -- PyQt6 is fetched
# once from PyPI into a private folder of the app's own, with no root, no
# sudo and no container, and used from there from then on.
#
#   ./spatiallinux.sh           start the app (setting up first if needed)
#   ./spatiallinux.sh --setup   only set up, showing progress (install.sh)
set -u
cd "$(dirname "$(readlink -f "$0")")"

ENV_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/spatiallinux/pyenv"
PYQT_SPEC="PyQt6>=6.5,<7"

notify() {
    echo "$1" >&2
    command -v notify-send >/dev/null && notify-send -a "Spatial Linux" \
        -i "$PWD/spatiallinux/data/spatiallinux.svg" "Spatial Linux" "$1"
}

has_pyqt() { "$1" -c "import PyQt6.QtWidgets, PyQt6.QtSvg" 2>/dev/null; }

# The Python to run with: the system's if it has PyQt6, else the private one.
pick_python() {
    if has_pyqt python3; then
        PY=python3
    elif [ -x "$ENV_DIR/bin/python" ] && has_pyqt "$ENV_DIR/bin/python"; then
        PY="$ENV_DIR/bin/python"
    else
        return 1
    fi
}

setup_private_env() {
    notify "Getting Spatial Linux ready. This happens only once and downloads about 90 MB, so it can take a minute."
    rm -rf "$ENV_DIR"
    mkdir -p "$(dirname "$ENV_DIR")"
    if ! python3 -m venv "$ENV_DIR"; then
        notify "Could not create a Python environment (python3 -m venv failed). Install PyQt6 with your package manager instead, e.g. 'sudo apt install python3-pyqt6' or 'sudo dnf install python3-pyqt6'."
        return 1
    fi
    if ! "$ENV_DIR/bin/python" -m pip install --disable-pip-version-check \
            --progress-bar on "$PYQT_SPEC"; then
        rm -rf "$ENV_DIR"
        notify "Could not download PyQt6. Check your internet connection and start Spatial Linux again."
        return 1
    fi
    notify "Spatial Linux is ready."
}

if ! command -v python3 >/dev/null; then
    notify "Spatial Linux needs Python 3, which was not found on this system."
    exit 1
fi

if ! pick_python; then
    setup_private_env && pick_python || exit 1
fi

[ "${1:-}" = "--setup" ] && { echo "Using $PY"; exit 0; }

# Inside a distrobox container KDE's native Wayland backend left the window
# unmapped, so XWayland is used there. On the host, Qt picks by itself.
if [ -z "${QT_QPA_PLATFORM:-}" ] && [ -e /run/.containerenv ] \
   && [ -n "${DISPLAY:-}" ]; then
    export QT_QPA_PLATFORM=xcb
fi

exec "$PY" -m spatiallinux.app "$@"
