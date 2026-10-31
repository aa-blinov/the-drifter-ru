#!/usr/bin/env python
"""Сборка docs/glossary.md из глоссария и перевода.

У глоссария две формы: машинная, к которой привязан пайплайн, и документ,
который читает человек. Документ, написанный руками, расходится с файлом,
который описывает: термин добавлен в файл, а в таблице его нет.

Скрипт собирает таблицу из файла, а счётчики из перевода, поэтому они не
могут разойтись. Проза остаётся в документе между маркерами; генерируются
только таблица и счётчики.

    python3 scripts/render_glossary.py
"""
from __future__ import annotations

import collections
import csv
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLOSSARY = os.path.join(ROOT, "src", "voice", "glossary.json")
CORPUS = os.path.join(ROOT, "corpus", "english.csv")
TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")
DOC = os.path.join(ROOT, "docs", "glossary.md")

BEGIN = "<!-- glossary:table:begin -->"
END = "<!-- glossary:table:end -->"

WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")


def source_terms(corpus):
    """Сколько строк источника упоминают каждый термин.

    Термин ищется целиком, вместе с падежными окончаниями: «Mick» и
    «Mick's» это одно упоминание, а «Roth» это упоминание в «Dr. Roth».
    """
    seen = collections.Counter()
    for row in corpus:
        english = row[4]
        for word in WORD.findall(english):
            if not word[:1].isupper():
                continue
            seen[word] += 1
    return seen


def main():
    glossary = json.load(io.open(GLOSSARY, encoding="utf-8"))
    with io.open(CORPUS, encoding="utf-8", newline="") as fh:
        corpus = list(csv.reader(fh))[1:]
    with io.open(TRANSLATION, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.reader(fh))

    seen = source_terms(corpus)
    lines = []
    for term in sorted(glossary, key=lambda t: (t.lower(), t)):
        ru = glossary[term]
        pattern = r"(?<![A-Za-z])" + re.escape(term) + r"(?:'s)?(?![A-Za-z])"
        count = sum(1 for row in corpus
                    if re.search(pattern, row[4], re.IGNORECASE))
        note = ""
        if count == 1:
            note = " (1 строка)"
        elif count > 1:
            note = " (%d строк)" % count
        lines.append("| %s | %s |%s" % (term, ru, note))

    body = "\n".join(lines)
    text = io.open(DOC, encoding="utf-8").read()
    if BEGIN not in text or END not in text:
        raise SystemExit("маркеров нет в документе")
    head, rest = text.split(BEGIN, 1)
    _old, tail = rest.split(END, 1)
    text = "%s%s\n%s\n%s%s" % (head, BEGIN, body, END, tail)
    io.open(DOC, "w", encoding="utf-8", newline="\n").write(text)
    print("glossary.md: %d терминов" % len(lines))


if __name__ == "__main__":
    main()
