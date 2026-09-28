"""Build the fonts that ship with the app.

    python3 tools/build_fonts.py

Inter (The Inter Project Authors, SIL Open Font License 1.1) is a variable
font. Not every Qt on the systems Spatial Linux runs on can pick a weight
out of one (setVariableAxis is Qt 6.7+; Ubuntu 24.04 has 6.4), so fixed
weights are cut out of it here with fontTools, and trimmed to the
characters the interface uses (Latin, Turkish, punctuation, arrows), which
takes them from 900 KB to a few tens of KB each.

Needs fontTools; downloads Google Fonts' copy of Inter into tools/cache/.
"""

import os
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
OUT = os.path.join(HERE, "..", "spatiallinux", "data", "fonts")
BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/"
SOURCES = {"roman": "Inter[opsz,wght].ttf",
           "italic": "Inter-Italic[opsz,wght].ttf"}

# family, style, source, weight, optical size (14 = text, 32 = display)
CUTS = [
    ("Inter", "Regular", "roman", 400, 14),
    ("Inter", "Medium", "roman", 500, 14),
    ("Inter", "SemiBold", "roman", 600, 14),
    ("Inter", "Bold", "roman", 700, 14),
    ("Inter Display", "Regular", "roman", 400, 32),
    ("Inter Display", "SemiBold", "roman", 600, 32),
    ("Inter Display", "Bold Italic", "italic", 700, 32),
]

UNICODES = (list(range(0x20, 0x7F)) + list(range(0xA0, 0x180))
            + list(range(0x2010, 0x2070)) + list(range(0x2190, 0x2200))
            + [0x20AC, 0x2212, 0x2022, 0x00B7, 0x2026, 0x25CF, 0x25CB])


def rename(font: TTFont, family: str, style: str, weight: int):
    """One family per name, the weight in OS/2 -- what fontconfig and Qt
    match on -- so "Inter" at weight 600 finds the SemiBold cut."""
    italic = "Italic" in style
    full = f"{family} {style}".replace(" Regular", "")
    ps = f"{family}-{style}".replace(" ", "")
    names = {1: family, 2: "Italic" if italic and weight < 600 else
             ("Bold Italic" if italic else "Regular"),
             4: full, 6: ps, 16: family, 17: style}
    table = font["name"]
    for rec in list(table.names):
        if rec.nameID in (1, 2, 4, 6, 16, 17, 21, 22, 25):
            table.removeNames(nameID=rec.nameID)
    for nid, text in names.items():
        table.setName(text, nid, 3, 1, 0x409)
        table.setName(text, nid, 1, 0, 0)
    font["OS/2"].usWeightClass = weight
    fs = font["OS/2"].fsSelection & ~0b1100001
    font["OS/2"].fsSelection = fs | (0b1 if italic else 0) | (0b100000 if weight >= 700 else 0) \
        | (0b1000000 if (weight == 400 and not italic) else 0)
    mac = font["head"].macStyle & ~0b11
    font["head"].macStyle = mac | (0b10 if italic else 0) | (0b1 if weight >= 700 else 0)


def main():
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    for name in SOURCES.values():
        path = os.path.join(CACHE, name)
        if not os.path.exists(path):
            url = BASE + name.replace("[", "%5B").replace("]", "%5D")
            urllib.request.urlretrieve(url, path)
    for family, style, source, weight, opsz in CUTS:
        font = TTFont(os.path.join(CACHE, SOURCES[source]))
        font = instancer.instantiateVariableFont(
            font, {"wght": weight, "opsz": opsz})
        rename(font, family, style, weight)
        options = subset.Options()
        options.layout_features = ["kern", "liga", "calt", "ccmp", "locl",
                                   "mark", "mkmk", "tnum", "case", "ss01"]
        options.name_IDs = ["*"]
        options.notdef_outline = True
        sub = subset.Subsetter(options)
        sub.populate(unicodes=UNICODES)
        sub.subset(font)
        out = os.path.join(OUT, f"{family}-{style}.ttf".replace(" ", ""))
        font.save(out)
        print(f"{out}: {os.path.getsize(out) // 1024} KB")


if __name__ == "__main__":
    main()
