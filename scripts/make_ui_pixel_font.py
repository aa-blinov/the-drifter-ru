#!/usr/bin/env python
"""Целый пиксельный шрифт на место гладкого шрифта интерфейса.

Меню и подписи реплик игра рисует гладким CarroisGothic, и кириллица в нём
гладкая. Здесь шрифт заменяется Ark Pixel целиком: латиница и кириллица
идут одной гарнитурой, и строка не распадается на два рисунка. Метрики
(подъём, спуск) берутся у заменяемого шрифта, поэтому высота строки в
панелях остаётся той, под которую игра разложена.
"""
from __future__ import annotations

import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fontTools import subset  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

import font_source  # noqa: E402

# Размер, в котором нарисован Ark: на нём пиксельные края получаются ровными,
# а на другом размере округление размывает их.
ARK_FILE = "ArkPixel-12px-Proportional-Latin.ttf"


def build(target: bytes, ark_dir: str) -> bytes:
    """Шрифт Ark Pixel с набором знаков и метриками шрифта-цели."""
    target_font = TTFont(io.BytesIO(target))
    chars = set(target_font.getBestCmap())
    chars.update(range(0x0400, 0x0500))
    chars.update(ord(c) for c in font_source.EXTRA_CHARS)

    ark = TTFont(os.path.join(ark_dir, ARK_FILE))
    options = subset.Options()
    options.layout_features = ["kern"]
    options.notdef_outline = True
    options.name_IDs = ["*"]
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=sorted(chars))
    subsetter.subset(ark)

    # Подъём и спуск цели, пересчитанные в единицы Ark: строка занимает ту же
    # долю кегля, что и со шрифтом игры.
    ratio = ark["head"].unitsPerEm / float(target_font["head"].unitsPerEm)
    ascent = round(target_font["hhea"].ascent * ratio)
    descent = round(target_font["hhea"].descent * ratio)
    ark["hhea"].ascent, ark["hhea"].descent, ark["hhea"].lineGap = ascent, descent, 0
    os2 = ark["OS/2"]
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = ascent, descent, 0
    os2.usWinAscent, os2.usWinDescent = ascent, -descent

    # Пробел Ark такой же ширины, как буква, и слова в строке расходятся
    # дальше, чем в шрифте игры. Он подтянут к четырём пикселям.
    cmap = ark.getBestCmap()
    for code in (0x20, 0xA0):
        if code in cmap:
            ark["hmtx"][cmap[code]] = (ark["head"].unitsPerEm // 3, 0)

    out = io.BytesIO()
    ark.save(out)
    return out.getvalue()


if __name__ == "__main__":
    src, ark_dir, dst = sys.argv[1:4]
    data = build(open(src, "rb").read(), ark_dir)
    open(dst, "wb").write(data)
    print("%s: %d байт" % (dst, len(data)))
