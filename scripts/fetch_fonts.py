#!/usr/bin/env python
"""Скачивание гарнитуры, из которой собирается кириллица.

Play — не пиксельный шрифт, но из него scripts/make_pixel_font.py собирает
пиксельный: растр Play в кеглях 8, 10, 12 и 18 совпадает с высотой
строчных и заглавных шрифтов игры, и буквы ложатся на их сетку без
перерисовки. Шрифт распространяется по SIL Open Font License 1.1.

Файлы не лежат в репозитории: это несколько мегабайт, и они тянутся со
страницы проекта.

    python3 scripts/fetch_fonts.py
"""
from __future__ import annotations

import argparse
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "work", "fonts")

PLAY_URL = "https://github.com/google/fonts/raw/main/ofl/play/Play-Regular.ttf"
PLAY_BOLD_URL = "https://github.com/google/fonts/raw/main/ofl/play/Play-Bold.ttf"
PLAY_LICENSE = "https://github.com/google/fonts/raw/main/ofl/play/OFL.txt"


def fetch_play(target_dir: str):
    """Исходники для сборки пиксельного шрифта с русскими очертаниями.

    Нужны два начертания: у игры у шрифтов разная толщина штриха, и
    кириллица должна ей соответствовать.
    """
    os.makedirs(target_dir, exist_ok=True)
    for url, name in ((PLAY_URL, "Play-Regular.ttf"),
                      (PLAY_BOLD_URL, "Play-Bold.ttf"),
                      (PLAY_LICENSE, "OFL.txt")):
        path = os.path.join(target_dir, name)
        if os.path.exists(path):
            continue
        print("скачивание %s" % url)
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        with open(path, "wb") as dst:
            dst.write(data)
        print("  %s (%.1f KB)" % (name, len(data) / 1024))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=FONT_DIR)
    args = parser.parse_args()
    fetch_play(args.dir)
    print("\nшрифты: %s" % args.dir)


if __name__ == "__main__":
    main()
