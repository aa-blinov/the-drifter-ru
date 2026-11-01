#!/usr/bin/env python
"""Установка русского перевода в копию The Drifter.

Игра читает из своего каталога две вещи:

  translation.csv, то есть текст. Импортёр игры читает его, регистрирует
  язык, названный в последней колонке заголовка, и показывает его в
  Options → Language.

  Шрифты. Игра рисует текст шрифтами из своих собственных ассетов, и ни
  один из них не несёт кириллического глифа. Кириллица вписывается в
  шрифты, которыми рисуется текст, и подгоняется под профиль каждого из
  них: кириллица встаёт на базовую линию латиницы ровно, имеет ту же
  высоту строчных и заглавных и тот же вынос, поэтому русская строка
  выглядит как строка игры.

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

from font_metrics import load_font  # noqa: E402
import font_source  # noqa: E402
from patch_assets import patch_assets, verify  # noqa: E402

ROOT = os.path.dirname(HERE)
TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")
BACKUP_DIR = "_ru_backup"
# Лицензия шрифта, из которого берётся кириллица. Шрифт вписывается в
# шрифты игры, поэтому распространение такой сборки требует, чтобы лицензия
# лежала рядом с файлом.
FONT_LICENSE = os.path.join(ROOT, "work", "fonts", "OFL.txt")
ARK_LICENSE = os.path.join(ROOT, "work", "fonts", "ArkPixel-OFL.txt")

# Шрифты, которыми игра рисует перевод. Это те, что стоят у надписей со
# строками перевода: у пиксельных шрифтов кириллица ложится на их сетку,
# у гладких собирается из контуров под их высоты. Остальные шрифты игры
# идут на заголовки и значки, где перевода нет.
GAME_FONTS = [
    "ChevyRay - Pinch - EU",
    "ChevyRay - Pinch - EU - AA",
    "CrawlTextBodyWide-EU",
    "CrawlSmall-EU",
    "tecno",
    "tecno_small",
    "embalm",
    "Army of Darkness Regular",
    "CarroisGothic-Regular-HD",
    "CarroisGothic-Regular",
    "Serif Gothic Bold",
    "DrifterGothic13",
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


def base_assets(paths, game_dir):
    """Файл, от которого идёт правка.

    Правка идёт от оригинала, а не от уже пропатченного файла: вписанная
    кириллица с чужой сеткой разрушает пиксельную сетку шрифта, и по
    пропатченному файлу профиль шрифта уже не определить. Копия оригинала
    лежит в каталоге `_ru_backup`.
    """
    backup_dir = os.path.join(game_dir, BACKUP_DIR)
    target = os.path.join(backup_dir, os.path.basename(paths["assets"]))
    if os.path.exists(target) and not count_cyrillic_in(target):
        return target
    return paths["assets"]


def count_cyrillic_in(assets_path):
    """Есть ли в файле кириллица: признак того, что он уже пропатчен."""
    import UnityPy
    from patch_assets import font_objects

    env = UnityPy.load(assets_path)
    total = 0
    for _obj, _name, raw in font_objects(env):
        cmap = load_font(raw).getBestCmap()
        total += len([c for c in cmap if 0x0400 <= c <= 0x04FF])
    return total


def install_font_license(paths):
    """Копирование лицензии шрифта рядом с игрой.

    Шрифт игры после патча несёт кириллицу, нарисованную из гарнитуры Play,
    а та распространяется по SIL Open Font License 1.1: лицензия должна идти
    вместе с файлом.
    """
    copied = []
    for source, filename in ((FONT_LICENSE, "PlayFont-OFL.txt"),
                             (ARK_LICENSE, "ArkPixel-OFL.txt")):
        if os.path.exists(source):
            target = os.path.join(paths["data"], filename)
            shutil.copy2(source, target)
            copied.append(target)
    return copied


PLAY_DIR = os.path.join(ROOT, "work", "fonts")


def install_fonts(paths, dry_run=False, mode="grid", source=None, bold=0,
                  narrow=1.0, game_dir=None, size=1.0):
    """Вписывание кириллицы в шрифты игры.

    Источник собирается под профиль каждого шрифта: у игры у шрифтов разные
    сетки, высоты строчных и заглавных, и кириллица, нарисованная под один
    из них, в другом легла бы мимо сетки.
    """
    if source is None:
        for name in ("Play-Regular.ttf", "Play-Bold.ttf",
                     "ArkPixel-10px-Proportional-Latin.ttf",
                     "ArkPixel-12px-Proportional-Latin.ttf"):
            if not os.path.exists(os.path.join(PLAY_DIR, name)):
                raise SystemExit(
                    "нет гарнитуры %s в %s\n"
                    "Запустите scripts/fetch_fonts.py, чтобы скачать шрифты."
                    % (name, PLAY_DIR))
    if dry_run:
        print("будут правиться %d шрифтов в %s"
              % (len(GAME_FONTS), paths["assets"]))
        return
    source_path = base_assets(paths, game_dir) if game_dir else paths["assets"]
    data, patched, expected = patch_assets(source_path, mode,
                                          set(GAME_FONTS), source, bold, narrow,
                                          size)

    staged = paths["assets"] + ".new"
    with open(staged, "wb") as fh:
        fh.write(data)
    verify(staged, paths["assets"], expected)
    os.replace(staged, paths["assets"])
    print("записан %s (%d шрифтов)" % (paths["assets"], patched))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, help="каталог игры")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-fonts", action="store_true",
                        help="поставить только текст, шрифты не трогать")
    parser.add_argument("--mode", default="grid", choices=["metric", "grid", "cap"],
                        help="как кириллица масштабируется под шрифт игры, "
                             "когда источник задан явно: grid — по "
                             "пиксельной сетке, metric — по высоте строчных, "
                             "cap — по высоте заглавных. По умолчанию "
                             "источник собирается под профиль шрифта, и "
                             "масштаб равен единице")
    parser.add_argument("--narrow", type=float, default=1.0,
                        help="сжатие кириллицы по горизонтали: 0.85 — "
                             "заметно уже, 0.95 — чуть-чуть")
    parser.add_argument("--size", type=float, default=font_source.DEFAULT_SIZE,
                        help="размер кириллицы против латиницы: 1.0 — "
                             "вровень с латиницей, 0.95 — чуть меньше, "
                             "0.9 — заметно меньше. Кириллица остаётся на "
                             "базовой линии, она просто ниже")
    parser.add_argument("--bold", type=int, default=0,
                        help="насколько утолщить кириллицу, в единицах "
                             "шрифта игры: 25 — как в игре, 50 — заметно")
    parser.add_argument("--source", default=None,
                        help="шрифт, из которого берётся кириллица, вместо "
                             "собранного под профиль цели")
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
        install_fonts(paths, args.dry_run, args.mode, args.source, args.bold,
                      args.narrow, game_dir, args.size)
        license_paths = [] if args.dry_run else install_font_license(paths)
        if license_paths:
            for license_path in license_paths:
                print("лицензия шрифта: %s" % license_path)

    if args.dry_run:
        print("\nпробный запуск: ничего не записано")
    else:
        print("\nготово. Запустите игру и выберите Русский в Options → Language.")


if __name__ == "__main__":
    main()
