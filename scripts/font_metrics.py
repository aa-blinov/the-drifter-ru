#!/usr/bin/env python
"""The metrics of a font, measured rather than assumed.

The game draws its text with fonts that live in its own assets, and each of
them has its own proportions: how high a capital letter stands, where the
baseline sits, how deep a descender goes, and how big one pixel of its grid
is. The Cyrillic glyphs have to match those proportions, or the Russian text
looks like a different font dropped into the middle of an English line.

Everything here is measured on the font itself: the pixel grid is the
greatest common divisor of the coordinates of its letters, and the heights
come from the letters themselves.
"""
from __future__ import annotations

import io
import os
from math import gcd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "work", "fonts")

# The source of the Cyrillic glyphs: a pixel font that carries the whole
# Cyrillic range. The file is picked by the design size of the target font.
CYRILLIC_SOURCES = {
    10: "ark-pixel-10px-proportional-latin.ttf",
    12: "ark-pixel-12px-proportional-latin.ttf",
    16: "ark-pixel-16px-proportional-latin.ttf",
}


def _coordinates(font, name):
    """The outline points of one glyph."""
    glyf = font["glyf"]
    glyph = glyf[name]
    try:
        coordinates, _end, _flags = glyph.getCoordinates(glyf)
    except Exception:
        return []
    return coordinates


def pixel_grid(font) -> int:
    """The size of one pixel of the font, in font units.

    A pixel font has no coordinate off its own grid, so the greatest common
    divisor of the coordinates of its glyphs is the size of one pixel.
    """
    grid = 0
    for name in font.getGlyphOrder():
        for x, y in _coordinates(font, name):
            grid = gcd(grid, abs(int(x)))
            grid = gcd(grid, abs(int(y)))
    return grid


def height_of(font, char) -> int:
    """The height of one letter, in font units."""
    codepoint = ord(char)
    cmap = font.getBestCmap()
    if codepoint not in cmap:
        return 0
    points = _coordinates(font, cmap[codepoint])
    if not points:
        return 0
    ys = [p[1] for p in points]
    return max(ys) - min(ys)


def baseline_of(font, char="H"):
    """The y of the baseline, in font units."""
    codepoint = ord(char)
    cmap = font.getBestCmap()
    if codepoint not in cmap:
        return 0
    points = _coordinates(font, cmap[codepoint])
    if not points:
        return 0
    return min(p[1] for p in points)


class Metrics:
    """What one font looks like, in its own units."""

    def __init__(self, font):
        self.upem = font["head"].unitsPerEm
        self.grid = pixel_grid(font) or 1
        self.cap = height_of(font, "H")
        self.x_height = height_of(font, "x")
        self.ascent = height_of(font, "h")
        self.descent = max(0, height_of(font, "p") - height_of(font, "x"))

    @property
    def pixels(self) -> float:
        """How many pixels of its own grid the em covers."""
        return self.upem / self.grid

    def describe(self, label=""):
        return ("%s upem %d, %.1f px em, cap %d, x-height %d"
                % (label, self.upem, self.pixels, self.cap, self.x_height))


def load_font(data):
    """A font from its bytes, or from the path to it."""
    from fontTools.ttLib import TTFont
    if isinstance(data, (bytes, bytearray)):
        return TTFont(io.BytesIO(data))
    return TTFont(data)
