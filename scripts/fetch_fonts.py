#!/usr/bin/env python
"""Скачивание исходных гарнитур для кириллических глифов.

Ark Pixel используется как источник пиксельных глифов, Play — как источник
для гладких шрифтов игры. Обе гарнитуры распространяются по SIL OFL 1.1.

Файлы не лежат в репозитории: это несколько мегабайт, и они тянутся со
страницы проекта.

    python3 scripts/fetch_fonts.py
"""
from __future__ import annotations

import argparse
import io
import os
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "work", "fonts")

PLAY_URL = "https://github.com/google/fonts/raw/main/ofl/play/Play-Regular.ttf"
PLAY_BOLD_URL = "https://github.com/google/fonts/raw/main/ofl/play/Play-Bold.ttf"
PLAY_LICENSE = "https://github.com/google/fonts/raw/main/ofl/play/OFL.txt"
ARK_RELEASE = "2026.10.25"
ARK_PIXEL_10_URL = (
    "https://github.com/TakWolf/ark-pixel-font/releases/download/"
    + ARK_RELEASE + "/ark-pixel-font-10px-proportional-ttf-v"
    + ARK_RELEASE + ".zip")
ARK_PIXEL_12_URL = (
    "https://github.com/TakWolf/ark-pixel-font/releases/download/"
    + ARK_RELEASE + "/ark-pixel-font-12px-proportional-ttf-v"
    + ARK_RELEASE + ".zip")
ARK_LICENSE = (
    "https://raw.githubusercontent.com/TakWolf/ark-pixel-font/"
    + ARK_RELEASE + "/LICENSE-OFL")


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


def fetch_ark_pixel(target_dir: str):
    """Исходники пиксельной кириллицы для восьми пиксельных шрифтов игры."""
    os.makedirs(target_dir, exist_ok=True)
    fonts = ((ARK_PIXEL_10_URL, "ark-pixel-10px-proportional-latin.ttf",
              "ArkPixel-10px-Proportional-Latin.ttf"),
             (ARK_PIXEL_12_URL, "ark-pixel-12px-proportional-latin.ttf",
              "ArkPixel-12px-Proportional-Latin.ttf"))
    for url, member, name in fonts:
        path = os.path.join(target_dir, name)
        if os.path.exists(path):
            continue
        print("скачивание %s" % url)
        with urllib.request.urlopen(url, timeout=120) as response:
            archive = response.read()
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            matches = [item for item in bundle.namelist()
                       if item.endswith("/" + member) or item == member]
            if len(matches) != 1:
                raise SystemExit("в архиве %s ожидался один файл %s"
                                 % (url, member))
            data = bundle.read(matches[0])
        with open(path, "wb") as dst:
            dst.write(data)
        print("  %s (%.1f KB)" % (name, len(data) / 1024))

    license_path = os.path.join(target_dir, "ArkPixel-OFL.txt")
    if not os.path.exists(license_path):
        print("скачивание %s" % ARK_LICENSE)
        with urllib.request.urlopen(ARK_LICENSE, timeout=120) as response:
            data = response.read()
        with open(license_path, "wb") as dst:
            dst.write(data)
        print("  ArkPixel-OFL.txt (%.1f KB)" % (len(data) / 1024))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=FONT_DIR)
    args = parser.parse_args()
    fetch_play(args.dir)
    fetch_ark_pixel(args.dir)
    print("\nшрифты: %s" % args.dir)


if __name__ == "__main__":
    main()
