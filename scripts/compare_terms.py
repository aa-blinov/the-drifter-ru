#!/usr/bin/env python
"""Compare two corpora by the words they use for the same term.

The law of the unbinding term says that a term the glossary does not hold is
translated again in every file of the script. This measures it: for every
term of the glossary it counts the Russian words the two corpora use.

    python3 scripts/compare_terms.py work/corpus/bulk.jsonl work/corpus/bulk_trial.jsonl
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLOSSARY = os.path.join(ROOT, "src", "voice", "glossary.json")

# The terms of the game, and the Russian words each of them may be written as.
TERMS = {
    "phase-flip": r"фазов\w+ (?:переворот\w*|переключен\w*|сдвиг\w*)|"
                  r"переключ\w* фазы|смен\w+ фазы|фазов\w+ переход\w*",
    "receptionist": r"рецепционистк\w*|секретар\w*|администраторш\w*",
    "third founder": r"треть\w+ соучредительниц\w+|треть\w+ основател\w+",
    "quantum coupler": r"квантов\w+ (?:соединител\w*|ответвител\w*|муфтрон\w*)|"
                       r"\bсоединител\w*|\bответвител\w*|\bмуфтрон\w*",
    "live wire": r"оголённ\w+ провод|провод под напряжением",
    "blast door": r"взрывн\w+ двер\w+|гермодвер\w+|аварийн\w+ двер\w+",
    "reactor floor": r"пол\w* реактора|этаж\w* реактора",
    "access shaft": r"шахт\w+ для доступа|смотров\w+ колодец|колодец\w* для доступа",
    "business ID": r"регистрационн\w+ номер\w*|бизнес-номер\w*|служебн\w+ (?:удостоверен\w*|идентификатор\w*)",
}


def load(path):
    out = {}
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            out["%s|%s" % (row.get("character", ""), row.get("id", ""))] = row
    return out


def forms(corpus, pattern):
    """The Russian words one term is written as, and the files they come from."""
    compiled = re.compile(pattern, re.IGNORECASE)
    found = collections.Counter()
    where = collections.defaultdict(set)
    for key, row in corpus.items():
        for word in compiled.findall(row.get("ru", "")):
            found[word.lower()] += 1
            where[word.lower()].add(row.get("file", ""))
    return found, where


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--glossary", default=GLOSSARY)
    args = parser.parse_args()

    before = load(args.before)
    after = load(args.after)
    glossary = json.load(io.open(args.glossary, encoding="utf-8"))

    print("%-18s %-28s %-28s" % ("term", "before", "after"))
    print("-" * 78)
    worse = better = same = 0
    for label, pattern in sorted(TERMS.items()):
        fb, wb = forms(before, pattern)
        fa, wa = forms(after, pattern)
        files_before = len(set().union(*wb.values())) if wb else 0
        files_after = len(set().union(*wa.values())) if wa else 0
        print("%-18s %2d forms in %2d files   %2d forms in %2d files"
              % (label, len(fb), files_before, len(fa), files_after))
        for word, count in fa.most_common(3):
            print("      %-26s ×%d" % (word, count))
        if len(fa) < len(fb):
            better += 1
        elif len(fa) > len(fb):
            worse += 1
        else:
            same += 1
    print()
    print("терминов стало меньше вариантов: %d, больше: %d, столько же: %d"
          % (better, worse, same))

    # the glossary itself: does the corpus use the word the glossary holds?
    print()
    print("=== соответствие глоссарию ===")
    for term, ru in sorted(glossary.items()):
        if len(term) < 4 or not ru[:1].isupper():
            continue
        used = collections.Counter()
        pattern = re.compile(r"\b%s\w*" % re.escape(ru.split()[0]), re.IGNORECASE)
        for row in after.values():
            for word in pattern.findall(row.get("ru", "")):
                used[word.lower()] += 1
        if not used:
            continue
        head = ru.split()[0].lower()
        share = used[head] / float(sum(used.values()))
        if share < 0.9:
            print("  %-24s -> %-22s доля формы %.0f%%  %s"
                  % (term, ru, share * 100, dict(used.most_common(3))))


if __name__ == "__main__":
    main()
