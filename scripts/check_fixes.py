#!/usr/bin/env python
"""Проверка того, что ручные правки не теряют источник.

Правка заменяет строку перевода. Правка, которая выбрасывает предложение
источника, это дефект, которого не видит ни одна другая проверка: строка
по-прежнему хороший русский текст, она просто больше не та английская строка.

Скрипт читает каждую правку и сравнивает её с тем английским источником,
которому она принадлежит. Сравнение идёт по тому, что они несут: плейсхолдеры,
теги игры, числа, имена и число предложений.

    python3 scripts/check_fixes.py
    python3 scripts/check_fixes.py --verbose
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "corpus", "english.csv")
FIXES = os.path.join(ROOT, "src", "voice", "manual_fixes.json")

PLACEHOLDER = re.compile(r"\{[^}]*\}")
NUMBER = re.compile(r"\d+")
WORD = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\-]*")


def sentences(text):
    """Предложения строки, как бы она их ни заканчивала.

    Точка между двумя цифрами это десятичная запятая, а точка после одной
    буквы это конец сокращения: «14.46 CPM» и «M.O.» это по одному
    предложению. Многоточие всегда заканчивает предложение: слова по обе
    стороны от него относятся к разным мыслям.
    """
    parts = re.split(r"…+|(?<![0-9A-Za-zА-Яа-яЁё])[.!?]+", text)
    return [p.strip() for p in parts if p.strip()]


def content_words(text):
    """Слова строки, которые несут её смысл.

    Короткие слова не считаются: в русской строке их больше, чем в
    английской, и их подсчёт делал бы каждую строку короче на вид.
    """
    return [w for w in WORD.findall(text) if len(w) >= 4]


def shared_words(before, after):
    """Сколько строки правка оставила.

    Правка переформулирует строку: она сохраняет большую часть её слов и
    меняет некоторые. Правка, которая почти ничего не разделяет с
    заменяемой строкой, попала не в ту строку: это признак ключа,
    написанного без своего символа.
    """
    old = set(w.lower() for w in WORD.findall(before) if len(w) >= 3)
    new = set(w.lower() for w in WORD.findall(after) if len(w) >= 3)
    if not old or not new:
        return 1.0
    return len(old & new) / float(min(len(old), len(new)))


# Предлог в конце строки: предложение не может на нём закончиться. Это
# признак строки, которую разрезали посередине.
DANGLING = re.compile(
    r"\b(?:в|на|с|к|по|из|о|об|у|до|за|для|от|под|над|при|про|через|без|"
    r"около|после|перед|между|ради|из-за)\s*[.!?…»]*$", re.IGNORECASE)


def cut_off(text: str) -> bool:
    """Строка заканчивается посередине предложения.

    Игра намеренно обрезает часть своих строк, и такая строка кончается
    многоточием. Строка, которая кончается предлогом, обрезана по ошибке.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.endswith(("…", "...")):
        return False
    # Метка интерфейса короткая: «Поговорить с» кончается предлогом и
    # при этом целая.
    if len(stripped.split()) < 5:
        return False
    return DANGLING.search(stripped) is not None


def names(text):
    """Слова, которые несут факты: числа и имена."""
    return set(NUMBER.findall(text))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--corpus-jsonl", default=os.path.join(
        ROOT, "work", "corpus", "polish.jsonl"),
        help="корпус, по которому делались правки")
    args = parser.parse_args()

    with io.open(CORPUS, encoding="utf-8", newline="") as fh:
        corpus = list(csv.reader(fh))[1:]
    english = {"%s|%s" % (r[0], r[1]): r[4] for r in corpus}

    # Строка, которую заменила каждая правка, чтобы было видно правку,
    # попавшую не в ту строку.
    before = {}
    if os.path.exists(args.corpus_jsonl):
        with io.open(args.corpus_jsonl, encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                before["%s|%s" % (row.get("character", ""), row.get("id", ""))] = row["ru"]

    fixes = json.load(io.open(FIXES, encoding="utf-8"))
    problems = []
    for key, russian in sorted(fixes.items()):
        source = english.get(key)
        if source is None:
            problems.append(("нет такой строки в корпусе", key, source, russian))
            continue
        if sorted(PLACEHOLDER.findall(source)) != sorted(PLACEHOLDER.findall(russian)):
            problems.append(("потерян плейсхолдер", key, source, russian))
        if source.count("<color") != russian.count("<color"):
            problems.append(("потеряна разметка", key, source, russian))
        lost = names(source) - names(russian)
        if lost:
            problems.append(("потеряно число: %s" % ", ".join(sorted(lost)),
                             key, source, russian))
        # Многоточие не конец предложения: слова по обе стороны от него
        # относятся к одной мысли.
        if len(sentences(source)) > len(sentences(russian)) + 1:
            problems.append(("потеряно предложение", key, source, russian))
        # Выброшенное предложение уносит с собой треть строки. Русский текст
        # обычно длиннее английского, но сжатая передача технической
        # формулировки («orders of magnitude» это «на порядки») потерей не
        # считается, поэтому правило мягкое: оно срабатывает только при
        # настоящей нехватке.
        words_en = len(content_words(source))
        words_ru = len(content_words(russian))
        if words_en >= 12 and words_ru < words_en * 0.55:
            problems.append(("потеряна часть текста", key, source, russian))
        old = before.get(key)
        if old is not None:
            # Правка переформулирует строку, а не меняет её на другую. Правка,
            # которая намного длиннее строки, которую она заменила, попала
            # не в ту строку: это признак ключа, написанного без своего
            # символа.
            grew = len(content_words(russian)) > len(content_words(old)) * 1.6 + 3
            if grew or (len(content_words(old)) >= 8
                        and shared_words(old, russian) < 0.2):
                problems.append(("правка попала не в ту строку", key, source, russian))
        if cut_off(russian) and not cut_off(source):
            # Строка кончается предлогом: её разрезали посередине.
            problems.append(("строка обрезана", key, source, russian))

    print("правок: %d" % len(fixes))
    print("правок, теряющих источник: %d" % len(problems))
    for what, key, source, russian in problems:
        print("  %s: %s" % (what, key))
        if args.verbose:
            print("      EN: %s" % (source or "")[:100])
            print("      RU: %s" % russian[:100])

    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
