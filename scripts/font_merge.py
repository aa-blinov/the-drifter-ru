#!/usr/bin/env python
"""Кириллические глифы, влитые в шрифты игры.

Игра рисует текст шрифтами из своих собственных ассетов, и ни один из них
не несёт кириллического глифа. Поэтому русская строка рисуется шрифтом,
которого игра не знает, и подстановка не похожа на игру.

Кириллица добавляется в собственные шрифты игры. Как именно решают два
измерения:

  x-height, то есть высота строчных букв. Кириллица масштабируется под
  x-height латиницы в том же шрифте, поэтому русская строка имеет тот же
  цвет и тот же ритм, что английская;

  базовая линия, то есть черта, на которой буквы стоят. Кириллица ставится
  на базовую линию латиницы, поэтому две никогда не стоят на разной высоте.

Доступны два способа масштабирования, и они тянут в разные стороны:

  "metric" масштабирует источник под x-height цели. Строчные кириллицы в
  точности той же высоты, что строчные латиницы, и строка переносится там,
  где велит метрика самой игры. Края глифов не попадают на пиксельную
  сетку игры, поэтому они рисуются чуть мягче латиницы.

  "grid" масштабирует источник так, чтобы один пиксель источника стал
  одним пикселем цели. Глифы такие же чёткие, как латиница, но у
  исходного начертания своя пропорция, и его строчные выходят выше
  строчных игры.

Источник это Ark Pixel Font: пиксельный шрифт со всем кириллическим
диапазоном.
"""
from __future__ import annotations

import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from font_metrics import (CYRILLIC_SOURCES, FONT_DIR, Metrics,  # noqa: E402
                          load_font)

# Символы, которые нужны русскому тексту помимо латинского диапазона.
EXTRA_CHARS = "«»—…№„“”‘’°"


def source_for(target: Metrics):
    """Пиксельный шрифт, из которого берётся кириллица.

    Берётся тот, который вписывается в цель без искажения: масштаб,
    ближайший к единице. Глиф, нарисованный для другого размера, приходится
    перерисовывать, а перерисовка ломает пиксельную сетку.

    Размер прорисовки цели сравнить не с чем: у шрифтов игры сетка не
    определяется, и «пикселей на em» выходит в тысячу. Поэтому мера здесь
    одна: насколько источник придётся растянуть.
    """
    best = None
    for size, name in sorted(CYRILLIC_SOURCES.items()):
        path = os.path.join(FONT_DIR, name)
        if not os.path.exists(path):
            continue
        metrics = Metrics(load_font(path))
        scale = scale_for(target, metrics, "metric")
        distance = abs(scale - 1.0)
        if best is None or distance < best[0]:
            best = (distance, path, metrics)
    if best is None:
        raise SystemExit(
            "в %s нет пиксельного шрифта\n"
            "Запустите scripts/fetch_fonts.py, чтобы скачать пиксельные шрифты." % FONT_DIR)
    return best[1], best[2]


def scale_for(target: Metrics, source: Metrics, mode: str) -> float:
    """Во сколько раз источник масштабируется под цель."""
    if mode == "grid":
        # Один пиксель источника становится одним пикселем цели.
        if target.grid <= 1 or source.grid <= 1:
            raise SystemExit(
                "у шрифта цели не определяется пиксельная сетка (%d), "
                "режим сетки неприменим: глифы сойдут в ноль. "
                "Используйте режим x-height." % target.grid)
        return target.grid / float(source.grid)
    if mode == "metric":
        # Строчные источника становятся той же высоты, что строчные цели.
        return target.x_height / float(source.x_height)
    if mode == "cap":
        # Заглавные источника становятся той же высоты, что заглавные цели.
        # У игры капитель ниже относительно строчных, чем у Ark Pixel, и
        # именно по ней русский текст кажется чужим.
        return target.cap / float(source.cap)
    raise SystemExit("неизвестный режим слияния: %s" % mode)


def merge(original: bytes, source_path: str, mode: str = "metric", bold: int = 0):
    """Добавить кириллические глифы источника к одному шрифту игры.

    Возвращает новый шрифт, число добавленных глифов и масштаб, в котором
    глифы нарисованы.

    `bold` — насколько контур утолщается, в единицах шрифта цели. У игры
    штрих тяжелее, чем у пиксельного источника, и разница видна: кириллица
    выглядит тоньше латиницы в одной строке. Утолщение рисует контур ещё раз
    со смещением; TrueType хранит координаты целыми, поэтому смещение должно
    быть целым, и буквы остаются пиксельными.
    """
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    target = load_font(original)
    source = load_font(source_path)

    target_metrics = Metrics(target)
    source_metrics = Metrics(source)
    if not target_metrics.x_height or not source_metrics.x_height:
        raise SystemExit("не удалось измерить x-height одного из шрифтов")

    scale = scale_for(target_metrics, source_metrics, mode)
    if scale <= 0 or scale > 4:
        raise SystemExit("масштаб %.3f вне диапазона: шрифт не текстовый" % scale)

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

        offsets = [(0, 0)]
        if bold:
            offsets += [(bold, 0), (-bold, 0), (0, bold), (0, -bold)]
        pen = TTGlyphPen(None)
        for dx, dy in offsets:
            transform = TransformPen(pen, (scale, 0, 0, scale, dx, dy))
            source_glyphs[source_name].draw(transform)
        target_glyphs.glyphs[glyph_name] = pen.glyph()

        advance, lsb = source_hmtx[source_name]
        target_hmtx.metrics[glyph_name] = (int(round(advance * scale)) + bold,
                                           int(round(lsb * scale)))
        order.append(glyph_name)
        existing.add(glyph_name)

        # Глиф, которому шрифт не может сопоставить символ, для отрисовщика не
        # существует. Новая запись идёт в каждую подтаблицу cmap с
        # юникодом.
        for subtable in target_cmap_table.tables:
            if subtable.isUnicode():
                subtable.cmap[codepoint] = glyph_name
        added += 1

    # Таблица glyf хранит свой порядок глифов, и он должен совпадать с
    # порядком шрифта: шрифт, у которого порядки расходятся, не
    # компилируется.
    target_glyphs.glyphOrder = order
    target.setGlyphOrder(order)

    buffer = io.BytesIO()
    target.save(buffer)
    return buffer.getvalue(), added, scale


def bounds_of(font, names):
    """Верхняя и нижняя точка набора глифов."""
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
