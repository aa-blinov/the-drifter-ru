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

from font_merge import merge  # noqa: E402
from font_metrics import Metrics, load_font  # noqa: E402
import font_source  # noqa: E402

# Каталог с гарнитурами, из которых собирается кириллица, и каталог, куда
# кладутся собранные источники. Источник нужен свой для каждого профиля
# шрифта, поэтому он и собирается, и хранится отдельно от шрифтов игры.
PLAY_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "work", "fonts")
SOURCE_CACHE = os.path.join(PLAY_DIR, "cyr")


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
    # После данных шрифта в объекте Unity идёт выравнивание до четырёх
    # байт, и его длина зависит от длины данных. Новый шрифт другой длины,
    # и без правки выравнивания следующее поле читается со сдвигом, а
    # объект не разбирается вовсе.
    old_pad = (-len(font)) % 4
    new_pad = (-len(new_font)) % 4
    padding = (data[offset + len(font):offset + len(font) + old_pad]
               + b"\x00" * 4)[:new_pad]
    return (data[:length_at] + struct.pack("<i", len(new_font)) + new_font
            + padding + data[offset + len(font) + old_pad:])


# Гладкие шрифты интерфейса: меню и подписи реплик. С --pixel-ui они
# заменяются пиксельным шрифтом целиком, а не получают гладкую кириллицу.
UI_PIXEL_FONTS = {"CarroisGothic-Regular-HD", "CarroisGothic-Regular"}


# FontRenderingMode Unity: 0 гладкий, 1 гладкий с хинтингом, 2 хинтованный растр
# без сглаживания. Пиксельный шрифт в растре сохраняет острые края.
RASTER_MODE = 2


def set_rendering_mode(data: bytes, mode: int) -> bytes:
    """Байты объекта шрифта с другим режимом отрисовки.

    Объект Font кончается полями `m_FontRenderingMode` (int) и двумя bool:
    `m_UseLegacyBoundsCalculation` и `m_ShouldRoundAdvanceValue`. Поле стоит
    после данных шрифта, поэтому его место считается от конца объекта и не
    зависит от длины шрифта. Сериализатор UnityPy поле не пишет, поэтому
    правка идёт по байтам; перед ней проверяется, что на этом месте лежит
    режим 0..3, а за ним два bool.
    """
    old = struct.unpack("<i", data[-6:-2])[0]
    if not 0 <= old <= 3 or data[-2] > 1 or data[-1] > 1:
        raise SystemExit("конец объекта шрифта не похож на режим отрисовки")
    return data[:-6] + struct.pack("<i", mode) + data[-2:]


def patch_assets(assets_path: str, mode: str = "grid", fonts=None,
                 source: str = None, bold: int = 0, narrow: float = 1.0,
                 size: float = 1.0, pixel_ui: bool = False,
                 raster: bool = True):
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
    expected = {}
    found = set()
    for obj, name, raw_font in font_objects(env):
        if fonts and name not in fonts:
            continue
        found.add(name)
        target_metrics = Metrics(load_font(raw_font))
        if pixel_ui and name in UI_PIXEL_FONTS:
            import make_ui_pixel_font
            new_font = make_ui_pixel_font.build(raw_font, PLAY_DIR)
            result = patch_object(obj.get_raw_data(), raw_font, new_font)
            if result is None:
                print("!! не найдены байты шрифта %s" % name)
                continue
            if raster:
                result = set_rendering_mode(result, RASTER_MODE)
            obj.set_raw_data(result)
            cmap = load_font(new_font).getBestCmap()
            expected[name] = len([c for c in cmap if 0x0400 <= c <= 0x04FF])
            print("заменён %-26s пиксельным шрифтом, %d знаков"
                  % (name, len(cmap)))
            patched += 1
            continue
        if source:
            # Чужой источник подгоняется под цель выбранным способом.
            source_path = source
            merge_mode = mode
        else:
            # Источник собирается под профиль этого шрифта: его сетка,
            # высота строчных и высота заглавных совпадают с целевыми, и
            # кириллица встаёт на сетку латиницы без перерисовки. У гладкого
            # шрифта сетки нет, и там источник собирается из контуров.
            source_path = font_source.source_for(
                raw_font, PLAY_DIR, SOURCE_CACHE,
                use_ark=bool(fonts and name in fonts))
            merge_mode = "same"
        new_font, added, scale = merge(raw_font, source_path, merge_mode, bold,
                                       narrow, size)
        data = obj.get_raw_data()
        result = patch_object(data, raw_font, new_font)
        if result is None:
            print("!! не найдены байты шрифта %s" % name)
            continue
        obj.set_raw_data(result)
        print("правлен %-28s +%d глифов, масштаб %.3f (%s)"
              % (name, added, scale, target_metrics.describe()))
        patched += 1
        # Ожидаемое число считается по источнику: кириллицы в нём столько,
        # сколько должно оказаться в шрифте игры. Глифы, уже лежавшие в
        # цели, в счёт не идут.
        source_cmap = load_font(source_path).getBestCmap()
        target_cmap = load_font(raw_font).getBestCmap()
        expected[name] = len([c for c in source_cmap
                               if 0x0400 <= c <= 0x04FF
                               and c not in target_cmap])

    if not patched:
        raise SystemExit("ни один шрифт не поправлен")

    # Шрифт из списка правки, которого в ассетах нет, это молчаливая
    # поломка: строка перевода уйдёт в системный шрифт, и игра это не
    # покажет.
    missing = sorted(set(fonts or ()) - found)
    if missing:
        raise SystemExit("в ассетах нет шрифтов: %s" % ", ".join(missing))

    if fonts:
        data = save_selected_objects(env.file, expected)
    else:
        data = env.file.save()

    # Ридер держит файл открытым, а Windows не заменяет открытый файл.
    release(env)
    return data, patched, expected


