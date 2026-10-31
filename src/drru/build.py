#!/usr/bin/env python
"""Сборка: канонический корпус превращается в файл, который читает игра.

Игра ищет translation.csv в своём каталоге. Заголовок задан импортёром игры:

    Character,ID,File,Context,English,<language name>

Строки адресуются парой (Character, ID), именно эту пару использует игра,
поэтому её и несёт файл. Английская колонка это образец, который игра показывает
рядом с переводом, поэтому она остаётся в файле.

Файл записывается в UTF-8 с BOM и CRLF, потому что этого ожидает импортёр
игры на Windows.

    python3 src/drru/build.py
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drru import corpus  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
# Файл, который записал последний этап: корпус после полировки и ручных
# правок. Сборка с более раннего этапа отгрузила бы те дефекты, ради
# устранения которых эти два этапа и существуют.
CANON_PATH = os.path.join(ROOT, "work", "corpus", "final.jsonl")
CORPUS_CSV = os.path.join(ROOT, "corpus", "english.csv")
OUT_DIR = os.path.join(ROOT, "translation", "Russian")
OUT_PATH = os.path.join(OUT_DIR, "translation.csv")

LANG_NAME = "Русский"


def build(canon_path: str = CANON_PATH, out_path: str = OUT_PATH):
    rows = corpus.read_jsonl(canon_path)
    source = corpus.load_corpus()
    if len(rows) != len(source):
        raise SystemExit("в корпусе %d строк, а в переводе %d"
                         % (len(source), len(rows)))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Импортёр читает файл через Encoding.Default с проверкой BOM, поэтому
    # BOM здесь не украшение: без него кириллица приходит в виде мусора.
    with io.open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
        writer.writerow(corpus.CSV_HEADER[:-1] + [LANG_NAME])
        for row, original in zip(rows, source):
            # Ключ и английская колонка берутся из корпуса, поэтому отгружаемый
            # файл и корпус, из которого он собран, не могут разойтись.
            writer.writerow([original["character"], original["id"],
                             original["file"], original["context"],
                             original["en"], row["ru"]])

    size = os.path.getsize(out_path)
    print("сборка: %d строк -> %s (%.1f KB)" % (len(rows), out_path, size / 1024))
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=CANON_PATH)
    parser.add_argument("--out", default=OUT_PATH)
    args = parser.parse_args()
    build(args.corpus, args.out)
