#!/usr/bin/env python
"""Батчи и вызов модели, который их заполняет.

Один батч это один вызов модели. Правило батчинга одинаково на всех этапах:
батч никогда не пересекает границу исходного файла, поэтому реплики одного
диалога попадают в модель вместе и голос персонажа переживает перевод.

Промпт несёт код стиля и только те статьи глоссария, которые батч действительно
затрагивает. Промпт со всем глоссарием это промпт со всем глоссарием 245 раз.
"""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time

from . import llm_client

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VOICE_PATH = os.path.join(ROOT, "src", "voice", "bible.md")
GLOSSARY_PATH = os.path.join(ROOT, "src", "voice", "glossary.json")

MAX_CHARS = int(os.environ.get("DRRU_MAX_CHARS", "3200"))
MAX_ITEMS = int(os.environ.get("DRRU_MAX_ITEMS", "40"))
WORKERS = int(os.environ.get("DRRU_WORKERS", "6"))

_print_lock = threading.Lock()


def log(*args):
    with _print_lock:
        print(*args, flush=True)


def load_voice() -> str:
    with open(VOICE_PATH, encoding="utf-8") as fh:
        return fh.read()


def load_glossary() -> dict:
    with open(GLOSSARY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def glossary_for(texts, glossary, limit: int = 60):
    """Статьи глоссария, которые батч действительно затрагивает, от длинных к коротким."""
    blob = " ".join(texts).lower()
    hits = []
    for en, ru in glossary.items():
        if len(en) < 3:
            continue
        if en.lower() in blob:
            hits.append((en, ru))
    hits.sort(key=lambda item: -len(item[0]))
    return hits[:limit]


def format_glossary(pairs) -> str:
    if not pairs:
        return ""
    lines = "\n".join("- %s → %s" % (en, ru) for en, ru in pairs)
    return ("\n\nГЛОССАРИЙ (обязательные переводы, синонимы не подставлять):\n"
            + lines)


def make_batches(rows, max_chars: int = MAX_CHARS, max_items: int = MAX_ITEMS):
    """Непрерывные батчи внутри каждого исходного файла."""
    batches = []
    current = []
    chars = 0
    current_file = None
    for row in rows:
        size = len(row.get("en", "")) or len(row.get("ru", ""))
        if current and (row["file"] != current_file
                        or len(current) >= max_items
                        or chars + size > max_chars):
            batches.append(current)
            current = []
            chars = 0
        current.append(row)
        chars += size
        current_file = row["file"]
    if current:
        batches.append(current)
    return batches


def placeholders(text: str):
    """Плейсхолдеры и разметка строки, по порядку."""
    return re.findall(r"\{[^}]*\}|<[^>]*>|\{\w+\}", text)


def call_batch(model: str, system: str, payload, temperature: float = 0.3,
               max_tokens: int = 8000, tag: str = "batch", attempts: int = 3,
               reasoning_effort: str = "none", prefix: str = ""):
    """Один вызов. Возвращает список ответов или None, если модель нарушила контракт.

    `payload` это список элементов, а ответ должен быть списком той же длины.
    `prefix` ставится перед payload в пользовательском сообщении, для этапов,
    которым нужно дать модели контекст до самих реплик.
    """
    user = prefix + json.dumps(payload, ensure_ascii=False, indent=1)
    for attempt in range(attempts):
        # Номер попытки входит в ключ кэша: повтор должен снова дойти до модели,
        # а плохой ответ из кэша вернулся бы как есть.
        key = "%s|%s|%s" % (tag, model, user) if attempt == 0 \
            else "%s|retry%d|%s|%s" % (tag, attempt, model, user)
        try:
            text = llm_client.call_llm(model, system, user, max_tokens=max_tokens,
                                       temperature=temperature, cache_key=key,
                                       reasoning_effort=reasoning_effort)
        except Exception as exc:
            log("  %s: вызов не удался: %s" % (tag, exc))
            time.sleep(2 + 4 * attempt)
            continue
        parsed = llm_client.extract_json_array(text)
        if parsed is None or len(parsed) != len(payload):
            # Запрос одной реплики модель иногда выполняет самой репликой,
            # без JSON-обёртки. Это пригодный ответ.
            if len(payload) == 1 and parsed is None:
                bare = text.strip().strip('"').strip()
                if bare and "\n" not in bare:
                    return [bare]
            log("  %s: плохой ответ (%s элементов, ожидалось %d), попытка %d"
                % (tag, len(parsed) if parsed else "нет", len(payload), attempt + 1))
            time.sleep(1 + 3 * attempt)
            continue
        return [_as_text(item) for item in parsed]
    return None


def _as_text(item) -> str:
    """Текст элемента ответа.

    Этапы просят массив строк. Редакторский этап отправляет объекты и иногда
    получает объекты же; текст такого объекта это то поле, которое назвал
    промпт, а сам объект ответом не является.
    """
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for field in ("ru", "text", "translation", "перевод"):
            if field in item and isinstance(item[field], str):
                return item[field]
    return str(item)


def call_split(model: str, system: str, payload, temperature: float = 0.3,
               max_tokens: int = 8000, tag: str = "batch",
               reasoning_effort: str = "none", chunk: int = 12,
               prefix: str = ""):
    """Один вызов, а при нарушении контракта те же реплики меньшими кусками.

    Батч из сорока реплик может вернуться коротким: модель останавливается
    раньше. Недостающие реплики запрашиваются заново по десять штук, потому
    что короткий батч модель отвечает надёжнее. Реплика, которая так и не
    пришла, попадает в отчёт, а не теряется молча.
    """
    replies = call_batch(model, system, payload, temperature=temperature,
                          max_tokens=max_tokens, tag=tag,
                          reasoning_effort=reasoning_effort, prefix=prefix)
    if replies is not None:
        return replies

    out = []
    for start in range(0, len(payload), chunk):
        piece = payload[start:start + chunk]
        piece_replies = call_batch(model, system, piece, temperature=temperature,
                                   max_tokens=max_tokens, tag="%s-part" % tag,
                                   reasoning_effort=reasoning_effort, prefix=prefix)
        if piece_replies is None:
            log("  %s: %d реплик не вернулись" % (tag, len(piece)))
            out.extend(["" for _ in piece])
            continue
        out.extend(piece_replies)
    return out


def call_report(model: str, system: str, payload, temperature: float = 0.1,
               max_tokens: int = 4000, tag: str = "report"):
    """Один вызов для этапа, у которого ответ короче запроса.

    Этап вычитки просит сомнительные реплики и получает только их, поэтому
    ответ короче запроса. Контракт тут другой: важно, чтобы ответ был
    списком объектов с идентификатором и чтобы идентификаторы указывали на
    существующие строки.
    """
    user = json.dumps(payload, ensure_ascii=False, indent=1)
    key = "%s|%s|%s" % (tag, model, user)
    for attempt in range(3):
        try:
            text = llm_client.call_llm(model, system, user, max_tokens=max_tokens,
                                       temperature=temperature, cache_key=key)
        except Exception as exc:
            log("  %s: вызов не удался: %s" % (tag, exc))
            time.sleep(2 + 4 * attempt)
            continue
        parsed = llm_client.extract_json_array(text)
        if parsed is None:
            log("  %s: в ответе нет массива, попытка %d" % (tag, attempt + 1))
            time.sleep(1 + 3 * attempt)
            continue
        return parsed
    return None


def run_parallel(jobs, worker: int = WORKERS):
    """Выполняет задания в небольшом пуле. Порядок результатов совпадает с порядком заданий."""
    results = [None] * len(jobs)
    index_lock = threading.Lock()
    next_index = [0]
    done = [0]

    def worker_loop():
        while True:
            with index_lock:
                index = next_index[0]
                if index >= len(jobs):
                    return
                next_index[0] = index + 1
            job = jobs[index]
            try:
                results[index] = job()
            except Exception as exc:
                results[index] = exc
                log("  задание %d не выполнено: %s" % (index, exc))
            done[0] += 1
            if done[0] % 10 == 0 or done[0] == len(jobs):
                log("  %d/%d батчей готово" % (done[0], len(jobs)))

    threads = [threading.Thread(target=worker_loop) for _ in range(max(1, worker))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results
