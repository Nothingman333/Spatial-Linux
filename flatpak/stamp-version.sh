#!/bin/sh
# Write the app's version and today's date into the store metadata's
# <release> entry. Plain sh and sed: the build container has no Python.
set -e
cd "$(dirname "$0")/.."
ver=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' spatiallinux/__init__.py)
[ -n "$ver" ] || { echo "no version found" >&2; exit 1; }
sed -i "s|<release version=\"[^\"]*\" date=\"[^\"]*\"/>|<release version=\"$ver\" date=\"$(date +%F)\"/>|" \
    flatpak/io.github.nothingman333.SpatialLinux.metainfo.xml
grep '<release ' flatpak/io.github.nothingman333.SpatialLinux.metainfo.xml
