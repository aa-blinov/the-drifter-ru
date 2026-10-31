#!/usr/bin/env python
"""Корпус: английские строки игры вместе с ключами, которыми игра их адресует.

Игра адресует текст парой (character, id): одна и та же английская строка
встречается в нескольких местах, и перевод должен быть одинаковым во всех
них. Корпус хранит эти ключи, исходный файл и исходную функцию, потому что
контекст строки, кто говорит, в какой комнате, в какой функции, это то, что
делает перевод верным.

Читается из corpus/english.csv, который пишет скрипт извлечения:

    python3 src/drru/extract_corpus.py --game "<путь к The Drifter>"

Пишется в JSONL, по одной строке на строку игры, чтобы этап мог прочитать
её срез, не разбирая CSV.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CORPUS_CSV = os.path.join(ROOT, "corpus", "english.csv")
WORK = os.path.join(ROOT, "work")
CORPUS_JSONL = os.path.join(WORK, "corpus", "corpus.jsonl")

# Колонка, из которой игра читает перевод, и заголовок, который игра
# ожидает в импортируемом CSV.
LANG_CODE = "RU"
CSV_HEADER = ["Character", "ID", "File", "Context", "English", "Русский"]


def load_corpus(path: str = CORPUS_CSV):
    """Все строки игры в том порядке, в каком игра их держит."""
    if not os.path.exists(path):
        raise SystemExit("корпус не найден: %s" % path)
    rows = []
    with io.open(path, encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header[:5] != ["Character", "ID", "File", "Context", "English"]:
            raise SystemExit("неожиданный заголовок корпуса: %r" % (header,))
        for index, row in enumerate(reader):
            if len(row) < 5:
                raise SystemExit("короткая строка %d: %r" % (index, row))
            rows.append({
                "index": index,
                "character": row[0],
                "id": row[1],
                "file": row[2],
                "context": row[3],
                "en": row[4],
            })
    return rows


def write_jsonl(rows, path: str = CORPUS_JSONL):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def read_jsonl(path: str):
    rows = []
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def key_of(row) -> str:
    """Ключ, которым игра адресует строку: персонаж плюс идентификатор."""
    return "%s|%s" % (row.get("character", ""), row.get("id", ""))


if __name__ == "__main__":
    rows = load_corpus()
    path = write_jsonl(rows)
    characters = len({r["character"] for r in rows})
    files = len({r["file"] for r in rows})
    print("корпус: %d строк, %d персонажей, %d исходных файлов -> %s"
          % (len(rows), characters, files, path))
