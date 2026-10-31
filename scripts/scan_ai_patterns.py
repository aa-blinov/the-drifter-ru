#!/usr/bin/env python3
"""Look for the traces of AI writing in the Russian localization.

The list of patterns is the one of the `humanizer` skill, translated into
Russian. The check is a measurement, not a rule: a line that matches is a
line to read, and the line next to it in the English source says whether the
word comes from the game or from the translation.

    python3 scripts/scan_ai_patterns.py
    python3 scripts/scan_ai_patterns.py --verbose
"""
from __future__ import annotations

import collections
import csv
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")
CORPUS = os.path.join(ROOT, "corpus", "english.csv")

# The patterns of the humanizer skill, in Russian.
PATTERNS = [
    "стоит отметить", "следует отметить", "важно отметить", "стоит сказать",
    "достаточно сказать", "нельзя не отметить",
    "на самом деле", "по большому счёту", "по большому счету", "в конечном итоге",
    "в конечном счёте", "в конечном счете", "подводя итог", "вот в чём дело",
    "вот в чем дело", "в сущности", "по сути", "если разобраться",
    "не просто", "не только",
    "давайте", "итак,", "поговорим о том",
    "эксперты считают", "эксперты отмечают", "исследователи отмечают",
    "исследователи считают", "многие полагают", "считается, что",
    "по мнению экспертов", "как полагают",
    "важнейшая роль", "ключевая роль", "играет ключевую", "подчёркивает",
    "подчеркивает", "неотъемлемая часть", "неотъемлемой", "неотъемлемым",
    "открывает новые горизонты", "воплощает в себе", "служит символом",
    "символизирует",
    "в определённой степени", "в определенной степени", "в значительной степени",
    "в той или иной степени", "может быть, возможно", "вполне возможно",
    "есть основания полагать", "можно предположить",
    "по состоянию на", "в настоящее время", "информация ограничена",
    "служит в качестве", "выступает в качестве", "представляет собой",
    "не следует считать", "не хочу сказать", "я не утверждаю",
    "естественным образом", "вполне естественно", "само собой разумеется",
    "впереди большие возможности", "время покажет",
    "иными словами", "другими словами", "проще говоря", "говоря проще",
    "имеет место", "это очевидно", "очевидно, что", "нельзя забывать",
    "трудно не заметить", "без преувеличения", "не случайно",
    "как ни странно", "так или иначе", "остаётся только", "остается только",
]

# The connectives, with the words the English source uses for them.
CONNECTIVES = [
    ("и это", "and it"), ("на самом деле", "actually"), ("по сути", "essentially"),
    ("итак", "so"), ("давайте", "let's"), ("не просто", "not just"),
    ("не только", "not only"), ("в конечном счёте", "ultimately"),
    ("в сущности", "in fact"), ("как ни странно", "strangely enough"),
    ("очевидно", "obvious"), ("время покажет", "time will tell"),
    ("иными словами", "in other words"), ("вот в чём дело", "here's the thing"),
]


def rows_of(path):
    """Every (key, english, russian) of the translation."""
    if not os.path.exists(path):
        return
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.reader(fh))
    if not table:
        return
    head = table[0]
    en_col = head.index("English")
    ru_col = head.index("Русский")
    for row in table[1:]:
        if len(row) > max(en_col, ru_col):
            yield ("%s|%s" % (row[0], row[1]), row[en_col], row[ru_col])


def main():
    verbose = "--verbose" in sys.argv
    hits = collections.defaultdict(list)
    ru_chars = 0
    rows = 0
    for key, english, russian in rows_of(TRANSLATION):
        if not russian:
            continue
        rows += 1
        ru_chars += len(russian)
        low = russian.lower()
        for pattern in PATTERNS:
            if pattern in low:
                hits[pattern].append((key, russian, english))

    total = sum(len(v) for v in hits.values())
    report = ["rows: %d, characters: %d" % (rows, ru_chars),
              "lines with a pattern: %d" % total, ""]
    for pattern, lines in sorted(hits.items(), key=lambda kv: -len(kv[1])):
        report.append("%5d  %s" % (len(lines), pattern))
    report.append("")

    if verbose:
        for pattern, lines in sorted(hits.items(), key=lambda kv: -len(kv[1])):
            report.append("=== %s (%d)" % (pattern, len(lines)))
            for key, ru, source in lines:
                report.append("  [%s]" % key)
                report.append("    RU: %s" % ru.replace("\n", " / ")[:160])
                if source:
                    report.append("    EN: %s" % source.replace("\n", " / ")[:160])
            report.append("")

    ru_dash = 0
    en_dash = 0
    en_chars = 0
    for _key, english, russian in rows_of(TRANSLATION):
        ru_dash += russian.count("—") + russian.count("–")
        en_dash += english.count("—") + english.count("–")
        en_chars += len(english)
    report.append("em dashes per 1000 characters:")
    report.append("  RU %.3f" % (1000.0 * ru_dash / max(ru_chars, 1)))
    report.append("  EN %.3f" % (1000.0 * en_dash / max(en_chars, 1)))

    report.append("")
    report.append("connectives per 1000 characters:")
    ru_all = [t.lower() for _k, _e, t in rows_of(TRANSLATION)]
    en_all = [e.lower() for _k, e, _t in rows_of(TRANSLATION)]
    for ru_pat, en_pat in CONNECTIVES:
        rc = sum(len(re.findall(r"\b%s" % re.escape(ru_pat), t)) for t in ru_all)
        ec = sum(len(re.findall(r"\b%s" % re.escape(en_pat), t)) for t in en_all)
        report.append("  %-18s RU %5.3f   EN %5.3f"
                      % (ru_pat, 1000.0 * rc / max(ru_chars, 1),
                         1000.0 * ec / max(en_chars, 1)))

    out = "\n".join(report)
    print(out)
    path = os.path.join(ROOT, "work", "ai_scan.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(out)


if __name__ == "__main__":
    main()
