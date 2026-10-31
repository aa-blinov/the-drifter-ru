#!/usr/bin/env python
"""Install the Russian translation into a copy of The Drifter.

The game reads two things from its own directory:

  translation.csv — the text. The game's importer reads it, registers the
  language named in the last column of the header, and shows it in
  Options → Language.

  The fonts — the game draws the text with the fonts in its own assets, and
  none of them carries a Cyrillic glyph. The Cyrillic is written into the
  fonts that draw text, scaled to the x-height of the Latin in the same
  font, so that a Russian line has the same colour as an English one.

The assets file is patched byte by byte and never rebuilt: Unity's reader
loses the data of the objects it did not parse, and a file that lost 29 of
its 30 megabytes is a game that does not start. The patched file is read
back and compared with the original before it is put in place.

The game's files are the developer's. The installer reads a copy the user
owns and backs up everything it touches, so the original can be restored
without Steam.

    python3 scripts/install.py --game "C:/Program Files (x86)/Steam/steamapps/common/The Drifter"

    python3 scripts/install.py --game "..." --dry-run

Requires UnityPy and fonttools.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from patch_assets import patch_assets, verify  # noqa: E402

ROOT = os.path.dirname(HERE)
TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")
BACKUP_DIR = "_ru_backup"

# The fonts the game draws its text with. The other fonts of the game are
# for titles and icons, and the Cyrillic does not belong in them: a font with
# no lowercase letters has no x-height to match, and the scale that would
# follow from it produces a font the game cannot read.
GAME_FONTS = [
    "ChevyRay - Pinch - EU",
    "ChevyRay - Pinch - EU - AA",
    "CrawlTextBodyWide-EU",
    "CrawlSmall-EU",
    "tecno",
    "tecno_small",
    "embalm",
]


def game_paths(game_dir: str):
    data = os.path.join(game_dir, "TheDrifter_Data")
    return {
        "data": data,
        "assets": os.path.join(data, "sharedassets1.assets"),
        "translation": os.path.join(game_dir, "translation.csv"),
    }


def install_translation(paths, dry_run=False):
    """Copy the translation next to the executable.

    The file is written with CRLF whatever the working tree holds. The
    repository stores LF — that is what `.gitattributes` says — but the
    importer of the game reads CRLF, and a fresh clone would otherwise
    install a file the game cannot read.
    """
    target = paths["translation"]
    if not os.path.exists(TRANSLATION):
        raise SystemExit("translation not built: %s" % TRANSLATION)
    if dry_run:
        rows = sum(1 for _ in open(TRANSLATION, encoding="utf-8-sig")) - 1
        print("would write %s (%d rows)" % (target, rows))
        return target
    with open(TRANSLATION, encoding="utf-8-sig", newline="") as fh:
        text = fh.read()
    with open(target, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write(text.replace("\r\n", "\n").replace("\n", "\r\n"))
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


def install_fonts(paths, dry_run=False, mode="metric"):
    """Write the Cyrillic into the fonts of the game."""
    if dry_run:
        print("would patch %d fonts in %s" % (len(GAME_FONTS), paths["assets"]))
        return
    data, patched = patch_assets(paths["assets"], mode, set(GAME_FONTS))

    staged = paths["assets"] + ".new"
    with open(staged, "wb") as fh:
        fh.write(data)
    verify(staged, paths["assets"])
    os.replace(staged, paths["assets"])
    print("wrote %s (%d fonts)" % (paths["assets"], patched))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, help="the game's directory")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-fonts", action="store_true",
                        help="install the text only, leave the fonts alone")
    parser.add_argument("--mode", default="metric", choices=["metric", "grid"],
                        help="how the Cyrillic is scaled to the game font")
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
        install_fonts(paths, args.dry_run, args.mode)

    if args.dry_run:
        print("\ndry run: nothing was written")
    else:
        print("\ndone. Start the game and choose Русский in Options → Language.")


if __name__ == "__main__":
    main()
