#!/usr/bin/env python
"""Download the pixel fonts the Cyrillic glyphs are taken from.

Ark Pixel Font carries the whole Cyrillic range at 10 px and 12 px, which
are the sizes the game draws its dialogue and its interface at. The font is
under the SIL Open Font License 1.1.

The files are not committed: they are a few megabytes, and they are fetched
from the project's release page.

    python3 scripts/fetch_fonts.py
"""
from __future__ import annotations

import argparse
import io
import os
import shutil
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "work", "fonts")

RELEASE = "https://github.com/TakWolf/ark-pixel-font/releases/download"
VERSION = "2026.10.25"

PACKAGES = {
    10: "ark-pixel-font-10px-proportional-ttf-v%s.zip" % VERSION,
    12: "ark-pixel-font-12px-proportional-ttf-v%s.zip" % VERSION,
}
WANTED = {10: "ark-pixel-10px-proportional-latin.ttf",
          12: "ark-pixel-12px-proportional-latin.ttf"}


def fetch(size: int, name: str, target_dir: str):
    url = "%s/%s/%s" % (RELEASE, VERSION, name)
    print("downloading %s" % url)
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read()
    archive = zipfile.ZipFile(io.BytesIO(data))
    wanted = WANTED[size]
    if wanted not in archive.namelist():
        raise SystemExit("%s not in %s" % (wanted, name))
    os.makedirs(target_dir, exist_ok=True)
    with archive.open(wanted) as src, open(os.path.join(target_dir, wanted), "wb") as dst:
        shutil.copyfileobj(src, dst)
    license_path = os.path.join(target_dir, "OFL.txt")
    if "OFL.txt" in archive.namelist() and not os.path.exists(license_path):
        with archive.open("OFL.txt") as src, open(license_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
    print("  %s (%.1f KB)" % (wanted, os.path.getsize(
        os.path.join(target_dir, wanted)) / 1024))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=FONT_DIR)
    args = parser.parse_args()
    for size, name in PACKAGES.items():
        fetch(size, name, args.dir)
    print("\nfonts: %s" % args.dir)


if __name__ == "__main__":
    main()
