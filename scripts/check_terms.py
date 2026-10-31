#!/usr/bin/env python
"""Проверка того, что глоссарий держит: один термин, одно слово.

Глоссарий говорит, что у имени одна русская форма. Проверка читает каждую
строку перевода, где термин упомянут в английском источнике, и смотрит на
русские слова, которые стоят на его месте. Термин, чьи строки используют два
разных русских слова, это термин, который разъехался, и это дефект: игрок
читает одного и того же человека под двумя именами.

Русские падежные окончания разъездом не считаются: «Рот», «Рота» и «Ротом»
это одно слово. Проверка сравнивает основы, а не формы.

    python3 scripts/check_terms.py
    python3 scripts/check_terms.py --verbose
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")
GLOSSARY = os.path.join(ROOT, "src", "voice", "glossary.json")

RU_WORD = re.compile(r"[А-Яа-яЁё][А-Яа-яЁё\-]*")
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z0-9\-]*")
TOKEN = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+")


def same_word(a: str, b: str) -> bool:
    """Два русских слова это одно слово, написанное в двух падежах.

    «Рот», «Рота» и «Ротом» это одно имя; «Хара» и «Хары» это одно имя.
    Окончание меняется, основа нет. Два слова совпадают, если у них
    общие все символы, кроме двух последних, и если короткое из них не
    короче трёх букв: этого хватает, чтобы не слить два разных имени и
    хватает, чтобы отличить «Сара» от «Сары».
    """
    a = a.lower()
    b = b.lower()
    if a == b:
        return True
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    shorter = min(len(a), len(b))
    return common >= 3 and common >= shorter - 2


def has_term(english: str, term: str) -> bool:
    """Строка источника упоминает термин.

    Совпадение ищется по слову, а не по буквам: «Anne» это имя, а
    «scanner» не упоминание его. Притяжательная форма входит в термин:
    «Mick's» это упоминание «Mick». Имя ищется в том виде, как оно
    написано, с заглавной буквы, поэтому «bill», счёт из банка, не
    считается упоминанием «Bill», человека.
    """
    pattern = r"(?<![A-Za-z'])" + re.escape(term).replace(r"\'", "'")
    pattern = pattern + r"(?:'s|’s)?(?![A-Za-z])"
    flags = 0 if term[:1].isupper() else re.IGNORECASE
    if term in ("EM", "em"):
        # «'em» это сокращение от «them», а не аббревиатура.
        pattern = r"(?<![A-Za-z'])EM(?![A-Za-z])"
    if term in ("End Ch.", "HD Dialogue Font", "hd font"):
        # Метка интерфейса: в источнике она написана в одном регистре, а в
        # переводе в другом, и это одна и та же метка.
        flags = re.IGNORECASE
    return re.search(pattern, english, flags) is not None


def phrase_in(words, phrase) -> bool:
    """Фраза глоссария есть в строке, если не считать падежных окончаний.

    Строка и фраза режутся на слова, а знаки препинания отбрасываются:
    игра пишет «С-Смертельное согласие» там, где источник говорит
    «D- Deadly Consent», и дефис в этом названии не часть имени.
    """
    wanted = TOKEN.findall(phrase)
    if not wanted:
        return False
    if len(wanted) == 1:
        return any(same_word(word, wanted[0]) for word in words)
    for start in range(len(words) - len(wanted) + 1):
        chunk = words[start:start + len(wanted)]
        if all(same_word(a, b) for a, b in zip(chunk, wanted)):
            return True
    return False


def rows_of(path):
    """Все пары (английский, русский) из перевода."""
    if not os.path.exists(path):
        return
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.reader(fh))
    if not table:
        return
    head = table[0]
    en_col = head.index("English")
    ru_col = head.index("Русский")
    for row in table[1:]:
        if len(row) > max(en_col, ru_col):
            yield row[en_col], row[ru_col]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    glossary = json.load(io.open(GLOSSARY, encoding="utf-8"))

    # Проверяются только те термины, которые являются именами. У обычного
    # слова много равноправных русских передач: «back» это «назад» в одной
    # строке и «спина» в следующей, и проверка по ним заглушила бы
    # настоящие находки.
    glossary = {term: ru for term, ru in glossary.items()
                if (ru[:1].isupper() or " " in ru) and term[:1].isupper()}

    # русские слова, которыми передан каждый английский термин
    rendered = collections.defaultdict(collections.Counter)
    examples = collections.defaultdict(dict)
    # строки, где термин есть в источнике, а его русской формы нет
    absent = collections.defaultdict(list)
    for english, russian in rows_of(TRANSLATION):
        if not english or not russian:
            continue
        words = TOKEN.findall(russian)
        for term, ru in glossary.items():
            if not has_term(english, term):
                continue
            # Русские слова, которые стоят на месте термина, ищутся по
            # основам, потому что падежные окончания меняются: «Рот»,
            # «Рота» и «Ротом» это одно слово.
            if phrase_in(words, ru):
                key = ru.lower()
                rendered[term][key] += 1
                examples[term].setdefault(key, russian)
            else:
                # Термин есть в источнике, а его слов нет в переводе: термин передан
                # иначе.
                absent[term].append((english, russian))

    drifted = []
    for term, forms in sorted(rendered.items()):
        # Формы одного слова это один разъезд: «Хара», «Хары» и «Харе» это
        # падежные окончания одного имени.
        clusters = []
        for form in forms:
            for group in clusters:
                if same_word(form, group[0]):
                    group.append(form)
                    break
            else:
                clusters.append([form])
        if len(clusters) > 1:
            drifted.append((term, glossary[term], clusters, examples))

    print("проверено терминов: %d" % len(rendered))
    print("терминов с несколькими русскими формами: %d" % len(drifted))
    for term, ru, clusters, samples in drifted:
        print("  %-24s -> %-22s %s" % (
            term, ru, " | ".join(", ".join(group) for group in clusters)))
        if args.verbose:
            for group in clusters:
                for form in group:
                    print("      %s: %s" % (form, samples.get(form, "")[:90]))

    # Строки, где термин есть в источнике, а его русских слов нет в
    # переводе: либо термин передан иначе, либо он не передан вовсе.
    print("терминов, переданных иначе: %d" % len(absent))
    for term, lines in sorted(absent.items()):
        print("  %-24s -> %-22s %d строк" % (term, glossary[term], len(lines)))
        if args.verbose:
            for english, russian in lines[:6]:
                print("      EN: %s" % english[:88])
                print("      RU: %s" % russian[:88])

    if drifted or absent:
        sys.exit(1)


if __name__ == "__main__":
    main()
