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

run_bootstrap() { python3 -m spatiallinux.bootstrap "$ENV_DIR" "$@"; }

# A progress window for the one-time download when there is no terminal to
# show it in (started from the application menu): zenity where it exists,
# KDE's kdialog otherwise, and at least a notification if neither does.
progress_zenity() {
    run_bootstrap --ui zenity | zenity --progress --title="Spatial Linux" \
        --text="Getting Spatial Linux ready…" --percentage=0 \
        --auto-close --no-cancel --width=440 2>/dev/null
    return "${PIPESTATUS[0]}"
}

progress_kdialog() {
    local ref svc obj status
    ref="$(kdialog --title "Spatial Linux" \
           --progressbar "Getting Spatial Linux ready…" 100 2>/dev/null)" || return 2
    svc="${ref%% *}"; obj="${ref#* }"
    run_bootstrap --ui zenity | while IFS= read -r line; do
        case "$line" in
            "#"*) busctl --user call "$svc" "$obj" org.kde.kdialog.ProgressDialog \
                      setLabelText s "${line#\# }" >/dev/null 2>&1 ;;
            *)    busctl --user set-property "$svc" "$obj" \
                      org.kde.kdialog.ProgressDialog value i "$line" >/dev/null 2>&1 ;;
        esac
    done
    status="${PIPESTATUS[0]}"
    busctl --user call "$svc" "$obj" org.kde.kdialog.ProgressDialog close \
        >/dev/null 2>&1
    return "$status"
}

setup_private_env() {
    mkdir -p "$(dirname "$ENV_DIR")"
    local status
    if [ -t 1 ]; then                                  # a terminal: text bar
        echo "Getting Spatial Linux ready (one-time download of PyQt6, about 95 MB)."
        run_bootstrap --ui terminal
        status=$?
    elif command -v zenity >/dev/null; then
        progress_zenity; status=$?
    elif command -v kdialog >/dev/null && command -v busctl >/dev/null; then
        progress_kdialog; status=$?
        if [ "$status" = 2 ]; then                     # kdialog would not open
            notify "Getting Spatial Linux ready. This happens only once and downloads about 95 MB."
            run_bootstrap --ui terminal >/dev/null; status=$?
        fi
    else
        notify "Getting Spatial Linux ready. This happens only once and downloads about 95 MB, so it can take a minute."
        run_bootstrap --ui terminal >/dev/null; status=$?
    fi
    if [ "$status" != 0 ]; then
        rm -rf "$ENV_DIR"
        notify "Could not download PyQt6. Check your internet connection and start Spatial Linux again. (Or install it with your package manager, e.g. 'sudo apt install python3-pyqt6' or 'sudo dnf install python3-pyqt6'.)"
        return 1
    fi
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
