#!/usr/bin/env python
"""The repair stage: the lines that did not come back.

A batch can come back short, and a single line can fail on its own — the
model refuses a long description of an item, or the reply is cut in the
middle. Whatever the cause, the line is still missing, and a missing line is
a hole in the game.

This stage asks for the missing lines again, one at a time, with a short
prompt that asks for nothing but the translation of one string. A single line
has no room for the model to lose it.

    python3 src/drru/repair.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drru import batch, corpus, llm_client  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORK = os.path.join(ROOT, "work", "corpus")

SYSTEM = """Ты переводишь одну строку игры The Drifter на русский.

Верни ТОЛЬКО перевод, без кавычек, без нумерации, без пояснений: JSON-массив из одной строки.

Правила: нуарный тон, повествование от первого лица, маты по силе, кавычки-ёлочки, тире «—» без пробела, многоточие «…». Плейсхолдер {0} переноси как есть. Ничего не выдумывай.
"""


def repair_line(model: str, english: str, glossary) -> str:
    """One line, asked for on its own."""
    system = SYSTEM + batch.format_glossary(
        batch.glossary_for([english], glossary, limit=12))
    user = json.dumps([english], ensure_ascii=False)
    key = "repair2|%s|%s" % (model, user)
    for attempt in range(4):
        try:
            text = llm_client.call_llm(model, system, user, max_tokens=2000,
                                       temperature=0.2, cache_key=key)
        except Exception:
            continue
        parsed = llm_client.extract_json_array(text)
        if parsed and len(parsed) == 1 and isinstance(parsed[0], str):
            candidate = parsed[0].strip()
            if candidate:
                return candidate
        # The model sometimes answers a one-line request with the line
        # itself, without the JSON wrapper. That is a usable answer.
        bare = text.strip().strip('"').strip()
        if bare and "\n" not in bare:
            return bare
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.environ.get("DRRU_MODEL", "minimax-m3"))
    parser.add_argument("--source", default=os.path.join(WORK, "bulk.jsonl"))
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    rows = corpus.read_jsonl(args.source)
    glossary = batch.load_glossary()
    missing = [row for row in rows if not row.get("ru", "").strip()]

    if not missing:
        batch.log("repair: nothing is missing")
        return

    batch.log("repair: %d lines to repair" % len(missing))
    for row in missing:
        row["ru"] = repair_line(args.model, row["en"], glossary)
        batch.log("  %s|%s -> %s" % (row["character"], row["id"], row["ru"][:60]))

    still = [row for row in missing if not row["ru"].strip()]
    if still:
        batch.log("repair: %d lines still did not come back" % len(still))
        for row in still:
            batch.log("  %s|%s: %s" % (row["character"], row["id"], row["en"][:80]))

    out = args.out or args.source
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    batch.log("repair: wrote %d lines -> %s" % (len(rows), out))


if __name__ == "__main__":
    main()
