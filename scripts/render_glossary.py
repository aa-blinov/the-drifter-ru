#!/usr/bin/env python
"""Render docs/glossary.md from the glossary and the translation.

The glossary has two forms: the machine-readable one, which the pipeline is
bound to, and the document, which a reader reads. A document that is written
by hand drifts from the file it describes: a term is added to the file and
the table still does not have it.

This renders the table from the file and the counts from the translation,
so the two cannot disagree. The prose is kept in the document between the
markers; only the table and the counts are generated.

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
    """How many lines of the source mention each term.

    The term is matched as a whole, with its case endings: «Mick» and
    «Mick's» are the same mention, and «Roth» is a mention in «Dr. Roth».
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
            note = " — 1 строка"
        elif count > 1:
            note = " — %d строк" % count
        lines.append("| %s | %s |%s" % (term, ru, note))

    body = "\n".join(lines)
    text = io.open(DOC, encoding="utf-8").read()
    if BEGIN not in text or END not in text:
        raise SystemExit("the markers are not in the document")
    head, rest = text.split(BEGIN, 1)
    _old, tail = rest.split(END, 1)
    text = "%s%s\n%s\n%s%s" % (head, BEGIN, body, END, tail)
    io.open(DOC, "w", encoding="utf-8", newline="\n").write(text)
    print("glossary.md: %d terms" % len(lines))


if __name__ == "__main__":
    main()
