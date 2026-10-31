#!/usr/bin/env python
"""The translation stage: English corpus in, Russian corpus out.

Two passes over the corpus, in this order:

  1. the bulk pass, which translates;
  2. the editorial pass, which brings the translation to one voice.

The editorial pass reads the bulk output and the English source of the same
batch, so it can tell a calque from a deliberate choice. It is also given
the tail of the previous batch, so the voice established in one batch
propagates into the next instead of each batch deciding on its own.

    python3 src/drru/translate.py --stage bulk
    python3 src/drru/translate.py --stage editorial
    python3 src/drru/translate.py --stage all
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

BULK_PATH = os.path.join(WORK, "bulk.jsonl")
EDIT_PATH = os.path.join(WORK, "edit.jsonl")
MANUAL_PATH = os.path.join(ROOT, "src", "voice", "manual_fixes.json")

BULK_SYSTEM = """Ты — переводчик игры The Drifter на русский.

ЖЁСТКИЕ ПРАВИЛА:
1. Вход — JSON-массив английских строк. Выход — JSON-массив русских строк РОВНО той же длины и в том же порядке. Больше ничего: ни нумерации, ни комментариев, ни markdown-обёрток.
2. Плейсхолдеры {0} переноси как есть, без изменений. Ничего не выдумывай: не добавляй имён, фактов, пояснений и оценочных слов, которых нет в оригинале.
3. Тон: нуар, сухо, устало, с чёрным юмором. Повествование от первого лица («я»). Реплики — живая разговорная речь, характер говорящего сохраняется.
4. Маты переводятся по силе: «shit» — « дерьмо » или « чёрт », а не « фигня ».
5. Одно и то же слово переводится одним и тем же способом по всему тексту. Один английский текст — один русский вариант.
6. Кавычки-ёлочки «», тире «—» без пробела перед ним, многоточие «…» одним символом.
7. Никаких английских слов в переводе, кроме имён и терминов из глоссария.
"""

EDITORIAL_SYSTEM = """Ты — литературный редактор русского перевода игры The Drifter.

Для каждой строки:
- сохрани смысл, объём, характер говорящего, плейсхолдеры и разметку;
- приведи строку к голосу, описанному ниже;
- если строка уже в голосе — верни её без изменений;
- не переводи заново то, что уже хорошо переведено.

ТОН: нуар, сухо, устало, цинично. Переводчик не шутит и не подмигивает: ирония держится на словах. Никакого пафоса, никакого панибратства, никакого сленга, которого нет в оригинале. Маты по силе, но не по количеству.

ПОВЕСТВОВАНИЕ (строки персонажа Narr и строки без говорящего): от первого лица, «я». Прошедшее время для того, что уже случилось, настоящее для того, что происходит сейчас. Короткая фраза, потом длинная. Две соседние строки не начинаются одинаково. Точность важнее красоты. Никаких вводных оборотов.

ПРЯМАЯ РЕЧЬ: говорит живой человек. Реплики игрока короткие и обрывистые. Прямая речь внутри реплики — в «ёлочках».

ЕДИНЫЕ СЛОВА: имена, названия мест, клички и игровые термины — строго по глоссарию. Слово из глоссария не заменяй синонимом. Собственные имена транслитерируй: Mick — Мик, Roth — Рот, Hara — Хара, Klein — Кляйн.

ЗАПРЕЩЕНО: кальки («принять меры», «сделать решение», «быть в состоянии»), канцелярит («данный», «осуществлять», «являться»), дословная зеркальность. Шутка в оригинале остаётся шуткой, угроза — угрозой. Смысл не добавлять и не убирать.

ПУНКТУАЦИЯ: «ёлочки», тире «—» без пробела, многоточие «…» одним символом, точка перед закрывающей «ёлочкой». Прямых кавычек быть не должно.

