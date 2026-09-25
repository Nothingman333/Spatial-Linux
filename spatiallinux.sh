#!/usr/bin/env bash
cd "$(dirname "$(readlink -f "$0")")"

# KDE Plasma's native Wayland QPA leaves the window unmapped in a distrobox
# setup, so XWayland is used when it is there. Without it (DISPLAY unset)
# forcing xcb would stop the window from opening at all, so Qt picks.
if [ -z "${QT_QPA_PLATFORM:-}" ] && [ -n "${DISPLAY:-}" ]; then
    export QT_QPA_PLATFORM=xcb
fi

# Started from the application menu there is no terminal to show Python's
# error, so a missing PyQt6 used to fail silently. Say so instead.
if ! python3 -c "import PyQt6.QtWidgets" 2>/dev/null; then
    msg="Spatial Linux needs PyQt6. Install it with your package manager, e.g. 'sudo apt install python3-pyqt6' or 'sudo dnf install python3-pyqt6'."
    echo "$msg" >&2
    command -v notify-send >/dev/null && notify-send "Spatial Linux" "$msg"
    exit 1
fi

exec python3 -m spatiallinux.app
