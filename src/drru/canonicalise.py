#!/usr/bin/env python
"""Канонизация: одна английская строка, одна русская строка.

Игра использует одну и ту же английскую строку в нескольких местах, и
перевод должен быть одинаковым во всех них. Редакторский проход может
оставить для одного источника два разных русских варианта, потому что видел
строки в разных батчах.

Этот этап собирает варианты каждой повторяющейся исходной строки и просит
модель выбрать одну формулировку, а затем применяет её везде. Это последний
этап, который трогает текст, поэтому ручная правка после него сохраняется.

    python3 src/drru/canonicalise.py
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drru import batch, corpus  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
EDIT_PATH = os.path.join(ROOT, "work", "corpus", "edit.jsonl")
OUT_PATH = os.path.join(ROOT, "work", "corpus", "canon.jsonl")

SYSTEM = """Ты редактор русского перевода игры The Drifter.

Тебе даны варианты перевода одной и той же английской строки. Выбери один вариант и верни его без изменений.

Критерии выбора, по порядку:
1. Совпадение с голосом: нуар, сухо, точно, без канцелярита и кальки.
2. Совпадение объёма с оригиналом: реплика не должна разрастаться.
3. Сохранение смысла: ни одна деталь оригинала не потеряна.
4. Разговорность, если реплика разговорная.

Если все варианты хороши, возьми самый короткий и самый естественный.

ФОРМАТ ОТВЕТА: вход это JSON-массив объектов {"id": N, "variants": ["...", "..."]}. Выход это JSON-массив строк РОВНО той же длины и порядка: выбранный вариант для каждой группы, без изменений.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.environ.get("DRRU_MODEL", "minimax-m3"))
    args = parser.parse_args()

    rows = corpus.read_jsonl(EDIT_PATH)
    groups = collections.OrderedDict()
    for row in rows:
        groups.setdefault(row["en"], []).append(row)

    conflicts = []
    for english, group in groups.items():
        variants = []
        for row in group:
            if row["ru"] not in variants:
                variants.append(row["ru"])
        if len(variants) > 1:
            conflicts.append((english, variants, group))

    batch.log("канонизация: %d разных строк, у %d больше одного варианта"
              % (len(groups), len(conflicts)))
    if not conflicts:
        _write(rows, OUT_PATH)
        return

    # Группы независимы, а короткий батч модель отвечает надёжнее, поэтому
    # они идут небольшими кусками.
    from drru.batch import call_split
    payload = [{"id": i, "variants": variants}
               for i, (_en, variants, _group) in enumerate(conflicts)]
    replies = call_split(args.model, SYSTEM, payload, temperature=0.2,
                          tag="canon", chunk=20)
    if replies is None:
        batch.log("канонизация: модель нарушила контракт, варианты оставлены как есть")
        _write(rows, OUT_PATH)
        return

    for (english, variants, group), chosen in zip(conflicts, replies):
        for row in group:
            row["ru"] = chosen
    _write(rows, OUT_PATH)


def _write(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    batch.log("канонизация: записано %d строк -> %s" % (len(rows), path))


if __name__ == "__main__":
    main()
