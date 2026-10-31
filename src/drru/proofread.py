#!/usr/bin/env python
"""Проход вычитки: каждая строка перевода читается против источника.

Редакторский проход приводит перевод к единому голосу. Этот проход ищет
другой вид дефекта: строка, которая говорит не то, что говорит английский
текст, строка, потерявшая факт, строка, сохранившая слово источника, которое
следовало перевести, строка, оборванная на полуслове.

Это ещё и измерение, а не оракул: модель просят назвать строки, в которых
она сомневается, и сказать почему, и каждую названную строку читают здесь,
до того как она изменена. Строка, в которой модель сомневается, а источник
этого не подтверждает, остаётся как есть.

    python3 src/drru/proofread.py
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drru import batch, corpus  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORK = os.path.join(ROOT, "work", "corpus")

IN_PATH = os.path.join(WORK, "polish.jsonl")
OUT_PATH = os.path.join(WORK, "proofread.jsonl")
REPORT_PATH = os.path.join(WORK, "proofread.json")

SYSTEM = """Ты вычитчик русского перевода игры The Drifter.

Тебе дают английскую строку игры и её русский перевод. Найди строки, где перевод расходится с оригиналом.

Ищи ТОЛЬКО:
1. Смысл изменён: в переводе сказано не то, что в оригинале, или добавлено то, чего в оригинале нет.
2. Потерян факт: число, имя, место, действие, отрицание.
3. Оставлено английское слово там, где его надо было перевести.
4. Перевод обрезан: фраза не закончена, в конце обрывок или посторонняя буква.
5. Чужая алфавитная вставка: в русском тексте иероглифы или другие буквы.
6. Перевод пустой или совпадает с оригиналом, хотя в оригинале есть слова.

НЕ ИЩИ: стиль, тон, кальки, опечатки, спорные формулировки. Это работа редакторского прохода, не твоя.

ФОРМАТ ОТВЕТА: JSON-массив объектов, по одному на сомнительную строку:
{"id": N, "why": "кратко по-русски, что не так", "fix": "исправленный русский текст"}
Если сомнительных строк нет, верни пустой массив []. Не выдумывай замечания."""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.environ.get("DRRU_MODEL", "minimax-m3"))
    parser.add_argument("--source", default=IN_PATH)
    parser.add_argument("--out", default=OUT_PATH)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows = corpus.read_jsonl(args.source)
    if args.limit:
        rows = rows[:args.limit]

    batches = []
    current = []
    chars = 0
    for row in rows:
        current.append(row)
        chars += len(row["en"]) + len(row["ru"])
        if len(current) >= 30 or chars >= 3000:
            batches.append(current)
            current = []
            chars = 0
    if current:
        batches.append(current)

    def make_job(index, rows_in_batch):
        def job():
            payload = [{"id": n, "en": row["en"], "ru": row["ru"]}
                       for n, row in enumerate(rows_in_batch)]
            replies = batch.call_report(args.model, SYSTEM, payload,
                                        temperature=0.1, tag="proof")
            if replies is None:
                return []
            out = []
            for reply in replies:
                if not isinstance(reply, dict):
                    continue
                try:
                    n = int(reply.get("id", -1))
                except Exception:
                    continue
                if not (0 <= n < len(rows_in_batch)):
                    continue
                out.append({
                    "key": corpus.key_of(rows_in_batch[n]),
                    "en": rows_in_batch[n]["en"],
                    "ru": rows_in_batch[n]["ru"],
                    "why": reply.get("why", ""),
                    "fix": reply.get("fix", ""),
                })
            return out
        return job

    jobs = [make_job(i, b) for i, b in enumerate(batches)]
    results = batch.run_parallel(jobs)

    findings = []
    for result in results:
        if result:
            findings.extend(result)

    with io.open(OUT_PATH, "w", encoding="utf-8", newline="") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with io.open(REPORT_PATH, "w", encoding="utf-8") as fh:
        json.dump(findings, fh, ensure_ascii=False, indent=2)

    print("вычитка: %d строк, %d строк к прочтению" % (len(rows), len(findings)))
    for finding in findings[:40]:
        print("  [%s] %s" % (finding["key"], finding["why"]))
        print("     EN: %s" % finding["en"][:110])
        print("     RU: %s" % finding["ru"][:110])
    if len(findings) > 40:
        print("  ... ещё %d" % (len(findings) - 40))


if __name__ == "__main__":
    main()
