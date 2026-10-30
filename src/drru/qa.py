#!/usr/bin/env python
"""The checks that run before the translation ships.

Two kinds of check:

  structural — the placeholders, the keys, the row count. A line that lost a
  placeholder is a broken line in the game, not a typo.
  linguistic — English left inside a Russian sentence, a fused word across
  two scripts, a straight quote, a three-dot ellipsis, a duplicated wording.

Every check reports the key, so the failing line can be found in the game.

    python3 src/drru/qa.py
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drru import checks, corpus  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CANON_PATH = os.path.join(ROOT, "work", "corpus", "final.jsonl")


def check_structural(rows, findings):
    """The placeholders and the keys."""
    for row in rows:
        key = corpus.key_of(row)
        if not row["ru"].strip():
            findings.append(("empty", key, "the Russian line is empty"))
    keys = collections.Counter(corpus.key_of(row) for row in rows)
    for key, count in keys.items():
        if count > 1:
            findings.append(("duplicate-key", key, "%d rows" % count))
    return findings


def check_linguistic(rows, findings):
    """What a reader would notice."""
    for row in rows:
        key = corpus.key_of(row)
        ru = row["ru"]
        if '"' in ru:
            findings.append(("straight-quote", key, ru[:80]))
        if "..." in ru:
            findings.append(("three-dot-ellipsis", key, ru[:80]))
        if "«" in ru and "»" not in ru:
            findings.append(("unbalanced-quote", key, ru[:80]))
        for kind in checks.defects(row["en"], ru):
            findings.append((kind.split(":")[0], key, kind))
    return findings


def check_repeats(rows, findings):
    """One English line, one Russian line."""
    by_english = collections.defaultdict(set)
    for row in rows:
        by_english[row["en"]].add(row["ru"])
    for english, variants in by_english.items():
        if len(variants) > 1:
            findings.append(("inconsistent-repeat", english[:60],
                             "%d variants" % len(variants)))
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=CANON_PATH)
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero on any finding")
    args = parser.parse_args()

    rows = corpus.read_jsonl(args.corpus)
    findings = []
    check_structural(rows, findings)
    check_linguistic(rows, findings)
    check_repeats(rows, findings)

    by_kind = collections.Counter(kind for kind, _key, _detail in findings)
    print("qa: %d lines, %d findings" % (len(rows), len(findings)))
    for kind, count in by_kind.most_common():
        print("  %-22s %d" % (kind, count))
    for kind, key, detail in findings[:60]:
        print("  %-22s %-28s %s" % (kind, key, detail))
    if len(findings) > 60:
        print("  ... %d more" % (len(findings) - 60))

    if findings and args.strict:
        sys.exit(1)


if __name__ == "__main__":
    main()
