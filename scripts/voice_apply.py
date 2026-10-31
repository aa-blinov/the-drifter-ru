#!/usr/bin/env python
"""Отбор находок аудита голоса и применение правок.

Аудит находит строки, где перевод суше источника, но модель ошибается:
четверть её предложений хуже оригинала, часть ломает глоссарий, часть
вставляет чужой алфавит. Поэтому правка проходит фильтры, и только то, что
прошло, попадает в перевод.

Фильтры:
- термин глоссария не исчезает и не подменяется другим;
- числа, плейсхолдеры и имена на месте;
- в правке нет символов вне кириллицы и латиницы;
- длина правки в пределах разумного;
- лицо повествования не перевёрнуто;
- типографика цела: «ёлочки» парны, нет прямых кавычек и трёх точек.

    python3 scripts/voice_apply.py --check     # только отчёт
    python3 scripts/voice_apply.py             # применить
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import check_fixes  # noqa: E402

DASH = "—"
ALLOWED_CHARS = set(" \t\n«»„“”'’…—–-.,:;!?()[]{}\"'/\\|+*=%&#@№$~^`_0123456789")
GLOSSARY = os.path.join(ROOT, "src", "voice", "glossary.json")
ALLOWED_LATIN = os.path.join(ROOT, "src", "voice", "allowed_latin.json")
FIXES = os.path.join(ROOT, "src", "voice", "manual_fixes.json")
TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")
FINDINGS = os.path.join(ROOT, "work", "voice_audit.jsonl")

NUMBER = re.compile(r"\d+")
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
PLACEHOLDER = re.compile(r"\{0\}")
WORD = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё'’-]*")
FIRST_PERSON = re.compile(r"^Я\b")
THIRD_PERSON = re.compile(r"^(Он|Она|Его|Её)\b")


def load_glossary() -> dict:
    with io.open(GLOSSARY, encoding="utf-8") as fh:
        return json.load(fh)


def load_allowed_latin() -> set:
    """Слова, которые в русской строке могут остаться латиницей."""
    with io.open(ALLOWED_LATIN, encoding="utf-8") as fh:
        data = json.load(fh)
    words = set()
    for key, values in data.items():
        if key.startswith("_"):
            continue
        words.update(values)
    return words


def load_fixes() -> dict:
    with io.open(FIXES, encoding="utf-8") as fh:
        data = json.load(fh)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def save_fixes(fixes: dict):
    with io.open(FIXES, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fixes, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


def load_translation() -> list:
    with io.open(TRANSLATION, encoding="utf-8-sig", newline="") as fh:
        return list(csv.reader(fh))


def glossary_forms(text: str, glossary: dict) -> set:
    """Формы глоссария, которые есть в строке.

    Слово ищется целиком, а короткие формы вроде «в» или «нет» пропускаются:
    в глоссарии они появляются кусками перевода, и подстрока тут даёт
    ложное срабатывание на каждой второй строке.
    """
    forms = set()
    for ru in glossary.values():
        for part in ru.split():
            if len(part) < 4:
                continue
            if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(part), text,
                         re.IGNORECASE):
                forms.add(part)
    return forms


def reject(reason: str) -> str:
    return reason


def source_text(key: str, english: dict) -> str:
    return english.get(key, "")


def check(item: dict, glossary: dict, allowed_latin: set,
          english: dict, before: dict) -> str:
    """Пустая строка, если правку можно применять, иначе причина отказа.

    Правка проходит те же правила, что и scripts/check_fixes.py: она не
    теряет плейсхолдер, разметку, число, предложение и не выглядит как
    правка чужой строки.
    """
    old = item["ru"].strip()
    new = item["fix"].strip()
    source = source_text(item["key"], english)
    if not new:
        return "пустая правка"
    if new == old:
        return "правка не меняет текст"
    for char in new:
        if char in ALLOWED_CHARS:
            continue
        if char.isalpha() and ("Ѐ" <= char <= "ӿ"):
            continue
        if char.isascii() and char.isalpha():
            continue
        return "чужой символ: %r" % char
    for word in LATIN_WORD.findall(new):
        if word not in allowed_latin:
            return "латиница: %s" % word
    if NUMBER.findall(old) != NUMBER.findall(new):
        return "изменились числа"
    if len(PLACEHOLDER.findall(old)) != len(PLACEHOLDER.findall(new)):
        return "изменилось число плейсхолдеров"
    old_forms = glossary_forms(old, glossary)
    new_forms = glossary_forms(new, glossary)
    if old_forms != new_forms:
        return "поехал термин глоссария"
    if len(new) > 1.5 * len(old) or len(new) < 0.6 * len(old):
        return "длина правки вышла за разумный предел"
    if FIRST_PERSON.match(old) and not FIRST_PERSON.match(new):
        return "повествование перешло из первого лица"
    if THIRD_PERSON.match(old) and FIRST_PERSON.match(new):
        return "повествование перешло в первое лицо"
    if new.count("«") != new.count("»"):
        return "непарные ёлочки"
    if '"' in new:
        return "прямые кавычки"
    if "..." in new:
        return "многоточие из трёх точек"
    if new.endswith(".") != old.endswith("."):
        return "поехала точка в конце"
    # Правила scripts/check_fixes.py: правка не должна терять источник.
    if source:
        if sorted(check_fixes.PLACEHOLDER.findall(source)) != \
                sorted(check_fixes.PLACEHOLDER.findall(new)):
            return "потерян плейсхолдер"
        if source.count("<color") != new.count("<color"):
            return "потеряна разметка"
        lost = check_fixes.names(source) - check_fixes.names(new)
        if lost:
            return "потеряно число: %s" % ", ".join(sorted(lost))
        if len(check_fixes.sentences(source)) > len(check_fixes.sentences(new)) + 1:
            return "потеряно предложение"
        if len(check_fixes.content_words(source)) >= 12 and \
                len(check_fixes.content_words(new)) < \
                len(check_fixes.content_words(source)) * 0.55:
            return "потеряна часть текста"
        if check_fixes.cut_off(new) and not check_fixes.cut_off(source):
            return "строка обрезана"
    previous = before.get(item["key"])
    if previous is not None:
        grew = len(check_fixes.content_words(new)) > \
            len(check_fixes.content_words(previous)) * 1.6 + 3
        if grew or (len(check_fixes.content_words(previous)) >= 8
                    and check_fixes.shared_words(previous, new) < 0.2):
            return "правка выглядит как правка чужой строки"
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--findings", default=FINDINGS)
    parser.add_argument("--check", action="store_true",
                        help="только показать, что пройдёт и что нет")
    args = parser.parse_args()

    glossary = load_glossary()
    allowed_latin = load_allowed_latin()
    fixes = load_fixes()
    rows = load_translation()
    header, table = rows[0], rows[1:]
    ru_col = header.index("Русский")

    english = {}
    with io.open(os.path.join(ROOT, "corpus", "english.csv"),
                 encoding="utf-8", newline="") as fh:
        for row in list(csv.reader(fh))[1:]:
            english["%s|%s" % (row[0], row[1])] = row[4]

    before = {}
    polish = os.path.join(ROOT, "work", "corpus", "polish.jsonl")
    if os.path.exists(polish):
        with io.open(polish, encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                before["%s|%s" % (row.get("character", ""),
                                   row.get("id", ""))] = row["ru"]

    with io.open(args.findings, encoding="utf-8") as fh:
        findings = [json.loads(line) for line in fh if line.strip()]

    passed = []
    reasons = collections.Counter()
    for item in findings:
        reason = check(item, glossary, allowed_latin, english, before)
        if reason:
            reasons[reason] += 1
            continue
        passed.append(item)

    print("находок: %d, прошло фильтры: %d, отклонено: %d"
          % (len(findings), len(passed), len(findings) - len(passed)))
    for reason, count in reasons.most_common():
        print("  %-45s %d" % (reason, count))

    if args.check:
        return 0

    index = {}
    for position, row in enumerate(table):
        index["%s|%s" % (row[0], row[1])] = position

    applied = 0
    for item in passed:
        key = item["key"]
        position = index.get(key)
        if position is None:
            continue
        current = table[position][ru_col]
        if current.strip() != item["ru"].strip():
            continue
        table[position][ru_col] = item["fix"].strip()
        fixes[key] = item["fix"].strip()
        applied += 1

    with io.open(TRANSLATION, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\r\n")
        writer.writerows([header] + table)
    save_fixes(fixes)
    print("применено правок: %d" % applied)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
