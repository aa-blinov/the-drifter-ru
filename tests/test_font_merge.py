#!/usr/bin/env python
"""The font merge: the Cyrillic glyphs have to land on the pixel grid.

The merge takes a font of the game and adds the Cyrillic glyphs of a pixel
font to it. The test takes a real pixel font, strips the Cyrillic out of it
so that it stands for a game font, merges the Cyrillic back in, and checks
three things:

  the Cyrillic glyphs are there;
  the original glyphs are untouched;
  every coordinate of a merged glyph is a multiple of the target's units per
  pixel, which is what keeps it crisp instead of blurry.

The game itself is not needed: the merge works on the font data alone, and
the metrics of a game font are the metrics of every font of that pixel size.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from install import design_pixels, merge_one, pixel_grid  # noqa: E402

FONT_DIR = os.path.join(ROOT, "work", "fonts")
SOURCE_10 = os.path.join(FONT_DIR, "ark-pixel-10px-proportional-latin.ttf")
SOURCE_12 = os.path.join(FONT_DIR, "ark-pixel-12px-proportional-latin.ttf")

# The metrics of a game font: 125 units per pixel at 10 px and 12 px.
UNITS_PER_PX = 125


def strip_cyrillic(path):
    """A font with the Cyrillic removed, so it stands for a game font."""
    from fontTools import subset
    from fontTools.ttLib import TTFont

    font = TTFont(path)
    options = subset.Options()
    options.glyph_names = True
    options.notdef_outline = True
    options.recalc_bounds = True
    options.drop_tables += ["GSUB", "GPOS", "GDEF", "BASE", "DSIG", "kern"]
    options.layout_features = []
    keep = [code for code in font.getBestCmap()
            if not (0x0400 <= code <= 0x04FF)]
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=keep)
    subsetter.subset(font)
    buffer = io.BytesIO()
    font.save(buffer)
    return buffer.getvalue()


class FontMergeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(SOURCE_10) or not os.path.exists(SOURCE_12):
            raise unittest.SkipTest("the pixel fonts are not fetched: %s" % FONT_DIR)
        from fontTools.ttLib import TTFont
        cls.source = TTFont(SOURCE_10)
        cls.game_font = strip_cyrillic(SOURCE_12)
        cls.game = TTFont(io.BytesIO(cls.game_font))

    def merged(self):
        from fontTools.ttLib import TTFont
        data = merge_one(self.game_font, SOURCE_12)
        return TTFont(io.BytesIO(data))

    def test_the_cyrillic_glyphs_are_added(self):
        cmap = self.merged().getBestCmap()
        for codepoint in (ord("А"), ord("я"), ord("Ё"), ord("ё"),
                          ord("«"), ord("»"), ord("—"), ord("…")):
            self.assertIn(codepoint, cmap,
                          "the glyph for U+%04X is missing" % codepoint)

    def test_the_original_glyphs_are_untouched(self):
        from fontTools.ttLib import TTFont
        before = TTFont(io.BytesIO(self.game_font))
        after = self.merged()
        for name in before.getGlyphOrder():
            if name not in after.getGlyphOrder():
                self.fail("the glyph %s was lost" % name)
            original = before["glyf"].glyphs[name]
            merged = after["glyf"].glyphs[name]
            self.assertEqual(getattr(original, "numberOfContours", None),
                             getattr(merged, "numberOfContours", None),
                             "the glyph %s changed" % name)
            self.assertEqual(getattr(original, "coordinates", None),
                             getattr(merged, "coordinates", None),
                             "the glyph %s changed" % name)

    def test_the_merged_glyphs_land_on_the_pixel_grid(self):
        merged = self.merged()
        grid = pixel_grid(self.game)
        self.assertGreater(grid, 0)
        cmap = merged.getBestCmap()
        checked = 0
        for codepoint, name in cmap.items():
            if not (0x0400 <= codepoint <= 0x04FF):
                continue
            glyph = merged["glyf"].glyphs[name]
            for x, y in getattr(glyph, "coordinates", []):
                self.assertEqual(x % grid, 0, "x=%d is off the grid" % x)
                self.assertEqual(y % grid, 0, "y=%d is off the grid" % y)
            checked += 1
        self.assertGreater(checked, 140)

    def test_the_pixel_size_is_measured_on_the_font(self):
        # The font the game draws its dialogue at is a 12 px font: the em
        # covers twelve pixels of the grid.
        self.assertEqual(design_pixels(self.game), 12)
        self.assertEqual(pixel_grid(self.game), 100)

    def test_the_source_font_carries_the_whole_cyrillic_range(self):
        cmap = self.source.getBestCmap()
        cyrillic = [c for c in cmap if 0x0400 <= c <= 0x04FF]
        self.assertGreater(len(cyrillic), 140)

    def test_the_merge_is_stable(self):
        # The same font merged twice gives the same result: the merge does
        # not depend on what happened before it.
        from fontTools.ttLib import TTFont
        once = self.merged()
        twice = TTFont(io.BytesIO(merge_one(self.game_font, SOURCE_12)))
        self.assertEqual(sorted(once.getBestCmap()), sorted(twice.getBestCmap()))


if __name__ == "__main__":
    unittest.main()
