#!/usr/bin/env python
"""Измерение ширины русской строки против английской.

Игра рисует текст своими шрифтами. Русская строка шире своего английского
источника не помещается там, где помещалась английская, и игра переносит
её, а перенесённая часть падает на то, что ниже.

Ширина строки это сумма ширин её символов в единицах шрифта; em это ширина
буквы «M» в тех же единицах. Латиница берётся из шрифта игры; кириллица это
пиксельный шрифт, влитый в него, и именно его установщик пишет в игру.

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

# Шрифты, которыми рисуется текст.
FONTS = ["ChevyRay - Pinch - EU - AA", "tecno_small", "CrawlTextBodyWide-EU"]


def advances(font, text):
    """Ширина текста в единицах шрифта."""
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
    """Ширина текста в em."""
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

    print("| Шрифт | Медиана | p90 | p99 | Максимум |")
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
