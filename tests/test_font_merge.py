#!/usr/bin/env python
"""Слияние шрифтов: кириллица должна лечь на сетку шрифта игры.

Игра рисует текст шрифтами из своих ассетов, и кириллицы нет ни в одном из
них. Кириллица вписывается в эти шрифты, и вписывается под их метрики:
высота строчных, высота заглавных, толщина штриха и пиксельная сетка.

Тест берёт настоящий шрифт игры и проверяет вписанную кириллицу:

  кириллические глифы на месте, вместе со знаками «×» и «₂», которых в
  шрифтах игры нет вовсе;

  исходные глифы не тронуты;

  высота строчных и заглавных кириллицы совпадает с высотой латиницы;

  каждая координата кириллицы кратна числу единиц на пиксель у цели, и
  масштаб слияния равен единице.

Сама игра не нужна: слияние работает только с данными шрифта, а метрики
шрифта игры совпадают с метриками любого шрифта с тем же профилем.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from font_merge import merge  # noqa: E402
from font_metrics import (Metrics, bottom_of, descender_depth,  # noqa: E402
                          grid_is_exact, load_font, pixel_grid, unicase_of,
                          _coordinates)
import font_source  # noqa: E402

FONT_DIR = os.path.join(ROOT, "work", "fonts")
PLAY_REGULAR = os.path.join(FONT_DIR, "Play-Regular.ttf")
PLAY_BOLD = os.path.join(FONT_DIR, "Play-Bold.ttf")
CACHE = os.path.join(FONT_DIR, "cyr")


def glyph_height(font, name):
    """Высота глифа в единицах шрифта."""
    points = _coordinates(font, name)
    if not points:
        return None
    ys = [p[1] for p in points]
    return max(ys) - min(ys)


def glyph_bottom(font, name):
    """Нижняя точка глифа в единицах шрифта: базовая линия."""
    points = _coordinates(font, name)
    if not points:
        return None
    return min(p[1] for p in points)


class FontMergeTest(unittest.TestCase):
    """Кириллица в шрифте игры."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(PLAY_REGULAR) or not os.path.exists(PLAY_BOLD):
            raise unittest.SkipTest(
                "гарнитуры Play не скачаны: %s" % FONT_DIR)
        from fontTools.ttLib import TTFont
        cls.play = TTFont(PLAY_REGULAR)

    def targets(self):
        """Все шрифты игры, которыми рисуется текст."""
        path = os.path.join(ROOT, "work", "pristine.assets")
        if not os.path.exists(path):
            raise unittest.SkipTest("нет ассетов игры: %s" % path)
        import UnityPy
        from patch_assets import font_objects
        from install import GAME_FONTS

        env = UnityPy.load(path)
        return [(name, raw) for _obj, name, raw in font_objects(env)
                if name in GAME_FONTS]

    def merged(self):
        """Слитый шрифт игры и его профиль."""
        name, raw = self.targets()[0]
        source = font_source.source_for(raw, FONT_DIR, CACHE)
        data, added, scale = merge(raw, source, "same")
        return name, raw, data, added, scale

    def test_the_cyrillic_glyphs_are_added(self):
        _name, _raw, data, _added, _scale = self.merged()
        cmap = load_font(data).getBestCmap()
        for codepoint in (ord("А"), ord("я"), ord("Ё"), ord("ё"),
                          ord("«"), ord("»"), ord("—"), ord("…")):
            self.assertIn(codepoint, cmap,
                          "глиф для U+%04X отсутствует" % codepoint)

    def test_the_signs_missing_from_the_game_are_added(self):
        """Знаков «×» и «₂» в шрифтах игры нет, а перевод их использует.

        У части шрифтов игры знака «×» нет вовсе, а «₂» нет ни в одном:
        без них строки «2×4» и «CO₂» читались бы дырами.
        """
        absent = 0
        for name, raw in self.targets():
            source = font_source.source_for(raw, FONT_DIR, CACHE)
            data, _added, _scale = merge(raw, source, "same")
            original = load_font(raw).getBestCmap()
            merged = load_font(data).getBestCmap()
            for codepoint in (ord("×"), ord("₂")):
                if codepoint not in original:
                    absent += 1
                self.assertIn(codepoint, merged,
                              "в шрифте %s знак U+%04X не вписан"
                              % (name, codepoint))
        self.assertGreater(absent, 0,
                           "во всех шрифтах игры знаки есть, тест неверен")

    def test_the_original_glyphs_are_untouched(self):
        from fontTools.ttLib import TTFont
        _name, raw, data, _added, _scale = self.merged()
        before = TTFont(io.BytesIO(raw))
        after = TTFont(io.BytesIO(data))
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
        _name, _raw, data, _added, _scale = self.merged()
        merged = load_font(data)
        grid = Metrics(merged).grid
        self.assertGreater(grid, 0)
        cmap = merged.getBestCmap()
        checked = 0
        for codepoint, name in cmap.items():
            if not (0x0400 <= codepoint <= 0x04FF):
                continue
            for x, y in _coordinates(merged, name):
                self.assertEqual(x % grid, 0, "x=%d вне сетки" % x)
                self.assertEqual(y % grid, 0, "y=%d вне сетки" % y)
            checked += 1
        self.assertGreater(checked, 140)

    def test_the_merge_scale_is_one(self):
        """Масштаб единицы: источник уже собран в единицах цели."""
        _name, _raw, _data, _added, scale = self.merged()
        self.assertAlmostEqual(scale, 1.0, places=6)

    def test_the_cyrillic_can_be_made_smaller(self):
        """Уменьшенная кириллица ниже латинских букв, но на той же строке.

        Размер задаётся в установщике: кириллица остаётся на базовой линии,
        но сама ниже латинских букв, и русская строка читается спокойнее.
        """
        size = font_source.DEFAULT_SIZE
        for name, raw in self.targets():
            source = font_source.source_for(raw, FONT_DIR, CACHE)
            data, _added, _scale = merge(raw, source, "same", size=size)
            original = load_font(raw)
            merged = load_font(data)
            latin = original.getBestCmap()
            expected = glyph_height(original, latin[ord("x")])
            found = glyph_height(merged, "ru0445")
            self.assertLessEqual(
                abs(found - expected * size), expected * 0.02,
                "в шрифте %s высота кириллицы (%d) не такова, как ждали от "
                "размера %.2f" % (name, found, size))
            # Базовая линия общая: буква стоит на строке, а не провисает.
            self.assertEqual(
                glyph_bottom(merged, "ru0445"),
                glyph_bottom(original, latin[ord("x")]),
                "в шрифте %s уменьшенная кириллица сошла с базовой линии"
                % name)

    def test_the_cyrillic_matches_the_latin_height(self):
        """Высота строчных и заглавных кириллицы совпадает с латиницей.

        Плоские буквы сравниваются точно: у `х` и `x` высота строчных одна,
        у `Р` и `H` капитель одна. Круглые буквы выходят за высоту строчных,
        и выход этот у латиницы и у кириллицы различается: у гладкого шрифта
        доля выхода задана начертанием, поэтому для них допуск в три процента.

        У шрифта с округлёнными координатами сетка найдена по em, и глифы на
        ней лежат с точностью до единицы: там допуск в один пиксель сетки.
        """
        for name, raw in self.targets():
            unicase = unicase_of(load_font(raw))
            tolerance = self.tolerance(raw)
            source = font_source.source_for(raw, FONT_DIR, CACHE)
            data, _added, _scale = merge(raw, source, "same")
            original = load_font(raw)
            merged = load_font(data)
            latin = original.getBestCmap()
            for cyrillic, latin_char in (("ru0445", "x"), ("ru0420", "H")):
                expected = glyph_height(original, latin[ord(latin_char)])
                found = glyph_height(merged, cyrillic)
                self.assertIsNotNone(found,
                                     "в шрифте %s нет глифа %s"
                                     % (name, cyrillic))
                self.assertLessEqual(
                    abs(found - expected), tolerance,
                    "в шрифте %s высота %s (%d) не совпала с латиницей (%d)"
                    % (name, cyrillic, found, expected))
            # В однорегистровом шрифте кириллица рисуется заглавной формой,
            # и сравнивать её надо с латинской заглавной.
            for cyrillic, lower, upper in (("ru043E", "o", "O"),
                                           ("ru0440", "p", "P")):
                latin_char = upper if unicase else lower
                expected = glyph_height(original, latin[ord(latin_char)])
                found = glyph_height(merged, cyrillic)
                self.assertIsNotNone(found,
                                     "в шрифте %s нет глифа %s"
                                     % (name, cyrillic))
                self.assertLessEqual(
                    abs(found - expected), expected * 0.03,
                    "в шрифте %s высота %s (%d) разошлась с латинской (%d)"
                    % (name, cyrillic, found, expected))

    def test_the_cyrillic_sits_on_the_same_baseline(self):
        """Кириллица стоит на базовой линии латиницы.

        Смещённая базовая линия это строка, которая садится ниже соседней:
        русские буквы уезжают вниз, и строка выглядит разъехавшейся.
        """
        for name, raw in self.targets():
            source = font_source.source_for(raw, FONT_DIR, CACHE)
            data, _added, _scale = merge(raw, source, "same")
            original = load_font(raw)
            merged = load_font(data)
            latin = original.getBestCmap()
            for cyrillic, latin_char in (("ru0445", "x"), ("ru0420", "H")):
                expected = glyph_bottom(original, latin[ord(latin_char)])
                found = glyph_bottom(merged, cyrillic)
                self.assertIsNotNone(found,
                                     "в шрифте %s нет глифа %s"
                                     % (name, cyrillic))
                self.assertEqual(
                    found, expected,
                    "в шрифте %s базовая линия %s (%d) не совпала с "
                    "латинской (%d)" % (name, cyrillic, found, expected))

    def tolerance(self, raw: bytes) -> int:
        """На сколько кириллица может отличаться от латиницы.

        У шрифта с округлёнными координатами сетка найдена по em, и буквы
        лежат на ней с точностью до единицы: там допуск в один пиксель.
        """
        if grid_is_exact(load_font(raw)):
            return 0
        return pixel_grid(load_font(raw))

    def test_the_cyrillic_descenders_match_the_latin_ones(self):
        """Кириллические буквы провисают так же, как латинские.

        Вынос задаёт латиница цели: `p` и `g` уходят под базовую линию на
        свою глубину, и кириллическая `р` должна уходить так же. Иначе
        русские буквы висят на строке, а английские провисают, и строка
        выглядит собранной из двух разных шрифтов.
        """
        checked = 0
        for name, raw in self.targets():
            original = load_font(raw)
            target_depth = descender_depth(original)
            tolerance = self.tolerance(raw)
            unicase = unicase_of(original)
            source = font_source.source_for(raw, FONT_DIR, CACHE)
            data, _added, _scale = merge(raw, source, "same")
            merged = load_font(data)
            base = bottom_of(original, "x")
            for char in "руцщд":
                merged_depth = base - glyph_bottom(merged, "ru%04X" % ord(char))
                if self.source_has_descender(char, unicase):
                    if target_depth > 0:
                        self.assertLessEqual(
                            abs(merged_depth - target_depth), tolerance,
                            "в шрифте %s буква %s уходит на %d, а латиница "
                            "на %d" % (name, char, merged_depth, target_depth))
                else:
                    self.assertEqual(
                        merged_depth, 0,
                        "в шрифте %s у буквы %s хвост, которого нет у "
                        "источника" % (name, char))
            checked += 1
        self.assertGreater(checked, 0, "шрифтов в списке правки нет")

    def source_has_descender(self, char: str, unicase: bool) -> bool:
        """Есть ли у буквы гарнитуры-источника хвост.

        В однорегистровом шрифте кириллица рисуется заглавной формой, и
        хвост есть у той формы, что рисуется на самом деле.
        """
        form = char.upper() if unicase else char
        cmap = self.play.getBestCmap()
        name = cmap.get(ord(form))
        if name is None:
            return False
        points = _coordinates(self.play, name)
        if not points:
            return False
        base = bottom_of(self.play, "Н" if form.isupper() else "н")
        return base - min(p[1] for p in points) > 0

    def test_the_source_carries_the_whole_cyrillic_range(self):
        cmap = self.play.getBestCmap()
        cyrillic = [c for c in cmap if 0x400 <= c <= 0x4FF]
        self.assertGreater(len(cyrillic), 140)

    def test_the_smooth_fonts_take_the_cyrillic_too(self):
        """Гладкие шрифты игры тоже принимают кириллицу.

        Игровые шрифты двух родов: пиксельные и гладкие. У гладких нет
        сетки, и кириллица для них собирается из контуров, но она всё
        равно должна лечь в шрифт: иначе строка уходит в системный шрифт и
        выглядит чужой.
        """
        checked = 0
        for name, raw in self.targets():
            if font_source.is_pixel(raw):
                continue
            source = font_source.source_for(raw, FONT_DIR, CACHE)
            data, added, scale = merge(raw, source, "same")
            self.assertGreater(added, 200,
                               "в шрифт %s кириллица не легла" % name)
            self.assertAlmostEqual(scale, 1.0, places=6,
                                   msg="в шрифт %s масштаб не единица" % name)
            cmap = load_font(data).getBestCmap()
            for codepoint in (ord("а"), ord("А"), ord("я"), ord("ё")):
                self.assertIn(codepoint, cmap,
                              "в шрифте %s нет глифа U+%04X"
                              % (name, codepoint))
            checked += 1
        self.assertGreater(checked, 0,
                           "гладких шрифтов в списке правки нет, тест неверен")

    def test_the_cyrillic_of_a_unicase_font_looks_like_its_latin(self):
        """В однорегистровом шрифте кириллица рисуется заглавной формой.

        У такого шрифта строчная и заглавная буквы — одна и та же форма, и
        кириллица должна быть такой же, иначе русские строчные выглядели
        бы иначе, чем английские в одной строке.
        """
        checked = 0
        for name, raw in self.targets():
            original = load_font(raw)
            latin = original.getBestCmap()
            if latin.get(ord("A")) is None or latin.get(ord("a")) is None:
                continue
            upper = _coordinates(original, latin[ord("A")])
            lower = _coordinates(original, latin[ord("a")])
            if upper != lower:
                continue
            source = font_source.source_for(raw, FONT_DIR, CACHE)
            data, _added, _scale = merge(raw, source, "same")
            merged = load_font(data)
            cmap = merged.getBestCmap()
            self.assertEqual(_coordinates(merged, cmap[ord("а")]),
                             _coordinates(merged, cmap[ord("А")]),
                             "в шрифте %s строчная кириллица нарисована не "
                             "заглавной формой" % name)
            checked += 1
        self.assertGreater(checked, 0,
                           "однорегистровых шрифтов нет, тест неверен")


if __name__ == "__main__":
    unittest.main()
