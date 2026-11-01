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
    общий делитель координат его букв и есть размер одного пикселя.

    Глиф `.notdef` в расчёт не входит: он рисуется прямоугольником
    произвольного размера и к рисунку шрифта не относится. С ним делитель
    получается единицей, и сетка шрифта не определяется вовсе.

    У некоторых шрифтов координаты округлены до целых, и общий делитель из-за
    этого рассыпается: у `DrifterGothic13` пиксель это 1024/13 = 78.77, а в
    координатах стоят 79, 157, 236. Тогда сетка ищется по em: координаты
    должны лечь на кратные `upem/N` с точностью до единицы.
    """
    values = _grid_values(font)
    grid = 0
    for value in values:
        grid = gcd(grid, value)
    if grid > 1:
        return grid
    upem = font["head"].unitsPerEm
    for pixels in range(6, 49):
        step = upem / float(pixels)
        if all(abs(value - round(value / step) * step) <= 1.0
               for value in values):
            return int(round(step))
    return 1


def grid_is_exact(font) -> bool:
    """Делит ли сетка шрифта координаты нацело.

    У шрифта с округлёнными координатами сетка найдена по em, и глифы на
    ней лежат с точностью до единицы: высота кириллицы может отличаться от
    латинской на один пиксель.
    """
    values = _grid_values(font)
    grid = 0
    for value in values:
        grid = gcd(grid, value)
    return grid > 1


def _grid_values(font) -> list:
    """Все координаты букв шрифта по модулю."""
    values = set()
    for name in font.getGlyphOrder():
        if name == ".notdef":
            continue
        for x, y in _coordinates(font, name):
            values.add(abs(int(x)))
            values.add(abs(int(y)))
    return sorted(value for value in values if value)


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
    return bottom_of(font, char)


def bottom_of(font, char):
    """Нижняя точка буквы в единицах шрифта.

    У круглых букв она лежит ниже базовой линии: буква `о` чуть выходит
    за неё. Для латиницы и кириллицы это должны быть одни и те же числа,
    иначе русские буквы сядут на строку ниже английских.
    """
    codepoint = ord(char)
    cmap = font.getBestCmap()
    if codepoint not in cmap:
        return 0
    points = _coordinates(font, cmap[codepoint])
    if not points:
        return 0
    return min(p[1] for p in points)


# Латинские буквы, которые уходят под базовую линию. Их вынос задаёт
# глубину выноса шрифта: кириллическая `р` должна провисать так же.
DESCENDERS = "pgyqj"


def descender_depth(font) -> int:
    """Насколько шрифт уходит под базовую линию.

    Это глубина выноса латиницы. У шрифта, где выносов нет вовсе, глубина
    нулевая, и кириллица выноса не получает: у неё хвост есть только у
    `ц` и `щ`, и без него они не отличить от `ш`.
    """
    cmap = font.getBestCmap()
    base = bottom_of(font, "x")
    depths = [base - bottom_of(font, char) for char in DESCENDERS
              if ord(char) in cmap]
    return max(depths) if depths else 0


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


def unicase_of(font) -> bool:
    """Однорегистровый ли шрифт.

    В однорегистровом шрифте строчная буква нарисована той же формой, что и
    заглавная: `A` и `a` у него это один и тот же контур. Кириллица в таком
    шрифте должна быть нарисована так же, иначе русские строчные выглядели бы
    иначе, чем английские в одной строке.
    """
    cmap = font.getBestCmap()
    upper = cmap.get(ord("A"))
    lower = cmap.get(ord("a"))
    if upper is None or lower is None:
        return False
    return _coordinates(font, upper) == _coordinates(font, lower)


def load_font(data):
    """Шрифт из своих байтов или по пути к нему."""
    from fontTools.ttLib import TTFont
    if isinstance(data, (bytes, bytearray)):
        return TTFont(io.BytesIO(data))
    return TTFont(data)
