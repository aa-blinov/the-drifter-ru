#!/usr/bin/env python
"""The Cyrillic glyphs, merged into the fonts of the game.

The game draws its text with the fonts in its own assets, and none of them
carries a Cyrillic glyph. A Russian line is therefore drawn with a font the
game does not know, and the fallback does not look like the game.

The Cyrillic is added to the game's own fonts. Two measurements decide how:

  the x-height — the height of the lowercase letters. The Cyrillic is scaled
  to the x-height of the Latin in the same font, so a Russian line has the
  same colour and the same rhythm as an English one;

  the baseline — the line the letters stand on. The Cyrillic is put on the
  baseline of the Latin, so the two never sit at different heights.

Two ways of scaling are available, and they pull in opposite directions:

  "metric" scales the source to the x-height of the target. The lowercase
  of the Cyrillic is exactly as tall as the lowercase of the Latin, and the
  line breaks where the game's own metrics say it does. The edges of the
  glyphs do not land on the pixel grid of the game, so they are drawn a
  little softer than the Latin.

  "grid" scales the source so that one pixel of the source is one pixel of
  the target. The glyphs are as crisp as the Latin, but the source typeface
  has its own proportions, and its lowercase comes out taller than the
  lowercase of the game.

The source is Ark Pixel Font: a pixel font with the whole Cyrillic range.
"""
from __future__ import annotations

import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from font_metrics import (CYRILLIC_SOURCES, FONT_DIR, Metrics,  # noqa: E402
                          load_font)

# The characters the Russian text needs beyond the Latin range.
EXTRA_CHARS = "«»—…№„“”‘’°"


def source_for(target: Metrics):
    """The pixel font the Cyrillic is taken from.

    The source is the one whose design size is closest to the design size of
    the target: a glyph drawn for a different size has different
    proportions.
    """
    best = None
    for size, name in sorted(CYRILLIC_SOURCES.items()):
        path = os.path.join(FONT_DIR, name)
        if not os.path.exists(path):
            continue
        metrics = Metrics(load_font(path))
        distance = abs(metrics.pixels - target.pixels)
        if best is None or distance < best[0]:
            best = (distance, path, metrics)
    if best is None:
        raise SystemExit(
            "no pixel font found in %s\n"
            "Run scripts/fetch_fonts.py to download the pixel fonts." % FONT_DIR)
    return best[1], best[2]


def scale_for(target: Metrics, source: Metrics, mode: str) -> float:
    """How much the source is scaled to fit the target."""
    if mode == "grid":
        # One pixel of the source becomes one pixel of the target.
        return target.grid / float(source.grid)
    if mode == "metric":
        # The lowercase of the source becomes as tall as the lowercase of
        # the target.
        return target.x_height / float(source.x_height)
    raise SystemExit("unknown merge mode: %s" % mode)


def merge(original: bytes, source_path: str, mode: str = "metric"):
    """Add the Cyrillic glyphs of the source to one game font.

    Returns the new font, the number of glyphs added and the scale the glyphs
    were drawn at.
    """
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    target = load_font(original)
    source = load_font(source_path)

    target_metrics = Metrics(target)
    source_metrics = Metrics(source)
    if not target_metrics.x_height or not source_metrics.x_height:
        raise SystemExit("cannot measure the x-height of one of the fonts")

    scale = scale_for(target_metrics, source_metrics, mode)
    if scale <= 0 or scale > 4:
        raise SystemExit("the scale %.3f is out of range: the font is not a "
                         "text font" % scale)

    source_cmap = source.getBestCmap()
    wanted = {codepoint for codepoint in source_cmap
              if 0x0400 <= codepoint <= 0x04FF}
    wanted |= {ord(ch) for ch in EXTRA_CHARS if ord(ch) in source_cmap}

    target_cmap = target.getBestCmap()
    target_glyphs = target["glyf"]
    target_hmtx = target["hmtx"]
    target_cmap_table = target["cmap"]
    source_glyphs = source.getGlyphSet()
    source_hmtx = source["hmtx"]
    order = list(target.getGlyphOrder())
    existing = set(order)

    added = 0
    for codepoint in sorted(wanted):
        if codepoint in target_cmap:
            continue
        source_name = source_cmap.get(codepoint)
        if not source_name:
            continue
        glyph_name = "ru%04X" % codepoint
        if glyph_name in existing:
            continue

        pen = TTGlyphPen(None)
        transform = TransformPen(pen, (scale, 0, 0, scale, 0, 0))
        source_glyphs[source_name].draw(transform)
        target_glyphs.glyphs[glyph_name] = pen.glyph()

        advance, lsb = source_hmtx[source_name]
        target_hmtx.metrics[glyph_name] = (int(round(advance * scale)),
                                           int(round(lsb * scale)))
        order.append(glyph_name)
        existing.add(glyph_name)

        # A glyph the font cannot map a character to does not exist for the
        # renderer. Every unicode subtable of the cmap gets the new entry.
        for subtable in target_cmap_table.tables:
            if subtable.isUnicode():
                subtable.cmap[codepoint] = glyph_name
        added += 1

    # The glyf table keeps its own order of the glyphs, and it has to be the
    # same order as the font's: a font whose two orders disagree does not
    # compile.
    target_glyphs.glyphOrder = order
    target.setGlyphOrder(order)

    buffer = io.BytesIO()
    target.save(buffer)
    return buffer.getvalue(), added, scale


def bounds_of(font, names):
    """The highest and the lowest point of a set of glyphs."""
    from font_metrics import _coordinates
    top = 0
    bottom = 0
    for name in names:
        points = _coordinates(font, name)
        if not points:
            continue
        ys = [p[1] for p in points]
        top = max(top, max(ys))
        bottom = min(bottom, min(ys))
    return top, bottom
