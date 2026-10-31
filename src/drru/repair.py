#!/usr/bin/env python
"""Этап починки: строки, которые не вернулись.

Батч может вернуться коротким, а отдельная строка может не сработать сама
по себе: модель отказывается переводить длинное описание предмета, или ответ
обрывается посередине. Причина не важна, строка всё равно отсутствует, а
отсутствующая строка это дыра в игре.

Этот этап просит недостающие строки заново, по одной, коротким промптом,
который просит только перевод одной строки. У одной строки нет места, где
модель её потеряет.

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

Правила: нуарный тон, повествование от первого лица, маты по силе, кавычки-ёлочки, тире «—»: в скобочной конструкции с пробела с обеих сторон, в разрыве фразы без пробела, тире примыкает к слову, многоточие «…». Плейсхолдер {0} переноси как есть. Ничего не выдумывай.
"""


def repair_line(model: str, english: str, glossary) -> str:
    """Одна строка, запрошенная отдельно."""
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
        # Модель иногда отвечает на запрос одной строки самой строкой,
        # без JSON-обёртки. Это пригодный ответ.
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
        batch.log("починка: ничего не отсутствует")
        return

    batch.log("починка: строк к починке %d" % len(missing))
    for row in missing:
        row["ru"] = repair_line(args.model, row["en"], glossary)
        batch.log("  %s|%s -> %s" % (row["character"], row["id"], row["ru"][:60]))

    still = [row for row in missing if not row["ru"].strip()]
    if still:
        batch.log("починка: %d строк так и не вернулись" % len(still))
        for row in still:
            batch.log("  %s|%s: %s" % (row["character"], row["id"], row["en"][:80]))

    out = args.out or args.source
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    batch.log("починка: записано %d строк -> %s" % (len(rows), out))


if __name__ == "__main__":
    main()
