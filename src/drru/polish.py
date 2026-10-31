#!/usr/bin/env python
"""Этап полировки: строки, которые проверки нашли сломанными.

Этап контроля качества сообщает о строках с дефектом: слово, склеенное из
двух алфавитов, английское слово внутри русского предложения, потерянный
плейсхолдер, сырой фрагмент JSON на месте строки текста.

Этот этап берёт такие строки и просит их заново, по одной, с названным
дефектом. Строка, которая вернулась с тем же дефектом, остаётся как есть и
попадает в отчёт, потому что второй неверный ответ хуже известного дефекта.

    python3 src/drru/polish.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drru import batch, checks, corpus, llm_client  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORK = os.path.join(ROOT, "work", "corpus")
IN_PATH = os.path.join(WORK, "typo.jsonl")
OUT_PATH = os.path.join(WORK, "polish.jsonl")

PLACEHOLDER = re.compile(r"\{[^}]*\}")
FUSED = re.compile(r"[А-Яа-яЁё][A-Za-z]{2,}|[A-Za-z]{2,}[А-Яа-яЁё]")
LATIN_WORD = re.compile(r"[A-Za-z]{3,}")

SYSTEM = """Ты корректор русского перевода игры The Drifter.

Тебе дают английскую строку и её перевод, в котором есть дефект. Верни исправленный перевод.

Требования:
- Смысл, объём и характер говорящего сохраняются.
- Плейсхолдеры {0} переносятся как есть.
- Никаких английских слов, кроме имён и терминов из глоссария: Mick, Roth, Hara, Klein, Trinity Biotech, Mulindji, MedCon, Quantum Cognition, Zippo, Tab, GUI, HDD и подобных.
- Никаких слов, склеенных из русского и английского.
- Кавычки-ёлочки, тире «—»: в скобочной конструкции с пробела с обеих сторон, в разрыве фразы без пробела, тире примыкает к слову, многоточие «…» одним символом.
- Никаких кальки и канцелярита: нуарный тон, сухо, от первого лица.

ФОРМАТ ОТВЕТА: JSON-массив из одной строки: только перевод, без пояснений.
"""



# Слово внутри тега разметки, URL или имени не дефект: такие остаются
# латиницей намеренно.
KEPT = re.compile(r"<[^>]*>|https?://\S*|[\w-]+(?:\.[\w-]+){2,}\b|[\w-]+\.(?:com|org|net|gg|io|ru)\b\S*|\[[A-Z]{1,6}\]")
JSON_BLOB = re.compile(r'\{\s*"id"\s*:')


def strip_kept(text: str) -> str:
    """Текст без частей, которые намеренно оставлены латиницей."""
    return KEPT.sub(" ", text)


def defects(row):
    """Что не так с этой строкой."""
    return checks.defects(row["en"], row["ru"])


def ask(model: str, row, glossary) -> str:
    """Одна строка, запрошенная заново с названным дефектом."""
    found = defects(row)
    system = SYSTEM + batch.format_glossary(
        batch.glossary_for([row["en"]], glossary, limit=10))
    user = ("АНГЛИЙСКИЙ: %s\n\nТЕКУЩИЙ ПЕРЕВОД: %s\n\nДЕФЕКТ: %s\n\n"
            % (json.dumps(row["en"], ensure_ascii=False),
               json.dumps(row["ru"], ensure_ascii=False),
               "; ".join(found)))
    key = "polish2|%s|%s" % (model, user)
    for attempt in range(3):
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
        bare = text.strip().strip('"').strip()
        if bare and "\n" not in bare:
            return bare
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.environ.get("DRRU_MODEL", "minimax-m3"))
    parser.add_argument("--source", default=IN_PATH)
    parser.add_argument("--out", default=OUT_PATH)
    args = parser.parse_args()

    rows = corpus.read_jsonl(args.source)
    glossary = batch.load_glossary()
    broken = [row for row in rows if defects(row)]
    batch.log("полировка: %d строк с дефектом" % len(broken))

    fixed = 0
    still = []
    for row in broken:
        candidate = ask(args.model, row, glossary)
        if not candidate:
            still.append(row)
            continue
        probe = dict(row)
        probe["ru"] = candidate
        if defects(probe):
            still.append(probe)
            batch.log("  %s|%s: дефект остался" % (row["character"], row["id"]))
            continue
        row["ru"] = candidate
        fixed += 1
        batch.log("  %s|%s -> %s" % (row["character"], row["id"], candidate[:60]))

    batch.log("полировка: исправлено %d, с дефектом осталось %d" % (fixed, len(still)))
    for row in still:
        batch.log("  %s|%s: %s" % (row["character"], row["id"], "; ".join(defects(row))))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    batch.log("полировка: записано %d строк -> %s" % (len(rows), args.out))


if __name__ == "__main__":
    main()
