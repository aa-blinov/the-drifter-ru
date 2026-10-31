#!/usr/bin/env python
"""Установка русского перевода в копию The Drifter.

Игра читает из своего каталога две вещи:

  translation.csv, то есть текст. Импортёр игры читает его, регистрирует
  язык, названный в последней колонке заголовка, и показывает его в
  Options → Language.

  Шрифты. Игра рисует текст шрифтами из своих собственных ассетов, и ни
  один из них не несёт кириллического глифа. Кириллица вписывается в
  шрифты, которыми рисуется текст, и масштабируется под x-height латиницы
  в том же шрифте, поэтому русская строка имеет тот же цвет, что
  английская.

Файл ассетов правится байт за байтом и никогда не пересобирается: ридер
Unity теряет данные объектов, которые не разобрал, а файл, потерявший 29
из своих 30 мегабайт, это игра, которая не запустится. Правленый файл
читается обратно и сравнивается с оригиналом до того, как встать на место.

Файлы игры принадлежат разработчику. Установщик работает с копией, которой
владеет пользователь, и копирует всё, к чему прикасается, поэтому
оригинал можно вернуть без Steam.

    python3 scripts/install.py --game "C:/Program Files (x86)/Steam/steamapps/common/The Drifter"

    python3 scripts/install.py --game "..." --dry-run

Нужны UnityPy и fonttools.
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
# Лицензия шрифта, из которого берётся кириллица. Шрифт вписывается в
# шрифты игры, поэтому распространение такой сборки требует, чтобы лицензия
# лежала рядом с файлом.
FONT_LICENSE = os.path.join(ROOT, "work", "fonts", "OFL.txt")

# Шрифты, которыми игра рисует текст. Остальные шрифты игры идут на
# заголовки и значки, и кириллица им не нужна: у шрифта без строчных
# букв нет x-height, под который можно подстроиться, и масштаб, который
# из этого получится, даёт шрифт, который игра не читает.
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
    """Копирование перевода рядом с исполняемым файлом.

    Файл пишется с CRLF независимо от того, что лежит в рабочем дереве.
    Репозиторий хранит LF, это сказано в `.gitattributes`, но импортёр игры
    читает CRLF, и свежая копия иначе поставила бы файл, который игра не
    читает.
    """
    target = paths["translation"]
    if not os.path.exists(TRANSLATION):
        raise SystemExit("перевод не собран: %s" % TRANSLATION)
    if dry_run:
        rows = sum(1 for _ in open(TRANSLATION, encoding="utf-8-sig")) - 1
        print("будет записан %s (%d строк)" % (target, rows))
        return target
    with open(TRANSLATION, encoding="utf-8-sig", newline="") as fh:
        text = fh.read()
    with open(target, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write(text.replace("\r\n", "\n").replace("\n", "\r\n"))
    print("установлен %s" % target)
    return target


def backup(paths, game_dir):
    """Сохранение оригинальных ассетов, чтобы правку можно было отменить."""
    backup_dir = os.path.join(game_dir, BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)
    source = paths["assets"]
    if os.path.exists(source):
        target = os.path.join(backup_dir, os.path.basename(source))
        if not os.path.exists(target):
            shutil.copy2(source, target)
            print("сохранена копия %s" % os.path.basename(source))
    return backup_dir


def install_font_license(paths):
    """Копирование лицензии шрифта рядом с игрой.

    Шрифт игры после патча несёт кириллицу Ark Pixel, а та распространяется
    по SIL Open Font License 1.1: лицензия должна идти вместе с файлом.
    """
    if not os.path.exists(FONT_LICENSE):
        return None
    target = os.path.join(paths["data"], "ArkPixelFont-OFL.txt")
    shutil.copy2(FONT_LICENSE, target)
    return target


def install_fonts(paths, dry_run=False, mode="metric", source=None, bold=0):
    """Вписывание кириллицы в шрифты игры."""
    if dry_run:
        print("будут правиться %d шрифтов в %s" % (len(GAME_FONTS), paths["assets"]))
        return
    expected_cyrillic = 0
    if source:
        from font_metrics import load_font
        cmap = load_font(source).getBestCmap()
        expected_cyrillic = len([c for c in cmap if 0x0400 <= c <= 0x04FF]) * len(GAME_FONTS)
    data, patched = patch_assets(paths["assets"], mode, set(GAME_FONTS), source,
                                bold)

    staged = paths["assets"] + ".new"
    with open(staged, "wb") as fh:
        fh.write(data)
    verify(staged, paths["assets"], expected_cyrillic)
    os.replace(staged, paths["assets"])
    print("записан %s (%d шрифтов)" % (paths["assets"], patched))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, help="каталог игры")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-fonts", action="store_true",
                        help="поставить только текст, шрифты не трогать")
    parser.add_argument("--mode", default="cap", choices=["metric", "grid", "cap"],
                        help="как кириллица масштабируется под шрифт игры: "
                             "cap — по высоте заглавных (по умолчанию), "
                             "metric — по высоте строчных, grid — по сетке")
    parser.add_argument("--bold", type=int, default=0,
                        help="насколько утолщить кириллицу, в единицах "
                             "шрифта игры: 25 — как в игре, 50 — заметно")
    parser.add_argument("--source", default=None,
                        help="шрифт, из которого берётся кириллица (по умолчанию "
                             "подбирается по шрифту игры)")
    args = parser.parse_args()

    game_dir = os.path.abspath(args.game)
    if not os.path.exists(os.path.join(game_dir, "TheDrifter.exe")):
        raise SystemExit("это не копия The Drifter: %s" % game_dir)

    paths = game_paths(game_dir)
    print("игра: %s" % game_dir)

    if not args.dry_run:
        backup(paths, game_dir)
    install_translation(paths, args.dry_run)
    if not args.no_fonts:
        install_fonts(paths, args.dry_run, args.mode, args.source, args.bold)
        license_path = install_font_license(paths)
        if license_path:
            print("лицензия шрифта: %s" % license_path)

    if args.dry_run:
        print("\nпробный запуск: ничего не записано")
    else:
        print("\nготово. Запустите игру и выберите Русский в Options → Language.")


if __name__ == "__main__":
    main()
