#!/usr/bin/env bash
cd "$(dirname "$(readlink -f "$0")")"
# KDE Plasma's native Wayland QPA leaves the window unmapped in this
# distrobox setup; forcing XWayland makes it actually appear on screen.
export QT_QPA_PLATFORM=xcb
exec python3 -m spatiallinux.app
