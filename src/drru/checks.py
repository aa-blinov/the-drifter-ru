#!/usr/bin/env python
"""The checks on one line of Russian text.

They live in one module because three places need them and they must agree:
the QA stage reports what is wrong, the polish stage fixes what is wrong, and
the tests check what was fixed.

A word in Latin is not a defect when it is a name, a brand, a part of the
game's own notation, a URL or a code identifier. The list of what is allowed
is a file, so the three places read the same one.
"""
from __future__ import annotations

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALLOWED_LATIN_PATH = os.path.join(ROOT, "src", "voice", "allowed_latin.json")

PLACEHOLDER = re.compile(r"\{[^}]*\}")
LATIN_WORD = re.compile(r"[A-Za-z]{3,}")
FUSED = re.compile(r"[А-Яа-яЁё][A-Za-z]{2,}|[A-Za-z]{2,}[А-Яа-яЁё]")
JSON_BLOB = re.compile(r'\{\s*"id"\s*:')

# The parts of a line that stay in Latin on purpose: a markup tag, a URL, a
# domain, the controller prompts of the interface.
KEPT = re.compile(r"<[^>]*>|https?://\S*|[\w-]+(?:\.[\w-]+){2,}\b"
                  r"|[\w-]+\.(?:com|org|net|gg|io|ru)\b\S*|\[[A-Z]{1,6}\]")

# A line the game shows as it is: an identifier, a number sequence, a key
# name. There is nothing to translate in them, and the tests must not claim
# otherwise.
DOMAIN = re.compile(r"https?://|\.[a-z]{2,4}\b")
CAMEL = re.compile(r"[a-z][A-Z]")
WORD = re.compile(r"[A-Za-z]{3,}")
# A run of lowercase letters of three or more is a word of a language. `Esc`
# and `R` are key names; `Jesus.` is a word.
LOWER_RUN = re.compile(r"[a-z]{3,}")


def load_allowed_latin() -> set:
    with open(ALLOWED_LATIN_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    words = set()
    for key, values in data.items():
        if key.startswith("_"):
            continue
        words.update(values)
    return words


ALLOWED_LATIN = load_allowed_latin()


def strip_kept(text: str) -> str:
    """The text with the parts that are Latin on purpose removed."""
    return KEPT.sub(" ", text)


def is_code(text: str) -> bool:
    """True when the line is an identifier and has nothing to translate.

    The game shows a few strings as they are: the name of a key, a button, a
    combination of digits, a domain. They are code, not prose, and a
    translation that leaves them alone is right.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if DOMAIN.search(stripped):
        return True
    # A name in camel case is a name: BtnContinue, TopicGauge, FlamerFire.
    if CAMEL.search(stripped):
        return True
    # A line of digits, punctuation and spaces carries no words.
    if not WORD.search(stripped):
        return True
    # A capitalised word with no lowercase run is a key name: Esc, R.
    if not LOWER_RUN.search(stripped):
        return True
    return False


def defects(en: str, ru: str):
    """The defects of one line, as a list of descriptions."""
    found = []
    if sorted(PLACEHOLDER.findall(en)) != sorted(PLACEHOLDER.findall(ru)):
        found.append("потерян плейсхолдер")
    if FUSED.search(ru):
        found.append("слово склеено из русского и английского")
    for word in LATIN_WORD.findall(strip_kept(ru)):
        if word not in ALLOWED_LATIN:
            found.append("английское слово внутри русской строки: %s" % word)
            break
    if JSON_BLOB.search(ru):
        found.append("вместо текста лежит фрагмент разметки")
    return found
