#!/usr/bin/env python
"""Проверки одной строки русского текста.

Они живут в одном модуле, потому что они нужны трём местам и должны
согласовываться: этап контроля качества сообщает, что не так, этап
полировки это чинит, а тесты проверяют, что починено.

Слово латиницей не дефект, если это имя, бренд, часть собственной нотации
игры, URL или идентификатор кода. Список разрешённого хранится в файле,
поэтому все три места читают один и тот же.
"""
from __future__ import annotations

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALLOWED_LATIN_PATH = os.path.join(ROOT, "src", "voice", "allowed_latin.json")

PLACEHOLDER = re.compile(r"\{[^}]*\}")
LATIN_WORD = re.compile(r"[A-Za-z]{3,}")
FUSED = re.compile(r"[А-Яа-яЁё][A-Za-z]{2,}|[A-Za-z]{2,}[А-Яа-яЁё]")
JSON_BLOB = re.compile(r'\{\s*"id"\s*:')

# Части строки, которые намеренно остаются латиницей: тег разметки, URL,
# домен, подсказки кнопок интерфейса.
KEPT = re.compile(r"<[^>]*>|https?://\S*|[\w-]+(?:\.[\w-]+){2,}\b"
                  r"|[\w-]+\.(?:com|org|net|gg|io|ru)\b\S*|\[[A-Z]{1,6}\]")

# Строка, которую игра показывает как есть: идентификатор, числовая
# последовательность, имя клавиши. Переводить в них нечего, и тесты не
# должны утверждать обратное.
DOMAIN = re.compile(r"https?://|\.[a-z]{2,4}\b")
CAMEL = re.compile(r"[a-z][A-Z]")
WORD = re.compile(r"[A-Za-z]{3,}")
# Серия из трёх и более строчных букв это слово какого-то языка. `Esc`
# и `R` это имена клавиш, `Jesus.` это слово.
LOWER_RUN = re.compile(r"[a-z]{3,}")


def load_allowed_latin() -> set:
    with open(ALLOWED_LATIN_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    words = set()
    for key, values in data.items():
        if key.startswith("_"):
            continue
        words.update(values)
    return words


ALLOWED_LATIN = load_allowed_latin()


def strip_kept(text: str) -> str:
    """Текст без частей, которые намеренно оставлены латиницей."""
    return KEPT.sub(" ", text)


def is_code(text: str) -> bool:
    """Истина, когда строка это идентификатор и переводить в ней нечего.

    Игра показывает несколько строк как есть: имя клавиши, кнопку,
    сочетание цифр, домен. Это код, а не проза, и перевод, который их не
    трогает, прав.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if DOMAIN.search(stripped):
        return True
    # Имя в camel case это имя: BtnContinue, TopicGauge, FlamerFire.
    if CAMEL.search(stripped):
        return True
    # Строка из цифр, знаков препинания и пробелов не несёт слов.
    if not WORD.search(stripped):
        return True
    # Слово с заглавной буквы без серии строчных это имя клавиши: Esc, R.
    if not LOWER_RUN.search(stripped):
        return True
    return False


def defects(en: str, ru: str):
    """Дефекты одной строки в виде списка описаний."""
    found = []
    if sorted(PLACEHOLDER.findall(en)) != sorted(PLACEHOLDER.findall(ru)):
        found.append("потерян плейсхолдер")
    if FUSED.search(ru):
        found.append("слово склеено из русского и английского")
    for word in LATIN_WORD.findall(strip_kept(ru)):
        if word not in ALLOWED_LATIN:
            found.append("английское слово внутри русской строки: %s" % word)
            break
    foreign = foreign_scripts(ru)
    if foreign:
        found.append("посторонний алфавит в русской строке: %s"
                     % ", ".join(sorted(foreign)))
    if JSON_BLOB.search(ru):
        found.append("вместо текста лежит фрагмент разметки")
    return found


def foreign_scripts(text: str):
    """Алфавиты текста, которым там не место.

    Русская строка написана кириллицей и, ради имён мира, латиницей. Всё
    остальное это модель, сбившаяся: одна строка корпуса вернулась с
    китайским словом в конце.

    Знаки препинания, метки игры (`<color=#5FCDE4FF>`) и знаки арифметики
    алфавитами не считаются, и их не трогают.
    """
    import unicodedata

    found = set()
    for char in text:
        if char.isspace() or char.isdigit():
            continue
        if char in "«»—–…„“”‘’'\"()[]{}.,:;!?-/\\|+*=%&#@×÷±°":
            continue
        if char in "<>":
            # Теги игры, `<color=#5FCDE4FF>`.
            continue
        name = unicodedata.name(char, "")
        for script in ("CYRILLIC", "LATIN"):
            if script in name:
                break
        else:
            found.add(name.split()[0] if name else repr(char))
    return found
