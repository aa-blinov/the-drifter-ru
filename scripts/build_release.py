#!/usr/bin/env python
"""Архив установки: перевод, установщик и всё, что ему нужно.

    python3 scripts/build_release.py 1.0.0

Архив кладётся в dist/the-drifter-ru-vX.Y.Z.zip. В него входит только то, что
нужно игроку; пайплайн, корпус и рабочие файлы остаются в репозитории.
"""
from __future__ import annotations

import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Список явный: скрипты проверки и аудита игроку не нужны, а новый файл в
# scripts/ не должен попадать в релиз без решения.
FILES = [
    ("translation/Russian/translation.csv", "translation/Russian/translation.csv"),
    ("scripts/install.py", "scripts/install.py"),
    ("scripts/patch_assets.py", "scripts/patch_assets.py"),
    ("scripts/font_merge.py", "scripts/font_merge.py"),
    ("scripts/font_metrics.py", "scripts/font_metrics.py"),
    ("scripts/font_source.py", "scripts/font_source.py"),
    ("scripts/make_pixel_font.py", "scripts/make_pixel_font.py"),
    ("scripts/make_smooth_font.py", "scripts/make_smooth_font.py"),
    ("scripts/make_ui_pixel_font.py", "scripts/make_ui_pixel_font.py"),
    ("scripts/fetch_fonts.py", "scripts/fetch_fonts.py"),
    ("requirements.txt", "requirements.txt"),
    ("LICENSE", "LICENSE"),
    ("packaging/install.bat", "install.bat"),
    ("packaging/INSTALL.txt", "INSTALL.txt"),
]


def build(version: str, out_dir: str = None) -> str:
    out_dir = out_dir or os.path.join(ROOT, "dist")
    missing = [src for src, _ in FILES if not os.path.isfile(os.path.join(ROOT, src))]
    if missing:
        raise SystemExit("нет файлов для архива: %s" % ", ".join(missing))
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, "the-drifter-ru-v%s.zip" % version)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for src, name in FILES:
            path = os.path.join(ROOT, src)
            if name.endswith((".bat", ".txt")):
                # cmd.exe читает пакетный файл только с CRLF; git может
                # привести файл к LF, поэтому окончания ставятся здесь.
                with open(path, "rb") as fh:
                    data = fh.read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                archive.writestr(name, data)
            else:
                archive.write(path, name)
    return target


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_release.py X.Y.Z")
    target = build(sys.argv[1].lstrip("v"))
    with zipfile.ZipFile(target) as archive:
        for info in archive.infolist():
            print("%8d  %s" % (info.file_size, info.filename))
    print("собран %s (%.0f KB)" % (target, os.path.getsize(target) / 1024))


if __name__ == "__main__":
    main()
