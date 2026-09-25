#!/usr/bin/env bash
cd "$(dirname "$(readlink -f "$0")")"

# KDE Plasma's native Wayland QPA leaves the window unmapped in a distrobox
# setup, so XWayland is used when it is there. Without it (DISPLAY unset)
# forcing xcb would stop the window from opening at all, so Qt picks.
if [ -z "${QT_QPA_PLATFORM:-}" ] && [ -n "${DISPLAY:-}" ]; then
    export QT_QPA_PLATFORM=xcb
fi

# Started from the application menu there is no terminal to show Python's
# error, so a missing PyQt6 used to fail silently. Say so instead -- and on
# an immutable system (Bazzite, Silverblue, ...), where apt and dnf do not
# install anything on the host, point to the container instead.
if ! python3 -c "import PyQt6.QtWidgets" 2>/dev/null; then
    if [ -e /run/ostree-booted ] && [ ! -e /run/.containerenv ]; then
        msg="Spatial Linux needs PyQt6, which is not on this system. On Bazzite and other immutable systems it runs inside a distrobox container. Open a terminal and run: distrobox enter ubuntu, then sudo apt install python3-pyqt6, then ./install.sh from the Spatial Linux folder. Start it from the menu afterwards."
    else
        msg="Spatial Linux needs PyQt6. Install it with your package manager, e.g. 'sudo apt install python3-pyqt6' or 'sudo dnf install python3-pyqt6'."
    fi
    echo "$msg" >&2
    command -v notify-send >/dev/null && notify-send "Spatial Linux" "$msg"
    exit 1
fi

exec python3 -m spatiallinux.app
