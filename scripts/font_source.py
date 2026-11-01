#!/usr/bin/env python
"""Источник кириллицы под шрифт игры.

У игры шрифты двух родов. Пиксельные имеют сетку, и кириллица для них
собирается растром: глиф ложится на ту же сетку, что и латиница, и края
у него такие же (`make_pixel_font`). Гладкие шрифты сетки не имеют, и
кириллица для них собирается из контуров и масштабируется под высоты
(`make_smooth_font`).

Список знаков, которые нужны русскому тексту помимо букв, лежит здесь:
и сборщики, и слияние берут его отсюда, иначе знаки разъедутся.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from font_metrics import load_font, pixel_grid  # noqa: E402

# Знаки, которые нужны русскому тексту помимо букв. Два из них, «×» и «₂»,
# в шрифтах игры отсутствуют, и без них строки с ними читаются с дырами.
EXTRA_CHARS = "«»„“”‘’…—–№°×₂"

# Размер кириллицы против латиницы. Кириллица остаётся на базовой линии,
# но сама немного ниже латинских букв: русская строка читается спокойнее,
# и в панелях игры ей остаётся место.
DEFAULT_SIZE = 0.95


def is_pixel(target: bytes) -> bool:
    """Пиксельный ли шрифт: у него есть сетка."""
    return pixel_grid(load_font(target)) > 1


def source_for(target: bytes, play_dir: str, cache_dir: str):
    """Путь к источнику под этот шрифт: готовый файл или новый.

    Источник уже в единицах цели, поэтому при слиянии масштаб равен
    единице и кириллица встаёт на базовую линию латиницы ровно.
    """
    if is_pixel(target):
        import make_pixel_font
        return make_pixel_font.source_for(target, play_dir, cache_dir)
    import make_smooth_font
    return make_smooth_font.source_for(target, play_dir, cache_dir)