def save_selected_objects(serialized, expected):
    """Пересобрать только таблицу смещений, оставив прочие объекты как есть.

    UnityPy сериализует все объекты класса Font, даже если изменили только
    несколько. Для версии файла 22 сохраняем исходные записи метаданных и
    переносим неизменённые байты объектов без участия сериализатора.
    """
    from UnityPy.streams import EndianBinaryWriter

    reader = serialized.reader
    header = serialized.header
    source_reader = reader
    old_position = source_reader.Position
    source_reader.Position = 0
    source_data = source_reader.read(header.file_size)
    source_reader.Position = old_position
    if header.version != 22:
        raise SystemExit("побайтная запись выбранных объектов поддерживает "
                         "только SerializedFile v22, получена v%d"
                         % header.version)

    replacement = {}
    for obj in serialized.objects.values():
        if obj.type.name != "Font":
            continue
        try:
            name = obj.read_typetree().get("m_Name")
        except Exception:
            continue
        if name in expected:
            replacement[obj.path_id] = obj.data

    meta_writer = EndianBinaryWriter(endian=header.endian)
    data_writer = EndianBinaryWriter(endian=header.endian)
    if header.version >= 7:
        meta_writer.write_string_to_null(serialized.unity_version)
    if header.version >= 8:
        meta_writer.write_int(serialized._m_target_platform)
    if header.version >= 13:
        meta_writer.write_boolean(serialized._enable_type_tree)
    meta_writer.write_int(len(serialized.types))
    for typ in serialized.types:
        typ.write(serialized, meta_writer, False)
    if 7 <= header.version < 14:
        meta_writer.write_int(serialized.big_id_enabled)
    meta_writer.write_int(len(serialized.objects))
    for obj in sorted(serialized.objects.values(), key=lambda item: item.path_id):
        raw = replacement.get(obj.path_id)
        if raw is None:
            raw = source_data[obj.byte_start:obj.byte_start + obj.byte_size]
        obj.data = raw
        obj.write(header, meta_writer, data_writer)
        data_writer.align_stream(8)
    if header.version >= 11:
        meta_writer.write_int(len(serialized.script_types))
        for item in serialized.script_types:
            item.write(header, meta_writer)
    meta_writer.write_int(len(serialized.externals))
    for item in serialized.externals:
        item.write(header, meta_writer)
    if header.version >= 20:
        meta_writer.write_int(len(serialized.ref_types))
        for item in serialized.ref_types:
            item.write(serialized, meta_writer, True)
    if header.version >= 5:
        meta_writer.write_string_to_null(serialized.userInformation)

    metadata_size = meta_writer.Length
    data_offset = 48 + metadata_size
    data_offset += (16 - data_offset % 16) % 16
    file_size = data_offset + data_writer.Length
    writer = EndianBinaryWriter()
    writer.write_u_int(0)
    writer.write_u_int(0)
    writer.write_u_int(header.version)
    writer.write_u_int(0)
    writer.write_boolean(">" == header.endian)
    writer.write_bytes(header.reserved)
    writer.write_u_int(metadata_size)
    writer.write_long(file_size)
    writer.write_long(data_offset)
    writer.write_long(serialized.unknown)
    writer.write_bytes(meta_writer.bytes)
    writer.align_stream(16)
    writer.write_bytes(data_writer.bytes)
    return writer.bytes


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


def verify(path: str, original_path: str, expected: dict = None) -> None:
    """Записанный файл должен держать те же объекты, что и оригинал.

    Число кириллических глифов сверяется с ожидаемым у каждого шрифта
    отдельно: у семи текстовых шрифтов игры кириллица должна лечь целиком.
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
    print("проверено: %d объектов, %d изменено, %d кириллических глифов"
          % (len(objects), differing, cyrillic))

    if expected:
        check_cyrillic(path, expected)

    # Ридер держит файл открытым, а Windows не заменяет открытый файл.
    for env in (before_env, after_env):
        release(env)
    del before_env, after_env


def check_cyrillic(path: str, expected: dict) -> None:
    """У каждого правленого шрифта кириллица должна лечь целиком."""
    import UnityPy

    env = UnityPy.load(path)
    counts = {}
    for obj, name, raw in font_objects(env):
        if name in expected:
            counts[name] = len([c for c in load_font(raw).getBestCmap()
                                if 0x0400 <= c <= 0x04FF])
    for name, minimum in expected.items():
        found = counts.get(name, 0)
        if found < minimum:
            raise SystemExit("в шрифте %s %d кириллических глифов, ожидалось "
                             "не меньше %d" % (name, found, minimum))
    release(env)


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
    parser.add_argument("--mode", default="grid", choices=["metric", "grid", "cap"],
                        help="как кириллица масштабируется под шрифт игры")
    parser.add_argument("--fonts", default="",
                        help="имена шрифтов через запятую, которые нужно править")
    args = parser.parse_args()

    wanted = {name.strip() for name in args.fonts.split(",") if name.strip()}
    data, patched, expected = patch_assets(args.assets, args.mode, wanted or None)

    with open(args.out, "wb") as fh:
        fh.write(data)
    print("записан %s (%d байт, было %d)"
          % (args.out, len(data), os.path.getsize(args.assets)))
    verify(args.out, args.assets, expected)


if __name__ == "__main__":
    main()
