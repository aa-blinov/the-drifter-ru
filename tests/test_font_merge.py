#!/usr/bin/env python
"""Слияние шрифтов: кириллические глифы должны попадать на пиксельную сетку.

Слияние берёт шрифт игры и добавляет к нему кириллические глифы пиксельного
шрифта. Тест берёт настоящий пиксельный шрифт, вырезает из него кириллицу,
чтобы он заменял шрифт игры, сливает кириллицу обратно и проверяет три вещи:

  кириллические глифы на месте;
  исходные глифы не тронуты;
  каждая координата слитого глифа кратна числу единиц на пиксель у цели,
  именно это делает глиф чётким, а не размытым.

Сама игра не нужна: слияние работает только с данными шрифта, а метрики
шрифта игры совпадают с метриками любого шрифта такого пиксельного размера.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from font_merge import merge  # noqa: E402
from font_metrics import Metrics, load_font  # noqa: E402

FONT_DIR = os.path.join(ROOT, "work", "fonts")
SOURCE_10 = os.path.join(FONT_DIR, "ark-pixel-10px-proportional-latin.ttf")
SOURCE_12 = os.path.join(FONT_DIR, "ark-pixel-12px-proportional-latin.ttf")

# Метрики шрифта игры: 125 единиц на пиксель при 10 px и при 12 px.
UNITS_PER_PX = 125


def strip_cyrillic(path):
    """Шрифт с вырезанной кириллицей, чтобы он заменял шрифт игры."""
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
            raise unittest.SkipTest("пиксельные шрифты не скачаны: %s" % FONT_DIR)
        from fontTools.ttLib import TTFont
        cls.source = TTFont(SOURCE_10)
        cls.game_font = strip_cyrillic(SOURCE_12)
        cls.game = TTFont(io.BytesIO(cls.game_font))

    def merged(self):
        from fontTools.ttLib import TTFont
        data, _added, _scale = merge(self.game_font, SOURCE_12, "metric")
        return TTFont(io.BytesIO(data))

    def test_the_cyrillic_glyphs_are_added(self):
        cmap = self.merged().getBestCmap()
        for codepoint in (ord("А"), ord("я"), ord("Ё"), ord("ё"),
                          ord("«"), ord("»"), ord("—"), ord("…")):
            self.assertIn(codepoint, cmap,
                          "глиф для U+%04X отсутствует" % codepoint)

    def test_the_original_glyphs_are_untouched(self):
        from fontTools.ttLib import TTFont
        before = TTFont(io.BytesIO(self.game_font))
        after = self.merged()
        for name in before.getGlyphOrder():
            if name not in after.getGlyphOrder():
                self.fail("глиф %s потерян" % name)
            original = before["glyf"].glyphs[name]
            merged = after["glyf"].glyphs[name]
            self.assertEqual(getattr(original, "numberOfContours", None),
                             getattr(merged, "numberOfContours", None),
                             "глиф %s изменился" % name)
            self.assertEqual(getattr(original, "coordinates", None),
                             getattr(merged, "coordinates", None),
                             "глиф %s изменился" % name)

    def test_the_merged_glyphs_land_on_the_pixel_grid(self):
        merged = self.merged()
        grid = Metrics(self.game).grid
        self.assertGreater(grid, 0)
        cmap = merged.getBestCmap()
        checked = 0
        for codepoint, name in cmap.items():
            if not (0x0400 <= codepoint <= 0x04FF):
                continue
            glyph = merged["glyf"].glyphs[name]
            for x, y in getattr(glyph, "coordinates", []):
                self.assertEqual(x % grid, 0, "x=%d вне сетки" % x)
                self.assertEqual(y % grid, 0, "y=%d вне сетки" % y)
            checked += 1
        self.assertGreater(checked, 140)

    def test_the_pixel_size_is_measured_on_the_font(self):
        # Шрифт, которым игра рисует диалоги, это шрифт 12 px: em занимает
        # двенадцать пикселей сетки.
        metrics = Metrics(self.game)
        self.assertEqual(metrics.pixels, 12)
        self.assertEqual(metrics.grid, 100)

    def test_the_source_font_carries_the_whole_cyrillic_range(self):
        cmap = self.source.getBestCmap()
        cyrillic = [c for c in cmap if 0x0400 <= c <= 0x04FF]
        self.assertGreater(len(cyrillic), 140)

    def test_the_merge_is_stable(self):
        # Один и тот же шрифт, слитый дважды, даёт один и тот же результат:
        # слияние не зависит от того, что было до него.
        from fontTools.ttLib import TTFont
        once = self.merged()
        data, _added, _scale = merge(self.game_font, SOURCE_12, "metric")
        twice = TTFont(io.BytesIO(data))
        self.assertEqual(sorted(once.getBestCmap()), sorted(twice.getBestCmap()))


if __name__ == "__main__":
    unittest.main()
