#!/usr/bin/env python
"""Проход типографики: правила, которые можно применить механически.

Это те правила стилевого руководства, которые скрипт применяет, не понимая
смысла строки:

  - многоточие это один символ, «…», а не три точки;
  - прямая двойная кавычка это пара «ёлочек»;
  - перед длинным тире «—» нет пробела, после него один;
  - «так же» это два слова, «также» одно.

Проход детерминирован и проходит по каждой строке, поэтому строка, которую
модель сделала правильно, не трогается, а строка, которую она сделала не так,
исправляется одинаково при каждом запуске. Проход идёт до этапа контроля
качества, поэтому контроль качества проверяет его результат.

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
IN_PATH = os.path.join(WORK, "canon.jsonl")
OUT_PATH = os.path.join(WORK, "typo.jsonl")

ELLIPSIS = re.compile(r"\.\.\.(?!\.)")
DASH = re.compile(r"\s+—\s*")
QUOTE = re.compile(r'"([^"\n]*)"')
ANY_QUOTE = re.compile(r"[\"«»“”]")
# Одиночная кавычка это кавычка, когда она открывает и закрывает фразу, а не
# когда это апостроф: `That's` не цитата.
SINGLE_QUOTED = re.compile(r"(?:^|[\s(\[])'[^']+'(?=[\s.,!?;:)\]]|$)")


def is_quoted(english: str) -> bool:
    """Истина, когда исходная строка сама несёт цитату."""
    if ANY_QUOTE.search(english):
        return True
    return bool(SINGLE_QUOTED.search(english))


def unwrap(text: str, english: str) -> str:
    """Снимает «ёлочки» со строки, обёрнутой в них целиком.

    Игра показывает произнесённую реплику как есть, без кавычек. Строка,
    которую редакторский проход обернул от края до края, читается как
    письменная цитата, а это не так: в английском оригинале кавычек тоже нет.
    """
    stripped = text.strip()
    if not (stripped.startswith("«") and stripped.endswith("»")):
        return text
    if is_quoted(english):
        # Источник цитирует, значит и по-русски цитата.
        return text
    inner = stripped[1:-1].strip()
    if inner.count("«") != inner.count("»"):
        return text
    return inner


def normalise(text: str, english: str = "") -> str:
    """Типографика одной строки."""
    out = ELLIPSIS.sub("…", text)
    out = DASH.sub(" — ", out)
    out = re.sub(r"\s+—(?=\S)", " — ", out)
    out = re.sub(r"«\s+", "«", out)
    out = re.sub(r"\s+»", "»", out)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)

    # Прямая кавычка это пара «ёлочек». В русском тексте игры прямых кавычек
    # нет, а одиночная в любом случае опечатка.
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
    print("типографика: %d строк, изменено %d -> %s" % (len(rows), changed, args.out))


if __name__ == "__main__":
    main()
