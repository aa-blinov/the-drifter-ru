#!/usr/bin/env python
"""Метрики шрифта, измеренные, а не взятые по умолчанию.

Игра рисует текст шрифтами из своих собственных ассетов, и у каждого из
них своя пропорция: насколько высок стоит заглавная буква, где проходит
базовая линия, насколько глубоко уходит выносной элемент и как велик один
пиксель её сетки. Кириллические глифы должны совпадать с этими
пропорциями, иначе русский текст выглядит как чужой шрифт, вставленный
в середину английской строки.

Здесь всё измеряется на самом шрифте: пиксельная сетка это наибольший
общий делитель координат его букв, а высоты берутся из самих букв.
"""
from __future__ import annotations

import io
import os
from math import gcd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "work", "fonts")

# Источник кириллических глифов: пиксельный шрифт со всем кириллическим
# диапазоном. Файл выбирается по размеру прорисовки целевого шрифта.
CYRILLIC_SOURCES = {
    10: "ark-pixel-10px-proportional-latin.ttf",
    12: "ark-pixel-12px-proportional-latin.ttf",
    16: "ark-pixel-16px-proportional-latin.ttf",
}


def _coordinates(font, name):
    """Контурные точки одного глифа."""
    glyf = font["glyf"]
    glyph = glyf[name]
    try:
        coordinates, _end, _flags = glyph.getCoordinates(glyf)
    except Exception:
        return []
    return coordinates


def pixel_grid(font) -> int:
    """Размер одного пикселя шрифта в единицах шрифта.

    У пиксельного шрифта нет координаты вне своей сетки, поэтому наибольший
    общий делитель координат его глифов и есть размер одного пикселя.
    """
    grid = 0
    for name in font.getGlyphOrder():
        for x, y in _coordinates(font, name):
            grid = gcd(grid, abs(int(x)))
            grid = gcd(grid, abs(int(y)))
    return grid


def height_of(font, char) -> int:
    """Высота одной буквы в единицах шрифта."""
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
    """Координата y базовой линии в единицах шрифта."""
    codepoint = ord(char)
    cmap = font.getBestCmap()
    if codepoint not in cmap:
        return 0
    points = _coordinates(font, cmap[codepoint])
    if not points:
        return 0
    return min(p[1] for p in points)


class Metrics:
    """Как выглядит один шрифт в его собственных единицах."""

    def __init__(self, font):
        self.upem = font["head"].unitsPerEm
        self.grid = pixel_grid(font) or 1
        self.cap = height_of(font, "H")
        self.x_height = height_of(font, "x")
        self.ascent = height_of(font, "h")
        self.descent = max(0, height_of(font, "p") - height_of(font, "x"))

    @property
    def pixels(self) -> float:
        """Сколько пикселей своей сетки покрывает em."""
        return self.upem / self.grid

    def describe(self, label=""):
        return ("%s upem %d, %.1f px em, cap %d, x-height %d"
                % (label, self.upem, self.pixels, self.cap, self.x_height))


def load_font(data):
    """Шрифт из своих байтов или по пути к нему."""
    from fontTools.ttLib import TTFont
    if isinstance(data, (bytes, bytearray)):
        return TTFont(io.BytesIO(data))
    return TTFont(data)
