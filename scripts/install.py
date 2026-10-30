#!/usr/bin/env python
"""Install the Russian translation into a copy of The Drifter.

The game reads two things from its own directory:

  translation.csv — the text. The game's importer reads it, registers the
  language and shows it in Options → Language.

  The fonts — the game draws the text with its own fonts, and those fonts
  carry no Cyrillic. The Russian text needs a font that does, so the
  installer writes the merged fonts back into sharedassets1.assets.

The game's files are the developer's. The installer reads a copy the user
owns and backs up everything it touches, so the original can be restored
without Steam.

    python3 scripts/install.py --game "C:/Program Files (x86)/Steam/steamapps/common/The Drifter"

    python3 scripts/install.py --game "..." --dry-run

Requires UnityPy and fonttools.
"""
from __future__ import annotations

import argparse
import io
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")
BACKUP_DIR = "_ru_backup"

# The fonts the game draws its text with. The pixel size of each one is
# measured on the font itself, so this list only names them.
GAME_FONTS = {
    "ChevyRay - Pinch - EU",
    "ChevyRay - Pinch - EU - AA",
    "CrawlTextBodyWide-EU",
    "CrawlSmall-EU",
    "tecno_small",
    "tecno",
    "embalm",
}

# The source of the Cyrillic glyphs: a pixel font that carries the whole
# Cyrillic range at the sizes the game draws its text at. The file is picked
# by the pixel size measured on the game font.
CYRILLIC_SOURCES = {
    10: "ark-pixel-10px-proportional-latin.ttf",
    12: "ark-pixel-12px-proportional-latin.ttf",
}

FONT_DIR = os.path.join(ROOT, "work", "fonts")


def game_paths(game_dir: str):
    data = os.path.join(game_dir, "TheDrifter_Data")
    return {
        "data": data,
        "assets": os.path.join(data, "sharedassets1.assets"),
        "translation": os.path.join(game_dir, "translation.csv"),
    }


def install_translation(paths, dry_run=False):
    """Copy the translation next to the executable."""
    target = paths["translation"]
    if not os.path.exists(TRANSLATION):
        raise SystemExit("translation not built: %s" % TRANSLATION)
    if dry_run:
        rows = sum(1 for _ in io.open(TRANSLATION, encoding="utf-8-sig")) - 1
        print("would write %s (%d rows)" % (target, rows))
        return target
    shutil.copy2(TRANSLATION, target)
    print("installed %s" % target)
    return target


def backup(paths, game_dir):
    """Keep the original assets, so the patch can be undone."""
    backup_dir = os.path.join(game_dir, BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)
    source = paths["assets"]
    if os.path.exists(source):
        target = os.path.join(backup_dir, os.path.basename(source))
        if not os.path.exists(target):
            shutil.copy2(source, target)
            print("backed up %s" % os.path.basename(source))
    return backup_dir


def merge_fonts(paths, dry_run=False):
    """Write the Cyrillic glyphs into the game's fonts."""
    import UnityPy

    if not os.path.exists(paths["assets"]):
        raise SystemExit("not found: %s" % paths["assets"])

    sources = {}
    for size, name in CYRILLIC_SOURCES.items():
        path = os.path.join(FONT_DIR, name)
        if not os.path.exists(path):
            raise SystemExit(
                "font not found: %s\n"
                "Run scripts/fetch_fonts.py to download the pixel fonts." % path)
        sources[size] = path

    env = UnityPy.load(paths["assets"])
    swapped = 0
    for obj in env.objects:
        if obj.type.name != "Font":
            continue
        data = obj.read()
        name = data.m_Name
        if name not in GAME_FONTS:
            continue
        original = obj.read_typetree()
        raw = bytes(original["m_FontData"])
        if not raw:
            continue

        # The pixel size of the font is measured on the font itself: the
        # source has to be drawn at the same size, or the merged glyphs land
        # between the pixels of the game.
        from fontTools.ttLib import TTFont
        measured = TTFont(io.BytesIO(raw))
        px = design_pixels(measured)
        if px not in sources:
            print("  !! %s is drawn at %d px, and there is no source for that size"
                  % (name, px))
            continue
        merged = merge_one(raw, sources[px])
        if dry_run:
            print("would merge %-28s %d -> %d bytes (drawn at %d px)"
                  % (name, len(raw), len(merged), px))
            swapped += 1
            continue
        original["m_FontData"] = list(merged)
        obj.save_typetree(original)
        print("merged %-28s %d -> %d bytes (drawn at %d px)"
              % (name, len(raw), len(merged), px))
        swapped += 1

    if swapped == 0:
        raise SystemExit("no game font was found in %s" % paths["assets"])

    if dry_run:
        return
    with open(paths["assets"], "wb") as fh:
        fh.write(env.file.save())
    print("wrote %s" % paths["assets"])


