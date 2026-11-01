#!/usr/bin/env python
"""Гладкий шрифт кириллицы под метрики гладкого шрифта игры.

У игры есть шрифты двух родов. Пиксельные рисуются квадратами сетки, и
кириллица для них собирается растром (`make_pixel_font`). Гладкие шрифты
рисуются сглаженно, и кириллица для них собирается из контуров: контур
гарнитуры масштабируется так, чтобы высота строчных кириллических букв
совпала с высотой строчных латинских, а высота заглавных — с высотой
заглавных латинских.

Обе высоты масштабируются отдельно: у гладкого шрифта игры отношение
высот не то же, что у гарнитуры-источника, и одна общая величина
подогнала бы только одну из них. В пиксельном шрифте то же достигается
двумя кеглями, по одному на строчные и на заглавные.

Шрифт игры, у которого строчные и заглавные одной высоты и одинаковой
формы, рисует и кириллицу одной формы: строчные буквы берутся из
заглавных, иначе русские строчные выглядели бы иначе, чем английские в
той же строке.

    python3 scripts/make_smooth_font.py --play work/fonts \\
        --target work/fonts/cyr/target.ttf --out work/fonts/cyr/source.ttf
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from fontTools.fontBuilder import FontBuilder  # noqa: E402
from fontTools.pens.recordingPen import DecomposingRecordingPen  # noqa: E402
from fontTools.pens.transformPen import TransformPen  # noqa: E402
from fontTools.pens.ttGlyphPen import TTGlyphPen  # noqa: E402

from font_metrics import (baseline_of, bottom_of, descender_depth,  # noqa: E402
                          height_of, load_font, pixel_grid, unicase_of,
                          _coordinates)

# Знаки, которые нужны русскому тексту помимо букв. Два из них, «×» и «₂»,
# в шрифтах игры отсутствуют, и без них строки с ними читаются с дырами.
EXTRA_CHARS = "«»„“”‘’…—–№°×₂"

# Начертания, из которых собирается источник. Толщина штриха у латиницы
# игры своя у каждого шрифта, и начертание подбирается под неё.
WEIGHTS = (("Play-Regular.ttf", "Regular"), ("Play-Bold.ttf", "Bold"))

# Буквы-носители метрик. По ним измеряется высота строчных и заглавных
# источника, и по ней слияние понимает, во сколько раз увеличивать глифы. В
# игру они не попадают: слияние переносит только кириллицу.
CARRIERS = "xH"

# Кегль, в котором измеряется толщина штриха. Шрифты игры рисуются от
# десяти до сотни пикселей, и на таком кегле штрих виден целиком.
STEM_SIZE = 64


class Profile:
    """Как выглядит один гладкий шрифт игры."""

    def __init__(self, upem, x, cap, base_low, base_high, unicase, stem,
                 descender):
        self.upem = upem
        self.x = x
        self.cap = cap
        # Низ строчных и заглавных считается отдельно: у круглых букв он
        # лежит ниже базовой линии, и кириллица сяла бы на строку иначе.
        self.base_low = base_low
        self.base_high = base_high
        self.unicase = unicase
        self.stem = stem
        # Глубина выноса цели: во столько же уходит под базовую линию
        # кириллическая `р`.
        self.descender = descender

    def describe(self):
        return ("upem %d, x %d, cap %d, низ %d/%d, штрих %d, вынос %d%s"
                % (self.upem, self.x, self.cap, self.base_low, self.base_high,
                   self.stem, self.descender,
                   ", однорегистровый" if self.unicase else ""))

    def key(self):
        """Имя файла источника под этот профиль."""
        return "cyr-s%d-x%d-c%d-b%d-%d-s%d-d%d%s" % (
            self.upem, self.x, self.cap, self.base_low, self.base_high,
            self.stem, self.descender, "-u" if self.unicase else "")


def stem_of_font(data: bytes, size: int = STEM_SIZE):
    """Толщина штриха латиницы шрифта в пикселях кегля."""
    from PIL import Image, ImageDraw, ImageFont

    face = ImageFont.truetype(io.BytesIO(data), size)
    ascent, descent = face.getmetrics()
    image = Image.new("L", (size * 2, ascent + descent), 0)
    ImageDraw.Draw(image).text((4, ascent), "H", font=face, fill=255,
                               anchor="ls")
    widths = []
    for y in range(image.height):
        xs = [x for x in range(image.width) if image.getpixel((x, y)) >= 128]
        if not xs:
            continue
        runs = []
        start = prev = xs[0]
        for x in xs[1:]:
            if x != prev + 1:
                runs.append((start, prev))
                start = x
            prev = x
        runs.append((start, prev))
        widths.extend(b - a + 1 for a, b in runs)
    if not widths:
        return None
    return Counter(widths).most_common(1)[0][0]


def profile_of(data: bytes) -> Profile:
    """Профиль гладкого шрифта: высоты, базовые линии, форма букв."""
    font = load_font(data)
    return Profile(font["head"].unitsPerEm,
                   height_of(font, "x"),
                   height_of(font, "H"),
                   bottom_of(font, "x"),
                   bottom_of(font, "H"),
                   unicase_of(font),
                   stem_of_font(data),
                   descender_depth(font))


def choose_weight(play_dir: str, profile: Profile):
    """Начертание гарнитуры, чей штрих ближе к штриху шрифта игры."""
    best = None
    for filename, weight in WEIGHTS:
        path = os.path.join(play_dir, filename)
        if not os.path.exists(path):
            continue
        stem = stem_of_font(open(path, "rb").read())
        distance = abs((stem or 0) - (profile.stem or 0))
        if best is None or distance < best[0]:
            best = (distance, path, weight)
    if best is None:
        raise SystemExit("нет гарнитуры в %s" % play_dir)
    return best[1], best[2]


class StretchBelowPen:
    """Перо, растягивающее то, что лежит ниже базовой линии.

    Вынос кириллицы должен быть такой же глубины, как вынос латиницы цели,
    а у гарнитуры источника своя глубина. Растягивается только то, что ниже
    базовой линии: высота строчных и заглавных от этого не меняется.
    """

    def __init__(self, pen, baseline, factor):
        self.pen = pen
        self.baseline = baseline
        self.factor = factor

    def _point(self, point):
        x, y = point
        if y < self.baseline:
            y = self.baseline + (y - self.baseline) * self.factor
        return (x, y)

    def moveTo(self, point):
        self.pen.moveTo(self._point(point))

    def lineTo(self, point):
        self.pen.lineTo(self._point(point))

    def curveTo(self, *points):
        self.pen.curveTo(*[self._point(point) for point in points])

    def qCurveTo(self, *points):
        self.pen.qCurveTo(*[self._point(point) for point in points])

    def closePath(self):
        self.pen.closePath()

    def endPath(self):
        self.pen.endPath()

    def addComponent(self, name, transform):
        self.pen.addComponent(name, transform)


# Кириллические буквы, у которых есть вынос под базовую линию. У остальных
# букв низ ниже базовой это круглый выступ, а не вынос, и растягивать его
# нельзя: буква вырастет вниз и станет выше прочих.
DESCENDER_CHARS = set("руцщдУЦЩ")


def descender_factor(source, source_name, scale, target_depth, source_base,
                     char):
    """Во сколько раз растянуть вынос глифа под глубину цели.

    Возвращает единицу, когда растягивать нечего: либо у гарнитуры выноса
    нет, либо у цели выноса нет вовсе.
    """
    if target_depth <= 0 or char not in DESCENDER_CHARS:
        return 1.0
    points = _contour_points(source, source_name)
    if not points:
        return 1.0
    depth = (source_base - min(p[1] for p in points)) * scale
    if depth <= 0:
        return 1.0
    return target_depth / depth


def _contour_points(font, name):
    """Точки контура глифа."""
    if name is None:
        return []
    return _coordinates(font, name)


def build_source(target: bytes, play_dir: str,
                 name: str = "The Drifter Cyrillic"):
    """Шрифт кириллицы под метрики гладкого шрифта игры.

    Глиф источника уже в единицах цели: масштаб равен единице, и кириллица
    встаёт на базовую линию латиницы ровно.
    """
    profile = profile_of(target)
    path, weight = choose_weight(play_dir, profile)
    print("цель: %s" % profile.describe())
    print("источник: %s" % weight)

    source = load_font(path)
    source_cmap = source.getBestCmap()
    source_glyphs = source.getGlyphSet()
    source_hmtx = source["hmtx"].metrics
    # Часть букв гарнитуры собрана из основы и значка: `Й` это `И` с
    # чертой. Такие глифы разлагаются на контуры, иначе ссылка на основу
    # повисла бы в воздухе.
    decomposer = DecomposingRecordingPen(source_glyphs)

    low = profile.x / float(height_of(source, "x"))
    high = profile.cap / float(height_of(source, "H"))
    # Базовая линия считается по самим буквам: у круглых букв низ лежит
    # ниже базовой, и сдвиг по `H` посадил бы русские строчные ниже
    # английских.
    source_base_low = bottom_of(source, "н")
    source_base_high = bottom_of(source, "Н")
    target_base_low = profile.base_low
    target_base_high = profile.base_high

    codes = {code for code in source_cmap if 0x400 <= code <= 0x4FF}
    codes |= {ord(ch) for ch in EXTRA_CHARS}
    codes |= {ord(ch) for ch in CARRIERS}

    glyph_order = [".notdef"]
    glyphs = {".notdef": TTGlyphPen(None).glyph()}
    metrics = {".notdef": (profile.upem // 2, 0)}
    cmap = {}

    for code in sorted(codes):
        char = chr(code)
        capital = char.isupper()
        if profile.unicase and char.islower() and 0x400 <= code <= 0x4FF:
            # Однорегистровый шрифт рисует строчную букву заглавной формой,
            # и кириллица должна быть такой же.
            source_char = char.upper()
            capital = True
        else:
            source_char = char
        scale = high if capital else low
        source_name = source_cmap.get(ord(source_char))
        if source_name is None:
            continue

        pen = TTGlyphPen(None)
        if capital:
            shift = target_base_high - source_base_high * scale
        else:
            shift = target_base_low - source_base_low * scale
        # Вынос глифа растягивается под глубину выноса цели: у гарнитуры
        # своя глубина, и кириллическая `р` провисала бы иначе, чем `p`.
        factor = descender_factor(source, source_name, scale,
                                  profile.descender,
                                  source_base_high if capital
                                  else source_base_low,
                                  char)
        target = StretchBelowPen(pen, target_base_low if not capital
                                  else target_base_high, factor)
        transform = TransformPen(target, (scale, 0, 0, scale, 0, shift))
        decomposer.value = []
        source_glyphs[source_name].draw(decomposer)
        decomposer.replay(transform)

        glyph_name = "uni%04X" % code
        glyphs[glyph_name] = pen.glyph()
        glyph_order.append(glyph_name)
        advance, lsb = source_hmtx[source_name]
        metrics[glyph_name] = (int(round(advance * scale)),
                               int(round(lsb * scale)))
        cmap[code] = glyph_name

    builder = FontBuilder(profile.upem, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(cmap)
    builder.setupHorizontalMetrics(metrics)
    builder.glyphs = glyphs
    builder.setupGlyf(glyphs)
    ascent = profile.base_high + profile.cap
    descent = max(0, -profile.base_high)
    builder.setupHorizontalHeader(ascent=ascent, descent=descent, lineGap=0)
    builder.setupOS2(sTypoAscender=ascent, sTypoDescender=-descent,
                      usWinAscent=ascent, usWinDescent=descent)
    builder.setupNameTable({"familyName": name, "styleName": "Regular",
                            "uniqueFontIdentifier": name,
                            "fullName": name, "psName": name,
                            "version": "Version 1.0"})
    builder.setupPost()
    buffer = io.BytesIO()
    builder.save(buffer)
    return buffer.getvalue()


def source_for(target: bytes, play_dir: str, cache_dir: str):
    """Путь к источнику под этот шрифт: готовый файл или новый.

    Источников по профилям получается несколько, и каждый нужен один раз,
    поэтому они лежат в кэше и переиспользуются.
    """
    profile = profile_of(target)
    path = os.path.join(cache_dir, profile.key() + ".ttf")
    if os.path.exists(path):
        return path
    data = build_source(target, play_dir)
    os.makedirs(cache_dir, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def is_smooth(target: bytes) -> bool:
    """Гладкий ли шрифт: у него нет пиксельной сетки."""
    return pixel_grid(load_font(target)) <= 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--play", required=True,
                        help="каталог с гарнитурами Play")
    parser.add_argument("--target", required=True,
                        help="шрифт игры, под который собирается кириллица")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    if not os.path.isdir(args.play):
        raise SystemExit("нет каталога с гарнитурами: %s" % args.play)
    if not os.path.exists(args.target):
        raise SystemExit("нет шрифта цели: %s" % args.target)

    data = build_source(open(args.target, "rb").read(), args.play)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as fh:
        fh.write(data)
    print("записано: %s (%d байт)" % (args.out, len(data)))


if __name__ == "__main__":
    main()
