#!/usr/bin/env bash
# Install Spatial Linux into the desktop's application menu.
#
# Works both natively and from inside a distrobox container: when run in a
# container it exports the launcher to the host, since that is where the
# application menu lives.
set -euo pipefail

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
DESKTOP_FILE="$HERE/spatiallinux.desktop"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Spatial Linux
Comment=3D sound enhancement for PipeWire
Exec=$HERE/spatiallinux.sh
Icon=audio-volume-high
Terminal=false
Categories=AudioVideo;Audio;
StartupNotify=true
EOF

chmod +x "$HERE/spatiallinux.sh" "$DESKTOP_FILE"

if [ -n "${DISTROBOX_ENTER_PATH:-}" ] && command -v distrobox-export >/dev/null; then
    distrobox-export --app "$DESKTOP_FILE" --export-label none
    echo "Exported to the host application menu."
else
    install -Dm644 "$DESKTOP_FILE" \
        "${XDG_DATA_HOME:-$HOME/.local/share}/applications/spatiallinux.desktop"
    echo "Installed to ${XDG_DATA_HOME:-$HOME/.local/share}/applications."
fi

# The app used to be called BoomLinux; drop that launcher so the menu does
# not show both names.
rm -f "${XDG_DATA_HOME:-$HOME/.local/share}/applications/boomlinux.desktop" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/applications/ubuntu-boomlinux.desktop" \
      2>/dev/null || true

echo "Done. Look for \"Spatial Linux\" in your application menu."