def pixel_grid(font):
    """The unit in which a pixel font draws: the greatest common divisor of
    the coordinates of its glyphs.

    A pixel font has no coordinate off its own grid, so the gcd of the
    coordinates is the size of one pixel in font units. The number of pixels
    the em covers follows from it.
    """
    from math import gcd

    glyf = font["glyf"]
    grid = 0
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        try:
            coordinates, _end, _flags = glyph.getCoordinates(glyf)
        except Exception:
            continue
        for x, _y in coordinates:
            grid = gcd(grid, abs(int(x)))
    return grid


def design_pixels(font) -> int:
    """The pixel size a font is drawn at: the pixels its em covers."""
    grid = pixel_grid(font)
    if not grid:
        return 0
    return int(round(font["head"].unitsPerEm / grid))


def merge_one(original: bytes, source_path: str) -> bytes:
    """Add the Cyrillic glyphs of the pixel font to one game font.

    The source is scaled to the em of the target, so that the merged glyphs
    are drawn at the size of the glyphs that were already there: the
    renderer scales by the font size over the em, and both have to agree.

    The source has to be drawn at the same pixel size as the target, so that
    one pixel of the source lands on one pixel of the target. The caller
    picks the source by that size, and the size is measured on the target
    rather than assumed.
    """
    from fontTools import subset
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.scaleUpem import scale_upem

    target = TTFont(io.BytesIO(original))
    source = TTFont(source_path)

    wanted = {codepoint for codepoint in source.getBestCmap()
              if 0x0400 <= codepoint <= 0x04FF}
    wanted |= {ord(ch) for ch in "«»—…№"}

    options = subset.Options()
    options.glyph_names = True
    options.notdef_outline = True
    options.recalc_bounds = True
    options.drop_tables += ["GSUB", "GPOS", "GDEF", "BASE", "DSIG", "kern"]
    options.layout_features = []
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=sorted(wanted))
    subsetter.subset(source)

    target_upem = target["head"].unitsPerEm
    scale_upem(source, target_upem)

    target_cmap = target.getBestCmap()
    source_cmap = source.getBestCmap()
    source_glyphs = source.getGlyphSet()
    source_hmtx = source["hmtx"]
    target_glyphs = target["glyf"]
    target_hmtx = target["hmtx"]
    target_cmap_table = target["cmap"]
    order = list(target.getGlyphOrder())
    existing = set(order)

    for codepoint in sorted(wanted):
        if codepoint in target_cmap:
            continue
        source_name = source_cmap.get(codepoint)
        if not source_name:
            continue
        glyph_name = "ru%04X" % codepoint
        if glyph_name in existing:
            continue
        pen = DecomposingRecordingPen(source_glyphs)
        source_glyphs[source_name].draw(pen)
        out = TTGlyphPen(None)
        pen.replay(out)
        target_glyphs.glyphs[glyph_name] = out.glyph()
        advance, lsb = source_hmtx[source_name]
        target_hmtx.metrics[glyph_name] = (int(round(advance)), int(round(lsb)))
        order.append(glyph_name)
        existing.add(glyph_name)

        # A glyph the font cannot map a character to does not exist for the
        # renderer. Every unicode subtable of the cmap gets the new entry.
        for subtable in target_cmap_table.tables:
            if subtable.isUnicode():
                subtable.cmap[codepoint] = glyph_name

    # The glyf table keeps its own order of the glyphs, and it has to be the
    # same order as the font's: a font whose two orders disagree does not
    # compile.
    target_glyphs.glyphOrder = order
    target.setGlyphOrder(order)

    buffer = io.BytesIO()
    target.save(buffer)
    return buffer.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, help="the game's directory")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-fonts", action="store_true",
                        help="install the text only, leave the fonts alone")
    args = parser.parse_args()

    game_dir = os.path.abspath(args.game)
    if not os.path.exists(os.path.join(game_dir, "TheDrifter.exe")):
        raise SystemExit("not a copy of The Drifter: %s" % game_dir)

    paths = game_paths(game_dir)
    print("game: %s" % game_dir)

    if not args.dry_run:
        backup(paths, game_dir)
    install_translation(paths, args.dry_run)
    if not args.no_fonts:
        merge_fonts(paths, args.dry_run)

    if args.dry_run:
        print("\ndry run: nothing was written")
    else:
        print("\ndone. Start the game and choose Русский in Options → Language.")


if __name__ == "__main__":
    main()
