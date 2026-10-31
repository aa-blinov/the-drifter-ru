#!/usr/bin/env python
"""Check that the glossary holds: one term, one word.

The glossary says that a name has one Russian form. The check reads every
line of the translation that mentions the term in the English source and
looks at the Russian words that stand in its place. A term whose lines use
two different Russian words is a term that has drifted, and that is a
defect: the player reads the same person under two names.

The Russian case endings are not a drift: «Рот», «Рота» и «Ротом» are one
word. The check compares the stems, not the forms.

    python3 scripts/check_terms.py
    python3 scripts/check_terms.py --verbose
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
TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")
GLOSSARY = os.path.join(ROOT, "src", "voice", "glossary.json")

RU_WORD = re.compile(r"[А-Яа-яЁё][А-Яа-яЁё\-]*")
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z0-9\-]*")
TOKEN = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+")


def same_word(a: str, b: str) -> bool:
    """Two Russian words are one word written in two cases.

    «Рот», «Рота» и «Ротом» are one name; «Хара» и «Хары» are one name.
    The endings change, the stem does not. The two words are the same when
    they share all but the last two characters, and when the shorter one is
    at least three characters long — short enough not to merge two
    different names, long enough to tell «Сара» from «Сары».
    """
    a = a.lower()
    b = b.lower()
    if a == b:
        return True
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    shorter = min(len(a), len(b))
    return common >= 3 and common >= shorter - 2


def has_term(english: str, term: str) -> bool:
    """The line of the source mentions the term.

    The match is on the word, not on the letters: «Anne» is a name, and
    «scanner» is not a mention of it. The possessive is part of the term:
    «Mick's» is the mention of «Mick». A name is matched as it is written,
    with its capital, so that «bill» — the bank statement — is not a
    mention of «Bill» the man.
    """
    pattern = r"(?<![A-Za-z'])" + re.escape(term).replace(r"\'", "'")
    pattern = pattern + r"(?:'s|’s)?(?![A-Za-z])"
    flags = 0 if term[:1].isupper() else re.IGNORECASE
    if term in ("EM", "em"):
        # «'em» is the contraction of «them», not the abbreviation.
        pattern = r"(?<![A-Za-z'])EM(?![A-Za-z])"
    if term in ("End Ch.", "HD Dialogue Font", "hd font"):
        # A label of the interface: it is written in one case in the source
        # and in the other in the translation, and it is the same label.
        flags = re.IGNORECASE
    return re.search(pattern, english, flags) is not None


def phrase_in(words, phrase) -> bool:
    """The phrase of the glossary is in the line, case endings apart.

    The line and the phrase are both cut into words, and the punctuation is
    dropped: the game writes «С-Смертельное согласие» where the source says
    «D- Deadly Consent», and the hyphen there is not part of the name.
    """
    wanted = TOKEN.findall(phrase)
    if not wanted:
        return False
    if len(wanted) == 1:
        return any(same_word(word, wanted[0]) for word in words)
    for start in range(len(words) - len(wanted) + 1):
        chunk = words[start:start + len(wanted)]
        if all(same_word(a, b) for a, b in zip(chunk, wanted)):
            return True
    return False


def rows_of(path):
    """Every (english, russian) of the translation."""
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
            yield row[en_col], row[ru_col]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    glossary = json.load(io.open(GLOSSARY, encoding="utf-8"))

    # Only the terms that are names are checked. An ordinary word has many
    # fair Russian renderings — «back» is «назад» in one line and «спина»
    # in the next — and a check over them would drown the real findings.
    glossary = {term: ru for term, ru in glossary.items()
                if (ru[:1].isupper() or " " in ru) and term[:1].isupper()}

    # the Russian words each English term is rendered by
    rendered = collections.defaultdict(collections.Counter)
    examples = collections.defaultdict(dict)
    # the lines where the term is in the source but its Russian form is not
    absent = collections.defaultdict(list)
    for english, russian in rows_of(TRANSLATION):
        if not english or not russian:
            continue
        words = TOKEN.findall(russian)
        for term, ru in glossary.items():
            if not has_term(english, term):
                continue
            # The Russian words that stand in the place of the term are
            # found by their stems, because the case endings change: «Рот»,
            # «Рота» and «Ротом» are one word.
            if phrase_in(words, ru):
                key = ru.lower()
                rendered[term][key] += 1
                examples[term].setdefault(key, russian)
            else:
                # The term is in the source and its words are not in the
                # translation: the term was rendered another way.
                absent[term].append((english, russian))

    drifted = []
    for term, forms in sorted(rendered.items()):
        # The forms of one word are one drift: «Хара», «Хары» и «Харе»
        # are the case endings of one name.
        clusters = []
        for form in forms:
            for group in clusters:
                if same_word(form, group[0]):
                    group.append(form)
                    break
            else:
                clusters.append([form])
        if len(clusters) > 1:
            drifted.append((term, glossary[term], clusters, examples))

    print("terms checked: %d" % len(rendered))
    print("terms with more than one Russian form: %d" % len(drifted))
    for term, ru, clusters, samples in drifted:
        print("  %-24s -> %-22s %s" % (
            term, ru, " | ".join(", ".join(group) for group in clusters)))
        if args.verbose:
            for group in clusters:
                for form in group:
                    print("      %s: %s" % (form, samples.get(form, "")[:90]))

    # The lines where the term is in the source but its Russian words are
    # not in the translation: either the term was rendered another way, or
    # the term is not rendered at all.
    print("terms rendered another way: %d" % len(absent))
    for term, lines in sorted(absent.items()):
        print("  %-24s -> %-22s %d line(s)" % (term, glossary[term], len(lines)))
        if args.verbose:
            for english, russian in lines[:6]:
                print("      EN: %s" % english[:88])
                print("      RU: %s" % russian[:88])

    if drifted or absent:
        sys.exit(1)


if __name__ == "__main__":
    main()
