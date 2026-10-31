#!/usr/bin/env python
"""Measure the width of the Russian line against the English one.

The game draws its text with its own fonts. A Russian line that is wider
than its English source does not fit where the English fit, and the game
wraps it and the wrapped part falls on what is below.

The width of a line is the sum of the widths of its characters in the units
of the font; the em is the width of the letter «M» in the same units. The
Latin comes from the game's font; the Cyrillic is the pixel font merged into
it, which is what the installer writes into the game.

    python3 scripts/measure_widths.py
"""
from __future__ import annotations

import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from font_merge import merge, source_for  # noqa: E402
from font_metrics import Metrics, load_font  # noqa: E402

GAME = os.environ.get("DR_GAME_DIR",
                      r"S:\SteamLibrary\steamapps\common\The Drifter")
ASSETS = os.path.join(GAME, "TheDrifter_Data", "sharedassets1.assets")
CORPUS = os.path.join(ROOT, "corpus", "english.csv")
TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")

# The fonts the text is drawn with.
FONTS = ["ChevyRay - Pinch - EU - AA", "tecno_small", "CrawlTextBodyWide-EU"]


def advances(font, text):
    """The width of the text in the units of the font."""
    from fontTools.ttLib import TTFont

    hmtx = font["hmtx"]
    cmap = font.getBestCmap()
    total = 0
    for char in text:
        name = cmap.get(ord(char))
        if name is None:
            continue
        total += hmtx[name][0]
    return total


def width_of(font, text):
    """The width of the text, in em."""
    em = advances(font, "M")
    if not em:
        return 0.0
    return advances(font, text) / em


def main():
    import UnityPy

    from patch_assets import font_objects

    env = UnityPy.load(ASSETS)
    raw = {}
    for _obj, name, data in font_objects(env):
        raw[name] = data

    with io.open(CORPUS, encoding="utf-8", newline="") as fh:
        corpus = list(csv.reader(fh))[1:]
    with io.open(TRANSLATION, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.reader(fh))
    ru_col = table[0].index("Русский")
    translation = {"%s|%s" % (r[0], r[1]): r[ru_col] for r in table[1:]}

    print("| Font | Median | p90 | p99 | Max |")
    print("| --- | --- | --- | --- | --- |")
    for name in FONTS:
        data = raw.get(name)
        if data is None:
            print("| %s | нет в ассетах | | | |" % name)
            continue
        original = load_font(data)
        metrics = Metrics(original)
        source, _source_metrics = source_for(metrics)
        merged_bytes, _added, _scale = merge(data, source, mode="metric")
        merged = load_font(merged_bytes)

        ratios = []
        widths_en = []
        widths_ru = []
        for row in corpus:
            english = row[4]
            russian = translation.get("%s|%s" % (row[0], row[1]), "")
            if not english or not russian:
                continue
            en = width_of(original, english)
            ru = width_of(merged, russian)
            if en <= 0:
                continue
            ratios.append(ru / en)
            widths_en.append(en)
            widths_ru.append(ru)
        ratios.sort()
        widths_en.sort()
        widths_ru.sort()

        def pct(values, p):
            return values[min(len(values) - 1, int(len(values) * p))]

        print("| `%s` | %.2f | %.2f | %.2f | %.2f |"
              % (name, pct(ratios, 0.5), pct(ratios, 0.9),
                 pct(ratios, 0.99), ratios[-1]))
        print("  по распределениям: медиана %.2f, p90 %.2f, p99 %.2f, максимум %.2f"
              % (pct(widths_ru, 0.5) / pct(widths_en, 0.5),
                 pct(widths_ru, 0.9) / pct(widths_en, 0.9),
                 pct(widths_ru, 0.99) / pct(widths_en, 0.99),
                 widths_ru[-1] / widths_en[-1]))


if __name__ == "__main__":
    main()
