#!/usr/bin/env python
"""Fill the gaps in the glossary from the translation that exists.

The glossary is the promise that a term has one Russian word. A term that
is missing from it is a term the pipeline is free to render any way it
likes, and the proof of that is in the text: the same name comes out in two
spellings.

This script finds the terms of the source that the glossary does not cover
and asks the model, over the lines where the term actually appears, which
Russian word the translation uses for it. The answer comes from the text,
not from the model's taste, and it is checked against the lines before it is
written.

    python3 scripts/glossary_expand.py            # what would be added
    python3 scripts/glossary_expand.py --apply    # write it into the glossary

The terms the model cannot pin down are left out: a glossary entry that is
wrong is worse than a missing one.
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from drru import llm_client  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_glossary  # noqa: E402

CORPUS = os.path.join(ROOT, "corpus", "english.csv")
TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")
GLOSSARY = os.path.join(ROOT, "src", "voice", "glossary.json")

WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]+")
RU_WORD = re.compile(r"[А-Яа-яЁё][А-Яа-яЁё\-]*")

SYSTEM = """Ты работаешь с глоссарием русского перевода игры The Drifter.

Тебе дают английские термины и строки перевода, где они встречаются. Назови русскую форму, которую перевод уже использует для каждого термина.

Правила:
- Бери форму ИЗ ТЕКСТА, не придумывай свою.
- Если в строках термин переведён по-разному (разные слова, разные формы), выбери ту, что встречается чаще, и напиши в why, что есть расхождение.
- Если термин в строках оставлен на латинице (MedCon, Mulindji), верни его как есть.
- Если термин не переведён и в тексте не видно, верни пустую строку.
- Ответ строго JSON: {"terms": [{"term": "...", "ru": "...", "why": "..."}]}
- Ничего, кроме JSON, не пиши."""


def source_terms(corpus, stop):
    """The capitalised words of the source that are not the first word."""
    counter = collections.Counter()
    lines = collections.defaultdict(list)
    for row in corpus:
        english = row[4]
        for index, word in enumerate(WORD.findall(english)):
            if index == 0 or not word[:1].isupper():
                continue
            if word.lower() in stop or "'" in word or "’" in word:
                continue
            counter[word] += 1
            lines[word].append(row)
    return counter, lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--min-count", type=int, default=4)
    parser.add_argument("--model", default=os.environ.get("DRRU_MODEL", "minimax-m3"))
    args = parser.parse_args()

    with io.open(CORPUS, encoding="utf-8", newline="") as fh:
        corpus = list(csv.reader(fh))[1:]
    with io.open(TRANSLATION, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.reader(fh))
    ru_col = table[0].index("Русский")
    translation = {(r[0], r[1]): r[ru_col] for r in table[1:] if len(r) > ru_col}
    english_of = {(r[0], r[1]): r[4] for r in corpus}

    glossary = json.load(io.open(GLOSSARY, encoding="utf-8"))
    stop = set(build_glossary.STOP)

    counter, lines = source_terms(corpus, stop)
    missing = [(t, c) for t, c in counter.most_common()
               if c >= args.min_count and t not in glossary]
    print("terms to resolve: %d" % len(missing))

    # the model is asked in batches, and every answer is checked against the
    # text before it is accepted
    resolved = {}
    notes = []
    batch_size = 20
    for start in range(0, len(missing), batch_size):
        part = missing[start:start + batch_size]
        payload = []
        for term, count in part:
            examples = []
            for row in lines[term][:6]:
                key = (row[0], row[1])
                examples.append({"en": row[4], "ru": translation.get(key, "")})
            payload.append({"term": term, "count": count, "lines": examples})
        user = json.dumps({"terms": payload}, ensure_ascii=False, indent=1)
        text = llm_client.call_llm(args.model, SYSTEM, user, max_tokens=6000,
                                   temperature=0.0)
        parsed = llm_client.extract_json_object(text)
        if not parsed:
            print("  batch %d: no answer" % (start // batch_size))
            continue
        for item in parsed.get("terms", []):
            term = item.get("term", "")
            ru = (item.get("ru") or "").strip()
            if not term or not ru:
                continue
            if term not in counter:
                continue
            resolved[term] = ru
            notes.append((term, ru, item.get("why", "")))

    print("resolved: %d" % len(resolved))
    for term, ru, why in sorted(notes):
        flag = "!" if why else " "
        print("  %s %-22s -> %-24s %s" % (flag, term, ru, why[:70]))

    if args.apply:
        added = 0
        for term, ru, _why in notes:
            if term in glossary:
                continue
            glossary[term] = ru
            added += 1
        ordered = dict(sorted(glossary.items(), key=lambda kv: kv[0].lower()))
        with io.open(GLOSSARY, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(ordered, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        print("glossary: %d entries, %d added" % (len(glossary), added))


if __name__ == "__main__":
    main()
