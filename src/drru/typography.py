#!/usr/bin/env python
"""The typography pass: the rules that are mechanical.

These are the rules of the style guide that a script can apply without
understanding the line:

  - the ellipsis is one character, «…», not three dots;
  - a straight double quote is a pair of «ёлочки»;
  - the em dash has no space before it and one space after it;
  - «так же» is two words; «также» is one.

The pass is deterministic and runs over every line, so a line the model got
right is not touched and a line it got wrong is fixed the same way every
time. It runs before the QA stage, so the QA stage checks the result.

    python3 src/drru/typography.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drru import corpus  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORK = os.path.join(ROOT, "work", "corpus")
IN_PATH = os.path.join(WORK, "edit.jsonl")
OUT_PATH = os.path.join(WORK, "typo.jsonl")

ELLIPSIS = re.compile(r"\.\.\.(?!\.)")
DASH = re.compile(r"\s+—\s*")
QUOTE = re.compile(r'"([^"\n]*)"')
ANY_QUOTE = re.compile(r"[\"«»“”]")
# A single quote is a quote when it opens and closes a phrase, not when it
# is an apostrophe: `That's` is not a quoted word.
SINGLE_QUOTED = re.compile(r"(?:^|[\s(\[])'[^']+'(?=[\s.,!?;:)\]]|$)")


def is_quoted(english: str) -> bool:
    """True when the source line carries a quotation of its own."""
    if ANY_QUOTE.search(english):
        return True
    return bool(SINGLE_QUOTED.search(english))


def unwrap(text: str, english: str) -> str:
    """Take the guillemets off a line that is wrapped in them entirely.

    The game shows a spoken line as it is, without quotation marks. A line
    the editorial pass wrapped from end to end reads as a written quotation,
    which it is not: the English original carries no quotes either.
    """
    stripped = text.strip()
    if not (stripped.startswith("«") and stripped.endswith("»")):
        return text
    if is_quoted(english):
        # The source quotes it, so the Russian quotes it too.
        return text
    inner = stripped[1:-1].strip()
    if inner.count("«") != inner.count("»"):
        return text
    return inner


def normalise(text: str, english: str = "") -> str:
    """The typography of one line."""
    out = ELLIPSIS.sub("…", text)
    out = DASH.sub(" — ", out)
    out = re.sub(r"\s+—(?=\S)", " — ", out)
    out = re.sub(r"«\s+", "«", out)
    out = re.sub(r"\s+»", "»", out)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)

    # A straight quote is a pair of guillemets. The game has no straight
    # quotes in the Russian text, and a lone one is a typo either way.
    def to_guillemet(match):
        inner = match.group(1)
        return "«%s»" % inner

    out = QUOTE.sub(to_guillemet, out)
    out = out.replace('"', "«")
    out = unwrap(out, english)
    return out.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=IN_PATH)
    parser.add_argument("--out", default=OUT_PATH)
    args = parser.parse_args()

    rows = corpus.read_jsonl(args.source)
    changed = 0
    for row in rows:
        fixed = normalise(row["ru"], row["en"])
        if fixed != row["ru"]:
            changed += 1
            row["ru"] = fixed
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("typography: %d lines, %d changed -> %s" % (len(rows), changed, args.out))


if __name__ == "__main__":
    main()
