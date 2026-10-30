#!/usr/bin/env python
"""Batches and the model call that fills them.

One batch is one call to the model. The batching rule is the same in every
stage: a batch never crosses a source file, so the lines of one dialogue
reach the model together and the voice of a character survives the
translation.

The prompt carries the style code and the part of the glossary the batch
actually mentions. A prompt that carries the whole glossary is a prompt
that carries the whole glossary 245 times.
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
    """The glossary entries a batch actually mentions, longest first."""
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
    """Contiguous batches inside each source file."""
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
    """The placeholders and the markup of a line, in order."""
    return re.findall(r"\{[^}]*\}|<[^>]*>|\{\w+\}", text)


def call_batch(model: str, system: str, payload, temperature: float = 0.3,
               max_tokens: int = 8000, tag: str = "batch", attempts: int = 3,
               reasoning_effort: str = "none", prefix: str = ""):
    """One call. Returns the list of replies, or None when the model broke the contract.

    `payload` is a list of items; the reply must be a list of the same
    length. `prefix` is put in front of the payload in the user message, for
    the stages that need to give the model context before the lines.
    """
    user = prefix + json.dumps(payload, ensure_ascii=False, indent=1)
    for attempt in range(attempts):
        # The attempt number is part of the cache key: a retry has to reach
        # the model again, and a cached bad reply would be returned as-is.
        key = "%s|%s|%s" % (tag, model, user) if attempt == 0 \
            else "%s|retry%d|%s|%s" % (tag, attempt, model, user)
        try:
            text = llm_client.call_llm(model, system, user, max_tokens=max_tokens,
                                       temperature=temperature, cache_key=key,
                                       reasoning_effort=reasoning_effort)
        except Exception as exc:
            log("  %s: call failed: %s" % (tag, exc))
            time.sleep(2 + 4 * attempt)
            continue
        parsed = llm_client.extract_json_array(text)
        if parsed is None or len(parsed) != len(payload):
            # A request for one line is sometimes answered with the line
            # itself, without the JSON wrapper. That is a usable answer.
            if len(payload) == 1 and parsed is None:
                bare = text.strip().strip('"').strip()
                if bare and "\n" not in bare:
                    return [bare]
            log("  %s: bad reply (%s items, expected %d), retry %d"
                % (tag, len(parsed) if parsed else "none", len(payload), attempt + 1))
            time.sleep(1 + 3 * attempt)
            continue
        return [_as_text(item) for item in parsed]
    return None


def _as_text(item) -> str:
    """The text of a reply item.

    The stages ask for an array of strings. The editorial stage sends objects
    and sometimes gets objects back; the text of such an object is the field
    the prompt named, and the raw object is never the answer.
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
    """One call, and when the model breaks the contract, the same lines in
    smaller pieces.

    A batch of forty lines can come back short: the model stops early. The
    lines that are missing are asked for again, ten at a time, because a
    shorter batch is answered more reliably. A line that never arrives is
    reported, not silently dropped.
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
            log("  %s: %d lines did not come back" % (tag, len(piece)))
            out.extend(["" for _ in piece])
            continue
        out.extend(piece_replies)
    return out


def run_parallel(jobs, worker: int = WORKERS):
    """Run the jobs on a small pool. The order of the results is the order of the jobs."""
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
                log("  job %d failed: %s" % (index, exc))
            done[0] += 1
            if done[0] % 10 == 0 or done[0] == len(jobs):
                log("  %d/%d batches done" % (done[0], len(jobs)))

    threads = [threading.Thread(target=worker_loop) for _ in range(max(1, worker))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results
