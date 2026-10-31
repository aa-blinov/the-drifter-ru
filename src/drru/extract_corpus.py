#!/usr/bin/env python
"""SystemText игры, прочитанный прямо из ресурсов.

Игра хранит свой текст в одном MonoBehaviour внутри
TheDrifter_Data/sharedassets1.assets: PowerTools.Quest.SystemText. Каждая
строка игры это одна запись там, с персонажем, который её произносит,
идентификатором, которым игра её адресует, исходным файлом и исходной
функцией, откуда она взята.

В сборке игры нет дерева типов для этого MonoBehaviour, поэтому обычные
читатели его не обходят. Раскладка известна и фиксирована, поэтому она
разбирается здесь: порядок полей ниже это тот, который пишет игра, а парсер
проверяется против игры на каждом запуске, чтением блоба обратно и сравнением
побайтово. Раскладка, которая не проходит туда и обратно, прочитана неверно,
и запуск на этом останавливается.

Файлы игры принадлежат разработчику. Этот скрипт читает копию, которой
владеет пользователь, и пишет только текст, никогда ресурсы.

    python3 src/drru/extract_corpus.py --game "<путь к The Drifter>"
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import struct
import sys

# Идентификатор пути MonoBehaviour SystemText в sharedassets1.assets.
SYSTEM_TEXT_PATH_ID = 28977


class Reader:
    """Маленький бинарный формат, в котором игра пишет свой текст."""

    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def raw(self, size: int) -> bytes:
        chunk = self.data[self.offset:self.offset + size]
        if len(chunk) != size:
            raise ValueError("чтение вышло за конец блоба")
        self.offset += size
        return chunk

    def i32(self) -> int:
        value = struct.unpack("<i", self.raw(4))[0]
        return value

    def u8(self) -> int:
        return self.raw(1)[0]

    def align(self):
        while self.offset % 4:
            self.raw(1)

    def string(self) -> str:
        length = self.i32()
        value = self.raw(length).decode("utf-8", "replace")
        self.align()
        return value

    def string_list(self):
        count = self.i32()
        return [self.string() for _ in range(count)]

    def file_id(self):
        """Указатель, который игра хранит на объект Unity."""
        return struct.unpack("<iq", self.raw(12))

    def floats(self):
        count = self.i32()
        return list(struct.unpack("<%df" % count, self.raw(4 * count)))

    def ushorts(self):
        count = self.i32()
        return list(struct.unpack("<%dH" % count, self.raw(2 * count)))


def parse_systemtext(data: bytes) -> dict:
    """Дерево блоба SystemText."""
    reader = Reader(data)
    tree = {
        "m_GameObject": reader.file_id(),
        "m_Enabled": reader.u8(),
    }
    reader.align()
    tree["m_Script"] = reader.file_id()
    tree["m_Name"] = reader.string()

    languages = []
    for _ in range(reader.i32()):
        languages.append({
            "m_code": reader.string(),
            "m_description": reader.string(),
            "m_customData": reader.string_list(),
        })
    tree["m_languages"] = languages

    tree["m_defaultTextSource"] = reader.i32()
    tree["m_lipSyncExtendedShapes"] = reader.string()

    strings = []
    for _ in range(reader.i32()):
        entry = {
            "m_character": reader.string(),
            "m_id": reader.i32(),
            "m_orderId": reader.i32(),
            "m_string": reader.string(),
            "m_sourceFile": reader.string(),
            "m_sourceFunction": reader.string(),
            "m_translations": reader.string_list(),
            "m_phonesTime": reader.floats(),
            "m_phonesCharacter": reader.ushorts(),
        }
        reader.align()
        entry["m_changedSinceImport"] = reader.u8()
        reader.align()
        strings.append(entry)
    tree["m_strings"] = strings

    tree["m_voVolTweaksFile"] = reader.file_id()
    if reader.offset != len(data):
        raise ValueError("прочитано %d байт из %d" % (reader.offset, len(data)))
    return tree


def serialize_systemtext(tree: dict) -> bytes:
    """Тот же блоб, записанный обратно."""
    out = io.BytesIO()

    def raw(data):
        out.write(data)

    def i32(value):
        out.write(struct.pack("<i", value))

    def u8(value):
        out.write(struct.pack("<B", value))

    def align():
        while out.tell() % 4:
            out.write(b"\x00")

    def string(value):
        encoded = value.encode("utf-8")
        i32(len(encoded))
        out.write(encoded)
        align()

    def string_list(values):
        i32(len(values))
        for value in values:
            string(value)

    raw(struct.pack("<iq", *tree["m_GameObject"]))
    u8(tree["m_Enabled"])
    align()
    raw(struct.pack("<iq", *tree["m_Script"]))
    string(tree["m_Name"])

    i32(len(tree["m_languages"]))
    for language in tree["m_languages"]:
        string(language["m_code"])
        string(language["m_description"])
        string_list(language["m_customData"])

    i32(tree["m_defaultTextSource"])
    string(tree["m_lipSyncExtendedShapes"])

    i32(len(tree["m_strings"]))
    for entry in tree["m_strings"]:
        string(entry["m_character"])
        i32(entry["m_id"])
        i32(entry["m_orderId"])
        string(entry["m_string"])
        string(entry["m_sourceFile"])
        string(entry["m_sourceFunction"])
        string_list(entry["m_translations"])
        i32(len(entry["m_phonesTime"]))
        for value in entry["m_phonesTime"]:
            out.write(struct.pack("<f", value))
        i32(len(entry["m_phonesCharacter"]))
        for value in entry["m_phonesCharacter"]:
            out.write(struct.pack("<H", value))
        align()
        u8(entry["m_changedSinceImport"])
        align()

    raw(struct.pack("<iq", *tree["m_voVolTweaksFile"]))
    return out.getvalue()


def load_systemtext(game_dir: str):
    """Блоб SystemText игры."""
    import UnityPy

    assets = os.path.join(game_dir, "TheDrifter_Data", "sharedassets1.assets")
    if not os.path.exists(assets):
        raise SystemExit("не найдено: %s" % assets)
    env = UnityPy.load(assets)
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour" and obj.path_id == SYSTEM_TEXT_PATH_ID:
            return obj.get_raw_data()
    raise SystemExit("SystemText не найден в %s" % assets)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, help="каталог с игрой")
    parser.add_argument("--out", default=None)
    parser.add_argument("--no-check", action="store_true",
                        help="пропустить проверку парсера туда и обратно")
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out = args.out or os.path.join(root, "corpus", "english.csv")

    blob = load_systemtext(args.game)
    tree = parse_systemtext(blob)

    if not args.no_check:
        # Парсер должен прочитать блоб ровно так, как его писала игра, иначе
        # корпус это догадка.
        again = serialize_systemtext(tree)
        if again != blob:
            raise SystemExit("парсер не проходит туда и обратно: на входе %d байт, "
                             "на выходе %d байт" % (len(blob), len(again)))
        print("парсер: блоб проходит туда и обратно (%d байт)" % len(blob))

    languages = [(l["m_code"], l["m_description"]) for l in tree["m_languages"]]
    print("языки: %s" % ", ".join("%s=%s" % (c, d) for c, d in languages))

    rows = []
    for entry in tree["m_strings"]:
        rows.append([
            entry["m_character"],
            str(entry["m_id"]),
            entry["m_sourceFile"],
            entry["m_sourceFunction"],
            entry["m_string"].rstrip(),
        ])

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["Character", "ID", "File", "Context", "English"])
        writer.writerows(rows)
    print("извлечение: %d строк -> %s" % (len(rows), out))


if __name__ == "__main__":
    main()
