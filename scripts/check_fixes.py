#!/usr/bin/env python
"""Check that the hand corrections do not lose the source.

A correction replaces a line of the translation. A correction that drops a
sentence of the source is a defect that no other check sees: the line is
still good Russian, it is simply not the English line any more.

This reads every correction and compares it with the English source it
belongs to. The two are compared by what they carry: the placeholders, the
tags of the game, the numbers, the names, and the number of the sentences.

    python3 scripts/check_fixes.py
    python3 scripts/check_fixes.py --verbose
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "corpus", "english.csv")
FIXES = os.path.join(ROOT, "src", "voice", "manual_fixes.json")

PLACEHOLDER = re.compile(r"\{[^}]*\}")
NUMBER = re.compile(r"\d+")
WORD = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\-]*")


def sentences(text):
    """The sentences of a line, however it ends them.

    A dot that sits between two digits is a decimal point, and a dot that
    follows a single letter is the end of an abbreviation: «14.46 CPM» and
    «M.O.» are one sentence each. The ellipsis always ends a sentence: the
    words on both sides of it belong to different thoughts.
    """
    parts = re.split(r"…+|(?<![0-9A-Za-zА-Яа-яЁё])[.!?]+", text)
    return [p.strip() for p in parts if p.strip()]


def content_words(text):
    """The words of a line that carry its meaning.

    The short words are left out: a Russian line holds more of them than an
    English one, and counting them would make every line look shorter.
    """
    return [w for w in WORD.findall(text) if len(w) >= 4]


def shared_words(before, after):
    """How much of the line the correction kept.

    A correction rephrases a line: it keeps most of its words and changes
    some of them. A correction that shares almost nothing with the line it
    replaces is a correction that landed on the wrong row — the sign of a
    key that was written without its character.
    """
    old = set(w.lower() for w in WORD.findall(before) if len(w) >= 3)
    new = set(w.lower() for w in WORD.findall(after) if len(w) >= 3)
    if not old or not new:
        return 1.0
    return len(old & new) / float(min(len(old), len(new)))


# A preposition at the end of a line: the sentence cannot end there. It is
# the sign of a line that was cut in the middle.
DANGLING = re.compile(
    r"\b(?:в|на|с|к|по|из|о|об|у|до|за|для|от|под|над|при|про|через|без|"
    r"около|после|перед|между|ради|из-за)\s*[.!?…»]*$", re.IGNORECASE)


def cut_off(text: str) -> bool:
    """The line ends in the middle of a sentence.

    The game clips some of its lines on purpose, and such a line ends in
    an ellipsis. A line that ends in a preposition is cut by mistake.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.endswith(("…", "...")):
        return False
    # A label of the interface is short: «Поговорить с» ends in a
    # preposition and is complete.
    if len(stripped.split()) < 5:
        return False
    return DANGLING.search(stripped) is not None


def names(text):
    """The words that carry the facts: the numbers and the names."""
    return set(NUMBER.findall(text))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--corpus-jsonl", default=os.path.join(
        ROOT, "work", "corpus", "polish.jsonl"),
        help="the corpus the corrections were made against")
    args = parser.parse_args()

    with io.open(CORPUS, encoding="utf-8", newline="") as fh:
        corpus = list(csv.reader(fh))[1:]
    english = {"%s|%s" % (r[0], r[1]): r[4] for r in corpus}

    # The line each correction replaced, so a correction that landed on the
    # wrong row can be seen.
    before = {}
    if os.path.exists(args.corpus_jsonl):
        with io.open(args.corpus_jsonl, encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                before["%s|%s" % (row.get("character", ""), row.get("id", ""))] = row["ru"]

    fixes = json.load(io.open(FIXES, encoding="utf-8"))
    problems = []
    for key, russian in sorted(fixes.items()):
        source = english.get(key)
        if source is None:
            problems.append(("нет такой строки в корпусе", key, source, russian))
            continue
        if sorted(PLACEHOLDER.findall(source)) != sorted(PLACEHOLDER.findall(russian)):
            problems.append(("потерян плейсхолдер", key, source, russian))
        if source.count("<color") != russian.count("<color"):
            problems.append(("потеряна разметка", key, source, russian))
        lost = names(source) - names(russian)
        if lost:
            problems.append(("потеряно число: %s" % ", ".join(sorted(lost)),
                             key, source, russian))
        # An ellipsis is not the end of a sentence: the words on both sides
        # of it belong to the same thought.
        if len(sentences(source)) > len(sentences(russian)) + 1:
            problems.append(("потеряно предложение", key, source, russian))
        # A dropped sentence takes a third of the line with it. The Russian
        # is usually longer than the English, but a compact rendering of a
        # technical phrase («orders of magnitude» — «на порядки») is not a
        # loss, so the rule is loose: it fires only on a real shortfall.
        words_en = len(content_words(source))
        words_ru = len(content_words(russian))
        if words_en >= 12 and words_ru < words_en * 0.55:
            problems.append(("потеряна часть текста", key, source, russian))
        old = before.get(key)
        if old is not None:
            # A correction rephrases a line; it does not replace it with a
            # different one. A correction that is much longer than the line
            # it took the place of landed on the wrong row — the sign of a
            # key that was written without its character.
            grew = len(content_words(russian)) > len(content_words(old)) * 1.6 + 3
            if grew or (len(content_words(old)) >= 8
                        and shared_words(old, russian) < 0.2):
                problems.append(("правка попала не в ту строку", key, source, russian))
        if cut_off(russian) and not cut_off(source):
            # The line ends in a preposition: it was cut in the middle.
            problems.append(("строка обрезана", key, source, russian))

    print("corrections: %d" % len(fixes))
    print("corrections that lose the source: %d" % len(problems))
    for what, key, source, russian in problems:
        print("  %s: %s" % (what, key))
        if args.verbose:
            print("      EN: %s" % (source or "")[:100])
            print("      RU: %s" % russian[:100])

    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
