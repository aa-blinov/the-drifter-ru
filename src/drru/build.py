#!/usr/bin/env python
"""The build: the canonical corpus becomes the file the game reads.

The game looks for translation.csv in its own directory. The header is
fixed by the game's importer:

    Character,ID,File,Context,English,<language name>

The rows are keyed by (Character, ID) — that pair is what the game uses, so
it is what the file carries. The English column is the reference the game
shows next to the translation; it stays in the file.

The file is written as UTF-8 with a BOM and CRLF, because that is what the
game's importer expects on Windows.

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
# The file the last stage wrote: the corpus after the polish pass and the
# hand corrections. Building from an earlier stage would ship the defects
# those two stages exist to remove.
CANON_PATH = os.path.join(ROOT, "work", "corpus", "final.jsonl")
CORPUS_CSV = os.path.join(ROOT, "corpus", "english.csv")
OUT_DIR = os.path.join(ROOT, "translation", "Russian")
OUT_PATH = os.path.join(OUT_DIR, "translation.csv")

LANG_NAME = "Русский"


def build(canon_path: str = CANON_PATH, out_path: str = OUT_PATH):
    rows = corpus.read_jsonl(canon_path)
    source = corpus.load_corpus()
    if len(rows) != len(source):
        raise SystemExit("the corpus has %d lines, the translation has %d"
                         % (len(source), len(rows)))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # The importer reads the file with Encoding.Default plus a BOM check, so
    # the BOM is not decoration: without it the Cyrillic arrives as mojibake.
    with io.open(out_path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
        writer.writerow(corpus.CSV_HEADER[:-1] + [LANG_NAME])
        for row, original in zip(rows, source):
            # The key and the English column come from the corpus, so the file
            # that ships and the corpus it was built from cannot drift apart.
            writer.writerow([original["character"], original["id"],
                             original["file"], original["context"],
                             original["en"], row["ru"]])

    size = os.path.getsize(out_path)
    print("build: %d rows -> %s (%.1f KB)" % (len(rows), out_path, size / 1024))
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=CANON_PATH)
    parser.add_argument("--out", default=OUT_PATH)
    args = parser.parse_args()
    build(args.corpus, args.out)
