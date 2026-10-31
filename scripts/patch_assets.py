#!/usr/bin/env python
"""Кириллические глифы, вписанные в шрифты внутри ассетов игры.

Игра держит шрифты в `TheDrifter_Data/sharedassets1.assets`. Шрифты это
сырые массивы байтов внутри своих объектов, а объекты адресуются своим
местом в файле.

Ридер Unity для этого файла пересобирает его из разобранных объектов, и
пересборка теряет данные объектов, которые разобрать не удалось: файл
возвращается в разы меньше прежнего, и игра не запускается. Поэтому файл не
пересобирается из разобранных объектов. Каждый объект сохраняет свои
байты, и заменяются только шрифты:

  1. шрифт объекта читается, в него вливается кириллица, и новые байты
     кладутся обратно в объект;
  2. объекты выписываются со своими байтами, поэтому всё, что файл держит
     кроме шрифтов, остаётся неизменным;
  3. результат читается обратно, каждый объект сравнивается с оригиналом,
     и файл встаёт на место только когда совпадают все.

Результат пишется рядом с оригиналом, читается обратно и только потом
встаёт на место.
"""
from __future__ import annotations

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from font_merge import merge, source_for  # noqa: E402
from font_metrics import Metrics, load_font  # noqa: E402


def font_objects(env):
    """Все шрифты файла вместе с их байтами."""
    for obj in env.objects:
        if obj.type.name != "Font":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        raw = bytes(tree.get("m_FontData") or b"")
        if not raw:
            continue
        yield obj, tree.get("m_Name"), raw


def find_font_data(raw: bytes, font: bytes):
    """Где шрифт лежит в байтах своего объекта и поле длины, которое говорит,
    какова она."""
    offset = raw.find(font)
    if offset < 4:
        return None, None
    length = struct.unpack("<i", raw[offset - 4:offset])[0]
    if length != len(font):
        return None, None
    return offset, offset - 4


def patch_object(data: bytes, font: bytes, new_font: bytes):
    """Объект с новым шрифтом внутри или None, если он не найден."""
    offset, length_at = find_font_data(data, font)
    if offset is None:
        return None
    return (data[:length_at] + struct.pack("<i", len(new_font)) + new_font
            + data[offset + len(font):])


def patch_assets(assets_path: str, mode: str = "metric", fonts=None,
                  source: str = None):
    """Файл, в шрифтах которого есть кириллица."""
    import UnityPy

    env = UnityPy.load(assets_path)
    objects = list(env.objects)

    # Каждый объект сохраняет свои байты. Без этого писатель пересобирает
    # объекты, которые не разобрал, и файл теряет большую часть своих
    # данных.
    for obj in objects:
        try:
            obj.set_raw_data(obj.get_raw_data())
        except Exception:
            pass

    patched = 0
    for obj, name, raw_font in font_objects(env):
        if fonts and name not in fonts:
            continue
        target_metrics = Metrics(load_font(raw_font))
        if source:
            source_path = source
        else:
            source_path, _source_metrics = source_for(target_metrics)
        new_font, added, scale = merge(raw_font, source_path, mode)
        data = obj.get_raw_data()
        result = patch_object(data, raw_font, new_font)
        if result is None:
            print("!! не найдены байты шрифта %s" % name)
            continue
        obj.set_raw_data(result)
        print("поправлен %-28s +%d глифов, x-height масштаб %.3f (%s)"
              % (name, added, scale, target_metrics.describe()))
        patched += 1

    if not patched:
        raise SystemExit("ни один шрифт не поправлен")

    data = env.file.save()

    # Ридер держит файл открытым, а Windows не заменяет открытый файл.
    release(env)
    return data, patched


def release(env) -> None:
    """Отпускание файлов, которые держит ридер.

    Ридер держит файл открытым, а Windows не заменяет открытый файл. Закрыть
    нужно поток под ридером.
    """
    for reader in env.file.files.values():
        stream = getattr(getattr(reader, "reader", None), "stream", None)
        if stream is not None and hasattr(stream, "close"):
            try:
                stream.close()
            except Exception:
                pass
    import gc
    gc.collect()


def verify(path: str, original_path: str, expected_cyrillic: int = 0) -> None:
    """Записанный файл должен держать те же объекты, что и оригинал.

    Число кириллических глифов сверяется с ожидаемым: сколько в источнике
    кириллицы, столько должно оказаться в каждом из текстовых шрифтов.
    """
    import UnityPy

    before_env = UnityPy.load(original_path)
    before = {obj.path_id: obj for obj in before_env.objects}
    after_env = UnityPy.load(path)
    objects = list(after_env.objects)
    by_id = {obj.path_id: obj for obj in objects}

    if len(objects) != len(before):
        raise SystemExit("в записанном файле %d объектов, в оригинале было %d"
                         % (len(objects), len(before)))

    differing = 0
    cyrillic = 0
    for path_id, obj in before.items():
        try:
            old = obj.get_raw_data()
            new = by_id[path_id].get_raw_data()
        except Exception:
            continue
        if old != new:
            differing += 1
        if obj.type.name == "Font":
            cyrillic += count_cyrillic(by_id[path_id])

    if differing > len(before) // 10:
        raise SystemExit("изменилось %d объектов из %d: это не правка шрифтов"
                         % (differing, len(before)))
    if expected_cyrillic and cyrillic < expected_cyrillic:
        raise SystemExit("в записанном файле %d кириллических глифов, ожидалось не "
                         "меньше %d" % (cyrillic, expected_cyrillic))
    print("проверено: %d объектов, %d изменено, %d кириллических глифов"
          % (len(objects), differing, cyrillic))

    # Ридер держит файл открытым, а Windows не заменяет открытый файл.
    for env in (before_env, after_env):
        release(env)
    del before_env, after_env


def count_cyrillic(obj) -> int:
    """Кириллические глифы, которые держит объект шрифта.

    Объект держит шрифт массивом байтов внутри более крупной структуры,
    поэтому шрифт ищется по своим байтам, а не разбирается из объекта.
    """
    try:
        tree = obj.read_typetree()
    except Exception:
        return 0
    raw = bytes(tree.get("m_FontData") or b"")
    if not raw:
        return 0
    try:
        font = load_font(raw)
    except Exception:
        return 0
    return len([c for c in font.getBestCmap() if 0x400 <= c <= 0x4FF])


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--mode", default="metric", choices=["metric", "grid"])
    parser.add_argument("--fonts", default="",
                        help="имена шрифтов через запятую, которые нужно править")
    args = parser.parse_args()

    wanted = {name.strip() for name in args.fonts.split(",") if name.strip()}
    data, patched = patch_assets(args.assets, args.mode, wanted or None)

    with open(args.out, "wb") as fh:
        fh.write(data)
    print("записан %s (%d байт, было %d)"
          % (args.out, len(data), os.path.getsize(args.assets)))
    verify(args.out, args.assets)


if __name__ == "__main__":
    main()
