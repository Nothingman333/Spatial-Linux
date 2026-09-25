#!/bin/sh
# Start Spatial Linux inside its Flatpak. PyQt6 comes from the base app.
export PYTHONPATH=/app/share/spatiallinux
exec python3 -m spatiallinux.app "$@"
