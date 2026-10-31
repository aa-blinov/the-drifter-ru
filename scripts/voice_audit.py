#!/usr/bin/env python
"""Аудит голоса: где перевод суше, чем источник.

Вычитка проверяет смысл и факты. Этот скрипт проверяет другое: читается ли
русская строка так же живо, как английская. Нуарный текст, переведённый
ровно, но без интонации, читается как протокол.

Скрипт идёт по корпусу батчами, как и пайплайн, и спрашивает модель про
каждую строку вместе с её источником. Ответ — список находок: строка,
причина и предложение. Находки пишутся в work/voice_audit.jsonl, решение
по ним принимает человек.

    python3 scripts/voice_audit.py                  # весь корпус
    python3 scripts/voice_audit.py --limit 3        # первые три батча
    python3 scripts/voice_audit.py --only Narr      # только повествование
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from src.drru import batch, corpus, llm_client  # noqa: E402

TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")
OUT = os.path.join(ROOT, "work", "voice_audit.jsonl")

SYSTEM = """Ты читаешь русский перевод игры The Drifter и ищешь строки, где перевод
потерял голос. Игра noir: нуарный детектив от Powerhoof, повествование от
первого лица, рассказчик усталый и циничный.

Отмечай строку только если выполнены оба условия:
1. В английском источнике есть оттенок: интонация, характер, усталость,
   сарказм, раздражение, нежность, ритм фразы.
2. В русском переводе этого оттенка нет, и строка от этого звучит плоско:
   как канцелярит, как доклад, как пересказ, как калька.

Не отмечай строку, если:
- она плоская и в источнике (короткий ответ, сухая реплика, описание);
- оттенок в переводе есть, пусть подан иначе;
- строка точна, калька работает, и менять её нечем;
- это описание предмета, подсказка интерфейса, вариант ответа или реплика
  без слов автора;
- тебе нечем объяснить потерю одним предложением.

Лучше пропустить строку, чем предложить переделку. Ошибка здесь дороже
пропуска: находок должно быть мало, и каждая должна быть настоящей.

Правка не должна менять смысл, факты, имена, числа, порядок событий и
плейсхолдеры. Правка не должна добавлять то, чего нет в источнике: только
интонация, ритм и разговорность. Если правка длиннее исходной строки в
полтора раза, она неудачная.

ФОРМАТ ОТВЕТА: JSON-массив объектов, по одному на каждую плоскую строку:
{"id": N, "почему": "одно предложение о потерянном оттенке",
 "правка": "исправленный русский текст"}
Если плоских строк нет, верни пустой массив.
"""

PAYLOAD = [{"id": 0, "en": "", "ru": ""}]


def load_rows() -> list:
    with io.open(TRANSLATION, encoding="utf-8-sig", newline="") as fh:
        import csv
        table = list(csv.reader(fh))
    header, rows = table[0], table[1:]
    en_col = header.index("English")
    ru_col = header.index("Русский")
    out = []
    for row in rows:
        out.append({
            "character": row[0],
            "id": row[1],
            "file": row[2],
            "context": row[3],
            "en": row[en_col],
            "ru": row[ru_col],
        })
    return out


def audit(model: str, rows_in_batch, tag: str):
    payload = [{"id": i, "en": r["en"], "ru": r["ru"]}
               for i, r in enumerate(rows_in_batch)]
    user = json.dumps(payload, ensure_ascii=False, indent=1)
    key = "%s|%s|%s" % (tag, model, user)
    text = llm_client.call_llm(model, SYSTEM, user, max_tokens=4000,
                               temperature=0.1, cache_key=key,
                               reasoning_effort="none")
    parsed = llm_client.extract_json_array(text)
    if parsed is None:
        return []
    out = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        number = item.get("id")
        if not isinstance(number, int) or not (0 <= number < len(rows_in_batch)):
            continue
        row = rows_in_batch[number]
        out.append({
            "key": "%s|%s" % (row["character"], row["id"]),
            "character": row["character"],
            "id": row["id"],
            "file": row["file"],
            "context": row["context"],
            "en": row["en"],
            "ru": row["ru"],
            "why": str(item.get("почему", "")),
            "fix": str(item.get("правка", "")),
        })
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.environ.get("DRRU_MODEL", "minimax-m3"))
    parser.add_argument("--limit", type=int, default=0,
                        help="сколько батчей проверить (0 — все)")
    parser.add_argument("--only", default="",
                        help="только строки этого персонажа")
    parser.add_argument("--out", default=OUT)
    parser.add_argument("--tag", default="voice1",
                        help="метка кэша: новая метка означает новый вызов модели")
    args = parser.parse_args()

    rows = load_rows()
    if args.only:
        rows = [r for r in rows if r["character"] == args.only]
    batches = batch.make_batches(rows)
    if args.limit:
        batches = batches[:args.limit]
    batch.log("аудит голоса: %d строк, %d батчей" % (len(rows), len(batches)))

    findings = []

    def job(index, rows_in_batch):
        def run():
            found = audit(args.model, rows_in_batch, args.tag)
            for item in found:
                item["batch"] = index
            return found
        return run

    jobs = [job(i, b) for i, b in enumerate(batches)]
    for result in batch.run_parallel(jobs):
        if result:
            findings.extend(result)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        for item in findings:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    batch.log("аудит голоса: находок %d -> %s" % (len(findings), args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