ФОРМАТ ОТВЕТА: вход — JSON-массив объектов {"id": N, "en": "...", "ru": "..."}. Выход — JSON-массив строк РОВНО той же длины и порядка: отредактированный русский текст.
"""


def _tail(batches, index, count=4):
    """The end of the previous batch, so the voice carries over."""
    if index == 0:
        return ""
    previous = batches[index - 1]
    lines = [row.get("ru", "") for row in previous[-count:] if row.get("ru")]
    if not lines:
        return ""
    return ("\n\nПРЕДЫДУЩИЙ ФРАГМЕНТ (для связности интонации, не переводить заново):\n"
            + "\n".join(lines))


def stage_bulk(model: str, out_path: str = None):
    rows = corpus.load_corpus()
    voice = batch.load_voice()
    glossary = batch.load_glossary()
    batches = batch.make_batches(rows)
    batch.log("bulk: %d lines, %d batches" % (len(rows), len(batches)))

    def make_job(index, rows_in_batch):
        def job():
            system = voice + batch.format_glossary(
                batch.glossary_for([r["en"] for r in rows_in_batch], glossary))
            payload = [r["en"] for r in rows_in_batch]
            replies = batch.call_split(model, system, payload, temperature=0.3,
                                       tag="bulk")
            if replies is None:
                return None
            out = []
            for row, ru in zip(rows_in_batch, replies):
                item = dict(row)
                item["ru"] = ru
                out.append(item)
            return out
        return job

    jobs = [make_job(i, b) for i, b in enumerate(batches)]
    results = batch.run_parallel(jobs)
    out = []
    failed = 0
    for result in results:
        if result is None:
            failed += 1
            continue
        out.extend(result)
    if failed:
        batch.log("bulk: %d batches failed" % failed)
    path = out_path or BULK_PATH
    os.makedirs(os.path.dirname(path) or WORK, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in out:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    batch.log("bulk: wrote %d lines -> %s" % (len(out), path))
    return out


def stage_editorial(model: str):
    rows = corpus.read_jsonl(BULK_PATH)
    glossary = batch.load_glossary()
    batches = batch.make_batches(rows)
    batch.log("editorial: %d lines, %d batches" % (len(rows), len(batches)))

    def make_job(index, rows_in_batch):
        def job():
            payload = []
            for number, row in enumerate(rows_in_batch):
                payload.append({"id": number, "en": row["en"], "ru": row["ru"]})
            system = EDITORIAL_SYSTEM + batch.format_glossary(
                batch.glossary_for([r["en"] for r in rows_in_batch], glossary))
            prefix = _tail(batches, index) + "\n\nСТРОКИ:\n"
            replies = batch.call_split(model, system, payload, temperature=0.25,
                                       tag="edit", prefix=prefix)
            if replies is None:
                return None
            out = []
            for row, ru in zip(rows_in_batch, replies):
                item = dict(row)
                item["ru"] = ru
                out.append(item)
            return out
        return job

    jobs = [make_job(i, b) for i, b in enumerate(batches)]
    results = batch.run_parallel(jobs)
    out = []
    failed = 0
    for result in results:
        if result is None:
            failed += 1
            continue
        out.extend(result)
    if failed:
        batch.log("editorial: %d batches failed" % failed)
    os.makedirs(WORK, exist_ok=True)
    with open(EDIT_PATH, "w", encoding="utf-8", newline="\n") as fh:
        for row in out:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    batch.log("editorial: wrote %d lines -> %s" % (len(out), EDIT_PATH))
    return out


def stage_manual(source: str = None, out: str = None):
    """The hand corrections, applied over the stage that came before.

    A correction lives in two places: in the CSV that ships, and in
    src/voice/manual_fixes.json. The second place is what survives the next
    run of the pipeline.
    """
    source = source or EDIT_PATH
    out = out or source
    if not os.path.exists(MANUAL_PATH):
        return []
    with open(MANUAL_PATH, encoding="utf-8") as fh:
        fixes = json.load(fh)
    rows = corpus.read_jsonl(source)
    applied = 0
    for row in rows:
        key = corpus.key_of(row)
        if key in fixes:
            row["ru"] = fixes[key]
            applied += 1
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    batch.log("manual: applied %d fixes -> %s" % (applied, out))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="all",
                        choices=["bulk", "editorial", "manual", "all"])
    parser.add_argument("--source", default=None,
                        help="the file the manual fixes are applied to")
    parser.add_argument("--out", default=None,
                        help="where the stage writes: the bulk corpus or the "
                             "manual fixes. A bulk run with --out leaves the "
                             "working corpus alone — a trial run does not "
                             "overwrite what ships")
    parser.add_argument("--model", default=os.environ.get("DRRU_MODEL", "minimax-m3"))
    args = parser.parse_args()

    if args.stage in ("bulk", "all"):
        stage_bulk(args.model, args.out)
    if args.stage in ("editorial", "all"):
        stage_editorial(args.model)
    if args.stage in ("manual", "all"):
        stage_manual(args.source, args.out)


if __name__ == "__main__":
    main()
