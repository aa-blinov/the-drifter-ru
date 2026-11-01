#!/usr/bin/env python
"""Пиксельный шрифт кириллицы под метрики шрифта игры.

Игра рисует текст шрифтами из своих собственных ассетов, и кириллицы нет
ни в одном из них. Кириллица вписывается в эти шрифты, и вписывается под их
метрики: высота строчных, высота заглавных, толщина штриха и пиксельная
сетка.

Источник собирается из гарнитуры Play. Она не пиксельная, но её растр
совпадает с игровыми шрифтами до пикселя: у латиницы игры высота строчных и
высота заглавных совпадают с растром Play в целых кеглях, и кегль тот же
самый. Поэтому буква кириллицы рисуется не контуром, а квадратами сетки:
глиф ложится на ту же сетку, что и латиница, и края у него такие же.

Размер подбирается отдельно для строчных и для заглавных. У большинства
шрифтов игры обе высоты совпадают с одним кеглем, но у шрифта
`CrawlSmall-EU` заглавные и строчные одной высоты, и для заглавных нужен
свой кегль.

Толщина штриха тоже своя у каждого шрифта. Если растр тоньше нужного,
штрих утолщается на пиксель, а если толще — утончается: и то и другое
делается по пикселям, поэтому глиф остаётся на сетке.

    python3 scripts/make_pixel_font.py --play work/fonts \\
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
from fontTools.pens.ttGlyphPen import TTGlyphPen  # noqa: E402

from font_metrics import (baseline_of, descender_depth, height_of,  # noqa: E402
                          load_font, pixel_grid, unicase_of)
from font_source import EXTRA_CHARS  # noqa: E402

# Начертания, из которых собирается источник. Толщина штриха у латиницы игры
# своя у каждого шрифта, и начертание подбирается под неё.
WEIGHTS = (("Play-Regular.ttf", "Regular"), ("Play-Bold.ttf", "Bold"))

# Буквы-носители метрик. По ним измеряется высота строчных и заглавных
# источника, и по ней слияние понимает, во сколько раз увеличивать глифы. В
# игру они не попадают: слияние переносит только кириллицу.
CARRIERS = "xH"

# Во сколько раз глиф рисуется больше нужного: так одна точка исходного
# контура даёт заливку в половину пикселя, и край получается ровным.
SUPERSAMPLE = 4

_FACES = {}


class Profile:
    """Как выглядит один шрифт игры в единицах своей сетки."""

    def __init__(self, upem, grid, x_px, cap_px, stem_px, baseline, unicase,
                 descender_px):
        self.upem = upem
        self.grid = grid
        self.x_px = x_px
        self.cap_px = cap_px
        self.stem_px = stem_px
        self.baseline = baseline
        self.unicase = unicase
        # Глубина выноса цели в пикселях её сетки: во столько же уходит
        # под базовую линию кириллический `р`.
        self.descender_px = descender_px

    def describe(self):
        return ("сетка %d, x %d px, cap %d px, штрих %d px, базовая %d, "
                "вынос %d px%s"
                % (self.grid, self.x_px, self.cap_px, self.stem_px,
                   self.baseline, self.descender_px,
                   ", однорегистровый" if self.unicase else ""))

    def key(self):
        """Имя файла источника под этот профиль."""
        return "cyr-g%d-x%d-c%d-s%d-d%d%s" % (self.grid, self.x_px,
                                              self.cap_px, self.stem_px,
                                              self.descender_px,
                                              "-u" if self.unicase else "")


def profile_of(data: bytes) -> Profile:
    """Профиль шрифта: сетка, высоты, толщина штриха и базовая линия."""
    font = load_font(data)
    grid = pixel_grid(font)
    if grid <= 1:
        raise SystemExit("у шрифта не определяется пиксельная сетка")
    upem = font["head"].unitsPerEm
    design_px = max(1, upem // grid)
    x_px = round(height_of(font, "x") / grid)
    cap_px = round(height_of(font, "H") / grid)
    stem_px = stem_of_font(data, design_px)
    # Базовая линия привязывается к сетке: иначе кириллица встала бы на
    # полпикселя выше латиницы.
    baseline = round(baseline_of(font, "H") / grid) * grid
    descender_px = round(descender_depth(font) / grid)
    return Profile(upem, grid, x_px, cap_px, stem_px, baseline,
                   unicase_of(font), descender_px)


def _face(path: str, size: int):
    """Гарнитура, готовая к растеризации."""
    from PIL import ImageFont

    key = (path, size)
    if key not in _FACES:
        _FACES[key] = ImageFont.truetype(path, size * SUPERSAMPLE)
    return _FACES[key]


def rasterise(face, size: int, glyph: str, threshold: int = 2):
    """Битовая карта глифа в пикселях кегля.

    Возвращает строки сверху вниз, номер строки базовой линии и номер
    столбца, где стоит начало буквы. Строка с номером базовой линии и ниже
    лежат под ней: так выглядывают выносные элементы букв `р`, `у`, `д`.

    `threshold` — знаменатель доли заливки ячейки, при которой ячейка
    считается залитой. Обычная ячейка набирает половину, и этого хватает;
    тонкий знак вроде `ї` в маленьком кегле не набирает и четверти, и при
    половине он пропадает совсем.
    """
    from PIL import Image, ImageDraw

    ascent, descent = face.getmetrics()
    # Базовая линия должна попасть на границу пикселя, иначе буква размажется
    # по двум строкам. Для этого она поднимается до ближайшей границы.
    baseline = -(-ascent // SUPERSAMPLE) * SUPERSAMPLE
    pad = 4 * SUPERSAMPLE
    width = max(1, int(face.getlength(glyph)) + 2 * pad)
    height = baseline + descent
    image = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(image)
    draw.text((pad, baseline), glyph, font=face, fill=255, anchor="ls")

    rows = []
    for y in range(height // SUPERSAMPLE):
        row = []
        for x in range(width // SUPERSAMPLE):
            filled = 0
            for dy in range(SUPERSAMPLE):
                for dx in range(SUPERSAMPLE):
                    if image.getpixel((x * SUPERSAMPLE + dx,
                                       y * SUPERSAMPLE + dy)) >= 128:
                        filled += 1
            row.append(filled * threshold >= SUPERSAMPLE * SUPERSAMPLE)
        rows.append(row)
    return rows, baseline // SUPERSAMPLE, pad // SUPERSAMPLE


def ink_span(rows):
    """Первый и последний залитый столбец и строка в растре."""
    columns = [x for row in rows for x, v in enumerate(row) if v]
    filled = [y for y, row in enumerate(rows) if any(row)]
    if not columns:
        return None
    return (min(columns), max(columns), min(filled), max(filled))


def stem_width(rows):
    """Толщина штриха: самая частая ширина вертикальной полосы."""
    widths = []
    for row in rows:
        xs = [x for x, v in enumerate(row) if v]
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


def stem_of_font(data: bytes, design_px: int):
    """Толщина штриха латиницы шрифта, в пикселях его сетки."""
    from PIL import Image, ImageDraw, ImageFont

    face = ImageFont.truetype(io.BytesIO(data), design_px)
    ascent, descent = face.getmetrics()
    width = max(1, int(face.getlength("H")) + 8)
    image = Image.new("L", (width, ascent + descent), 0)
    ImageDraw.Draw(image).text((4, ascent), "H", font=face, fill=255,
                               anchor="ls")
    rows = [[image.getpixel((x, y)) >= 128 for x in range(image.width)]
            for y in range(image.height)]
    return stem_width(rows)


def measure(face, size: int):
    """Высота строчных и заглавных кириллицы в пикселях кегля.

    Меряются те буквы, что и рисуются: `н` и `Н`. У латинской `H` высота
    одна, у кириллической `Н` другая, и мерить нужно по той, что попадёт
    в шрифт.
    """
    x_rows, _base, _origin = rasterise(face, size, "н")
    h_rows, _base2, _origin2 = rasterise(face, size, "Н")
    x_span = ink_span(x_rows)
    h_span = ink_span(h_rows)
    if not x_span or not h_span:
        return None
    return x_span[3] - x_span[2] + 1, h_span[3] - h_span[2] + 1


def _table(path: str):
    """Все кегли гарнитуры с их высотами и толщиной штриха.

    Толщина штриха меряется по кириллическим буквам `н` и `Н`: они и есть
    результат, и штрих у них должен совпасть со штрихом латиницы цели.
    """
    table = []
    for size in range(4, 33):
        face = _face(path, size)
        measured = measure(face, size)
        if not measured:
            continue
        x_px, cap_px = measured
        lower = stem_width(rasterise(face, size, "н")[0])
        upper = stem_width(rasterise(face, size, "Н")[0])
        table.append((size, x_px, cap_px, lower, upper))
    return table


def choose_sizes(play_dir: str, profile: Profile):
    """Кегли гарнитуры под профиль цели.

    Для строчных берётся кегль, у которого высота строчных совпадает с
    целевой, для заглавных — кегль с совпадающей высотой заглавных. Один
    кегль на обе высоты предпочтителен: тогда обе половины алфавита
    нарисованы одной гарнитурой и выглядят одинаково.
    """
    best = None
    for filename, weight in WEIGHTS:
        path = os.path.join(play_dir, filename)
        if not os.path.exists(path):
            continue
        table = _table(path)
        for lower in table:
            if lower[1] != profile.x_px:
                continue
            for upper in table:
                if upper[2] != profile.cap_px:
                    continue
                score = (
                    # Один кегль на обе высоты лучше двух.
                    0 if lower[0] == upper[0] else 1,
                    # Штрих ближе к нужному.
                    abs((lower[3] or 0) - profile.stem_px),
                    abs((upper[4] or 0) - profile.stem_px),
                    lower[0] + upper[0],
                )
                if best is None or score < best[0]:
                    best = (score, path, weight, lower[0], upper[0])
    if best is None:
        raise SystemExit("нет гарнитуры, подходящей под профиль: %s"
                         % profile.describe())
    return best[1], best[2], best[3], best[4]


def thin(rows):
    """Штрих на пиксель тоньше: у каждой полосы снимается правый столбец.

    Полоса шириной в один пиксель остаётся как есть: снять с неё столбец
    значит снять её целиком, и буква потеряла бы штрих. Так исчезал хвост
    у `ц` и `щ`: он узкий, и от него не оставалось ничего.

    Высота строк не меняется, поэтому буква остаётся на базовой линии и
    капитель не вырастает.
    """
    out = []
    for row in rows:
        new = list(row)
        width = len(row)
        x = 0
        while x < width:
            if not row[x]:
                x += 1
                continue
            start = x
            while x < width and row[x]:
                x += 1
            if x - 1 > start:
                new[x - 1] = False
        out.append(new)
    return out


def thicken(rows):
    """Штрих на пиксель толще: к каждой полосе добавляется правый столбец.

    Высота строк не меняется, поэтому буква остаётся на базовой линии.
    """
    out = []
    for row in rows:
        new = list(row)
        for x, filled in enumerate(row):
            if filled and x + 1 < len(row):
                new[x + 1] = True
        out.append(new)
    return out


def _glyph_contours(rows, base, origin, grid, baseline):
    """Контуры глифа по растру: каждый залитый пиксель это квадрат сетки."""
    pen = TTGlyphPen(None)
    for y, row in enumerate(rows):
        for x, filled in enumerate(row):
            if not filled:
                continue
            # Строка базовой линии и ниже лежит под ней.
            bottom = baseline + (base - y - 1) * grid
            left = (x - origin) * grid
            pen.moveTo((left, bottom))
            pen.lineTo((left + grid, bottom))
            pen.lineTo((left + grid, bottom + grid))
            pen.lineTo((left, bottom + grid))
            pen.closePath()
    return pen.glyph()


def build_source(target: bytes, play_dir: str, name: str = "The Drifter Cyrillic"):
    """Шрифт кириллицы под метрики целевого шрифта.

    Целевой шрифт задаёт шесть вещей: шаг пиксельной сетки, высоту
    строчных, высоту заглавных, толщину штриха, положение базовой линии и
    ширину em. Гарнитура растеризуется в кеглях, где высоты совпадают, и
    кладётся на сетку цели.
    """
    profile = profile_of(target)
    path, weight, lower_size, upper_size = choose_sizes(play_dir, profile)
    grid = profile.grid
    print("цель: %s" % profile.describe())
    print("источник: %s, строчные %d px, заглавные %d px"
          % (weight, lower_size, upper_size))

    codes = _cyrillic_codepoints(path)
    codes |= {ord(ch) for ch in EXTRA_CHARS}
    codes |= {ord(ch) for ch in CARRIERS}

    glyph_order = [".notdef"]
    glyphs = {}
    metrics = {}
    cmap = {}

    glyphs[".notdef"] = TTGlyphPen(None).glyph()
    metrics[".notdef"] = (grid, 0)

    for code in sorted(codes):
        char = chr(code)
        capital = _is_capital(char)
        size = upper_size if capital else lower_size
        if profile.unicase and char.islower() and 0x400 <= code <= 0x4FF:
            # Однорегистровый шрифт рисует строчную букву заглавной формой,
            # и кириллица должна быть такой же.
            char = char.upper()
            capital = True
            size = upper_size
        face = _face(path, size)
        rows, base, origin = rasterise(face, size, char)
        if ink_span(rows) is None:
            # Тонкий знак в маленьком кегле не набирает половины ячейки и
            # пропадает из растра совсем. Ему порог снижается: лучше узкая
            # буква, чем дыра в строке.
            rows, base, origin = rasterise(face, size, char, threshold=4)
        if ink_span(rows) is None:
            continue
        rows = _fit_stem(rows, profile.stem_px)
        rows = fit_descender(rows, base, profile.descender_px)
        glyph_name = "uni%04X" % code
        glyphs[glyph_name] = _glyph_contours(rows, base, origin, grid,
                                            profile.baseline)
        glyph_order.append(glyph_name)
        # Ширина буквы берётся у гарнитуры и округляется до целого пикселя:
        # тогда буквы встают на сетку, и строка не разъезжается.
        advance_px = max(1, round(face.getlength(char) / SUPERSAMPLE))
        metrics[glyph_name] = (advance_px * grid, 0)
        cmap[code] = glyph_name

    builder = FontBuilder(profile.upem, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(cmap)
    builder.setupHorizontalMetrics(metrics)
    builder.glyphs = glyphs
    builder.setupGlyf(glyphs)
    ascent = profile.baseline + profile.cap_px * grid
    descent = profile.cap_px * grid - profile.baseline
    builder.setupHorizontalHeader(ascent=ascent, descent=-descent,
                                  lineGap=0)
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


def _fit_stem(rows, target_stem):
    """Штрих глифа приводится к толщине целевого шрифта."""
    stem = stem_width(rows)
    if stem is None or target_stem is None or stem == target_stem:
        return rows
    if stem > target_stem:
        return thin(rows)
    return thicken(rows)


def fit_descender(rows, base, depth_px):
    """Хвост глифа приводится к глубине выноса целевого шрифта.

    Вынос задаёт латиница цели: буквы вроде `p` уходят под базовую линию на
    свою глубину, и кириллическая `р` должна уходить так же. У гарнитуры
    источника своя глубина, и строки хвоста пересэмплируются под целевую.

    Если у цели выноса нет вовсе, хвост остаётся таким, как его нарисовала
    гарнитура: у `ц` и `щ` хвост это часть самой буквы, и без них они не
    отличить от `ш`.
    """
    last = None
    for y, row in enumerate(rows):
        if any(row):
            last = y
    if last is None or last < base or depth_px <= 0:
        return rows
    tail = rows[base:last + 1]
    if len(tail) == depth_px:
        return rows
    scaled = [tail[min(len(tail) - 1, y * len(tail) // depth_px)]
              for y in range(depth_px)]
    return rows[:base] + scaled


def _is_capital(char: str) -> bool:
    """Заглавная ли буква: у неё и высота другая, и кегль свой."""
    return char.isupper()


def _cyrillic_codepoints(play_path: str):
    """Весь кириллический блок гарнитуры."""
    font = load_font(play_path)
    return {code for code in font.getBestCmap() if 0x400 <= code <= 0x4FF}


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
