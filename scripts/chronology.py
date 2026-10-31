#!/usr/bin/env python
"""Хронология игры: всё время, которое называет текст.

У сюжета есть порядок, и перевод, который двигает дату, год или
последовательность, ломает его так, что этого не видит ни одна проверка
орфографии. Скрипт собирает все временные ссылки источника вместе с
русским текстом, который их несёт, чтобы порядок можно было прочитать.

    python3 scripts/chronology.py                 # все временные ссылки
    python3 scripts/chronology.py --year          # годы и эпохи
    python3 scripts/chronology.py --show "five"   # строки, которые это называют
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "corpus", "english.csv")
TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")

# Слова, которые называют время.
TIME = re.compile(
    r"\b("
    r"yesterday|tomorrow|tonight|today|now|then|already|still|yet|soon|"
    r"later|ago|before|after|during|while|since|until|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"january|february|march|april|may|june|july|august|september|october|"
    r"november|december|"
    r"morning|afternoon|evening|night|midnight|noon|dawn|dusk|"
    r"week|month|year|decade|century|hour|minute|second|moment|"
    r"monday|january|june|"
    r"early|late|sooner|later|first|second|third|final|last|"
    r"five|four|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|sixty|"
    r"seventy|eighty|ninety|hundred|thousand|million|billion|"
    r"once|twice|thrice|again|always|never|sometimes|often|rarely|"
    r"future|past|present|history|century|era|period|"
    r"childhood|teenager|adult|elderly|baby|infant"
    r")\b", re.IGNORECASE)

YEAR = re.compile(r"\b(1[89]\d\d|20[0-2]\d)\b")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", default="",
                        help="строки, которые это называют")
    parser.add_argument("--year", action="store_true",
                        help="годы, которые называет текст")
    args = parser.parse_args()

    with io.open(CORPUS, encoding="utf-8", newline="") as fh:
        corpus = list(csv.reader(fh))[1:]
    with io.open(TRANSLATION, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.reader(fh))
    ru_col = table[0].index("Русский")
    translation = {"%s|%s" % (r[0], r[1]): r[ru_col] for r in table[1:]}

    if args.show:
        pattern = re.compile(re.escape(args.show), re.IGNORECASE)
        for row in corpus:
            english = row[4]
            if not pattern.search(english):
                continue
            key = "%s|%s" % (row[0], row[1])
            print("  EN: %s" % english[:92])
            print("  RU: %s" % translation.get(key, "")[:92])
        return

    if args.year:
        found = collections.Counter()
        where = collections.defaultdict(list)
        for row in corpus:
            for year in YEAR.findall(row[4]):
                found[year] += 1
                where[year].append(row[0])
        for year in sorted(found):
            print("%-6s %3d  %s" % (year, found[year], ", ".join(where[year][:6])))
        return

    # каждое слово, которое называет время, вместе с русским текстом, который его несёт
    words = collections.Counter()
    lines = collections.defaultdict(list)
    for row in corpus:
        english = row[4]
        for word in TIME.findall(english):
            key = word.lower()
            words[key] += 1
            lines[key].append(row)
    print("%-16s %6s" % ("слово", "число"))
    for word, count in words.most_common():
        print("%-16s %6d" % (word, count))


if __name__ == "__main__":
    main()
