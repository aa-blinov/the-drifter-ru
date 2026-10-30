#!/usr/bin/env python
"""The model endpoint, the disk cache, the reply parser.

The endpoint is a local OpenAI Responses API (the codex-router on
127.0.0.1:8788 by default). Every call is cached on disk under work/cache/,
keyed by the hash of model + system + user, so an interrupted run costs
nothing when it is resumed.

Plain standard library: the pipeline has to run on a machine with nothing
installed but Python 3.10 or newer.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import threading
import time
import urllib.error
import urllib.request

BASE_URL = os.environ.get("DRRU_BASE_URL", "http://127.0.0.1:8788/v1").rstrip("/")
DEFAULT_MODEL = os.environ.get("DRRU_MODEL", "minimax-m3")
CACHE_DIR = os.environ.get(
    "DRRU_CACHE_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "work", "cache"))

_lock = threading.Lock()


def cache_path(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return os.path.join(CACHE_DIR, digest + ".json")


def call_llm(model: str, system: str, user: str, max_tokens: int = 8000,
             temperature: float = 0.3, timeout: float = 600.0,
             retries: int = 4, cache_key: str | None = None,
             reasoning_effort: str = "none") -> str:
    """One model call. Returns the assistant text; raises on failure."""
    key = cache_key or ("%s|%s|%s" % (model, system, user))
    path = cache_path(key)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                cached = json.load(fh)
            if cached.get("text"):
                return cached["text"]
        except Exception:
            pass

    body = {
        "model": model,
        "max_output_tokens": max_tokens,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system}]},
            {"role": "user", "content": [{"type": "input_text", "text": user}]},
        ],
    }
    if temperature is not None:
        body["temperature"] = temperature
    if reasoning_effort:
        # The reasoning trace of this model is worth 180 seconds on a batch of
        # forty lines and adds nothing to a translation. The stages that need
        # the model to think about a hard choice ask for it explicitly.
        body["reasoning"] = {"effort": reasoning_effort}

    request = urllib.request.Request(
        BASE_URL + "/responses",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    last = ""
    for attempt in range(retries):
        try:
            text = _stream(request, timeout)
            if text.strip():
                with _lock:
                    os.makedirs(CACHE_DIR, exist_ok=True)
                    with open(path, "w", encoding="utf-8") as fh:
                        json.dump({"text": text, "model": model}, fh, ensure_ascii=False)
                return text
            last = "empty text"
        except urllib.error.HTTPError as exc:
            last = "HTTP %s: %s" % (exc.code, exc.read()[:200])
        except Exception as exc:
            last = "%s: %s" % (type(exc).__name__, exc)
        time.sleep(min(2 ** attempt, 20) + random.random())

    raise RuntimeError("model call failed after %d attempts: %s" % (retries, last))


def _stream(request, timeout) -> str:
    """The endpoint answers with an event stream; the text is the deltas."""
    text = ""
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: "):
                continue
            try:
                event = json.loads(line[6:])
            except Exception:
                continue
            if event.get("type") == "response.output_text.delta":
                text += event.get("delta", "")
    return text


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.M)


def extract_json_array(text: str):
    """The first JSON array in a reply, fenced or not."""
    stripped = _FENCE.sub("", text).strip()
    try:
        value = json.loads(stripped)
        if isinstance(value, list):
            return value
    except Exception:
        pass
    start = stripped.find("[")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(stripped)):
            char = stripped[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    fragment = stripped[start:index + 1]
                    try:
                        value = json.loads(fragment)
                        if isinstance(value, list):
                            return value
                    except Exception:
                        pass
                    break
        start = stripped.find("[", start + 1)
    return None
