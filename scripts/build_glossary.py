#!/usr/bin/env python
"""Build the glossary out of the translation that exists.

The glossary is a promise: a term has one Russian word in this game. A
glossary written by hand drifts from the text; a glossary read out of the
text cannot, because every entry of it is a pair that the translation
actually uses.

The pair is found by alignment. A term in the English source is followed, in
the Russian line, by the word that stands in its place: the capitalised
Russian word next to it, or the capitalised Russian word in the same
position. The candidates are counted, and the one that the text uses most is
the entry.

    python3 scripts/build_glossary.py            # the terms that are missing
    python3 scripts/build_glossary.py --apply    # write them into the glossary

A term that the translation renders in more than one way is a finding, not an
entry: it is printed with the forms it was found in, and it is left for a
reader to decide.
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "corpus", "english.csv")
TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")
GLOSSARY = os.path.join(ROOT, "src", "voice", "glossary.json")

WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]+")
RU_WORD = re.compile(r"[А-Яа-яЁё][А-Яа-яЁё\-]*")

# The words a Russian sentence opens with. They are capitalised for the
# grammar, not because they are names.
RU_OPENERS = {
    "Да", "Нет", "Он", "Она", "Они", "Это", "Этот", "Эта", "Эти", "Что",
    "Как", "Почему", "Зачем", "Кто", "Где", "Когда", "Куда", "Откуда",
    "Но", "И", "А", "Или", "Но", "Ты", "Мы", "Вы", "Я", "Мне", "Меня",
    "Ну", "Угу", "Ах", "Ох", "Эй", "Хм", "Хмм", "Хммм", "Угу", "Хех",
    "Правда", "Серьёзно", "Прости", "Простите", "Извини", "Извините",
    "Спасибо", "Пожалуйста", "Привет", "Здравствуй", "Здравствуйте",
    "Хорошо", "Хорошо", "Ладно", "Стоп", "Подожди", "Подождите", "Тише",
    "Тсс", "Смотри", "Смотрите", "Послушай", "Послушайте", "Знаешь",
    "Знаете", "Погоди", "Погодите", "Слышишь", "Слышите", "Иди", "Идите",
    "Вон", "Смотри", "Ты", "Твои", "Все", "Всё", "Так", "Тоже", "Ещё",
    "Уже", "Еще", "Еще", "Очень", "Немного", "Много", "Мало", "Больше",
    "Меньше", "Почти", "Почти", "Совсем", "Сначала", "Потом", "Теперь",
    "Тогда", "Сейчас", "Позже", "Раньше", "Потому", "Поэтому", "Конечно",
    "Разумеется", "Очевидно", "Возможно", "Наверное", "Вероятно", "Похоже",
    "Кажется", "Казалось", "Значит", "Значит", "Слушай", "Слушайте",
    "Знаешь", "Думаю", "Кажется", "По-моему", "По-моему", "Короче",
    "Наконец", "Всё-таки", "Всё-таки", "Один", "Одна", "Одно", "Каждый",
    "Любой", "Никакой", "Ничто", "Кто-то", "Что-то", "Кое-что", "Куда-то",
    "Где-то", "Когда-то", "Как-то", "Сам", "Сама", "Сами", "Весь", "Вся",
    "Всё", "Кто", "Что", "Где", "Когда", "Зачем", "Почему", "Как", "Чей",
    "Чья", "Чьи", "Какой", "Какая", "Какие", "Сюда", "Туда", "Там",
    "Здесь", "Оттуда", "Отсюда", "Вниз", "Вверх", "Назад", "Вперёд",
    "Вперед", "Назад", "Рядом", "Около", "Вдруг", "Вот", "Вот",
    "Жаль", "К счастью", "К несчастью", "Боже", "Боже", "Господи",
    "Господи", "Иисус", "Чёрт", "Черт", "Дерьмо", "Хрен", "Твою мать",
    "Слушай", "Эй", "Пс", "Пст", "Тип", "Слышь", "Брат", "Сестренка",
    "Друг", "Друг", "Ребята", "Ребята", "Парни", "Девушка", "Муж",
    "Женщина", "Мужчина", "Суки", "Суки", "Мать", "Папа", "Мама",
    "Сын", "Дочь", "Мой", "Моя", "Моё", "Мои", "Твой", "Твоя", "Твоё",
    "Наш", "Наша", "Наше", "Наши", "Ваш", "Ваша", "Ваше", "Ваши",
    "Это", "Вот", "Всё", "Ни", "Никак", "Куда", "Кто", "Что",
}

# The words that are not terms of the game.
STOP = {
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "not", "no",
    "yes", "of", "to", "in", "on", "at", "by", "for", "with", "from", "up",
    "out", "off", "on", "is", "are", "was", "were", "be", "been", "being",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
    "them", "my", "your", "his", "its", "our", "their", "this", "that",
    "these", "those", "there", "here", "what", "which", "who", "whom",
    "when", "where", "why", "how", "do", "does", "did", "done", "have", "has",
    "had", "will", "would", "can", "could", "should", "may", "might", "must",
    "shall", "get", "got", "go", "going", "gone", "come", "came", "know",
    "knew", "think", "thought", "want", "wanted", "need", "needed", "look",
    "looking", "looked", "see", "saw", "seen", "say", "said", "tell", "told",
    "make", "made", "take", "took", "give", "gave", "find", "found", "well",
    "yeah", "okay", "ok", "hey", "oh", "ah", "right", "sure", "maybe",
    "nothing", "something", "anything", "everything", "just", "only", "even",
    "still", "back", "down", "over", "again", "around", "through", "between",
    "before", "after", "because", "while", "where", "who", "god", "jesus",
    "christ", "fuck", "shit", "damn", "hell", "sorry", "thanks", "thank",
    "please", "hello", "hi", "good", "bad", "better", "best", "worse", "worst",
    "much", "many", "more", "most", "less", "least", "very", "too", "now",
    "then", "again", "always", "never", "sometimes", "soon", "later", "here",
    "there", "goddamn", "bastard", "bitch", "asshole", "dick", "cock", "pussy",
    "gun", "shot", "shoot", "knife", "kill", "killed", "killing", "dead",
    "death", "die", "died", "blood", "pain", "hurt", "fear", "afraid", "angry",
    "mad", "tired", "hunger", "thirst", "cold", "hot", "warm", "wet", "dry",
    "run", "ran", "running", "walk", "walked", "stop", "stopped", "stand",
    "stood", "sit", "sat", "open", "opened", "close", "closed", "push", "pull",
    "move", "moved", "turn", "turned", "wait", "waited", "ask", "asked",
    "answer", "answered", "help", "try", "tried", "use", "used", "work",
    "worked", "put", "keep", "kept", "let", "leave", "left", "man", "woman",
    "men", "women", "people", "person", "thing", "time", "day", "night", "morning",
    "evening", "week", "month", "year", "minute", "second", "hour",
    "seemed", "seems", "felt", "feel", "sound", "sounded", "smell", "smelled",
    "sound", "voice", "sound", "name", "names", "called", "call", "cried",
    "shouted", "whispered", "laughed", "smiled", "nodded", "shook", "hand",
    "hands", "head", "eyes", "face", "back", "room", "house", "door", "car",
    "road", "water", "air", "light", "dark", "black", "white", "red", "green",
    "blue", "grey", "gray", "brown", "yellow", "skin", "eye", "face", "mouth",
    "leg", "arm", "body", "foot", "feet", "finger", "heart", "breath", "air",
    "moment", "second", "minute", "day", "night", "morning", "evening", "today",
    "tomorrow", "yesterday", "now", "then", "soon", "later", "always", "never",
    "again", "here", "there", "back", "away", "down", "up", "over", "under",
    "through", "across", "around", "past", "toward", "towards", "into", "onto",
    "from", "with", "without", "for", "against", "between", "among", "before",
    "after", "during", "while", "until", "since", "because", "though", "although",
    "however", "unless", "whether", "if", "so", "than", "as", "like", "unlike",
    "both", "either", "neither", "each", "every", "any", "some", "all", "most",
    "few", "several", "much", "many", "little", "less", "more", "most", "other",
    "another", "such", "own", "very", "too", "also", "just", "only", "even",
    "still", "yet", "already", "always", "never", "often", "sometimes",
    "usually", "rarely", "seldom", "once", "twice", "thrice", "again",
}


def terms_of(english):
    """The terms of a line: the words that are capitalised inside it.

    A word at the start of a sentence carries no information: every line
    starts with a capital. A word in the middle of a sentence that is
    capitalised is a name, a place, or a title of the game.
    """
    out = []
    for index, word in enumerate(WORD.findall(english)):
        if index == 0:
            continue
        if not word[:1].isupper():
            continue
        if word.lower() in STOP:
            continue
        if "'" in word or "’" in word:
            # a possessive is a form of the name it follows
            continue
        out.append(word)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write the missing terms into the glossary")
    parser.add_argument("--min-count", type=int, default=3)
    args = parser.parse_args()

    with io.open(CORPUS, encoding="utf-8", newline="") as fh:
        corpus = list(csv.reader(fh))[1:]
    with io.open(TRANSLATION, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.reader(fh))
    head = table[0]
    en_col = head.index("English")
    ru_col = head.index("Русский")
    translation = {row[1]: row[ru_col] for row in table[1:] if len(row) > ru_col}

    glossary = json.load(io.open(GLOSSARY, encoding="utf-8"))

    # the terms of the game, counted over the source
    source_terms = collections.Counter()
    lines_of = collections.defaultdict(list)
    for row in corpus:
        english = row[4]
        russian = translation.get(row[1], "")
        if not english:
            continue
        for term in terms_of(english):
            source_terms[term] += 1
            lines_of[term].append((row[1], russian))

    # the Russian form of a term: the name of the translation that stands
    # where the term stands. The word at the start of a Russian sentence
    # carries no information, so the words that open a line are not names.
    forms = collections.defaultdict(collections.Counter)
    for term, entries in lines_of.items():
        for _key, russian in entries:
            if not russian:
                continue
            ru_words = RU_WORD.findall(russian)
            ru_names = []
            for index, word in enumerate(ru_words):
                if not word[:1].isupper() or word.isupper():
                    continue
                if index == 0 and word in RU_OPENERS:
                    continue
                ru_names.append(word)
            if len(ru_names) != 1:
                continue
            forms[term][ru_names[0]] += 1

    missing = []
    for term, count in source_terms.most_common():
        if count < args.min_count:
            continue
        if term in glossary:
            continue
        found = forms.get(term, collections.Counter())
        if not found:
            continue
        missing.append((term, count, found))

    print("terms of the source without a glossary entry: %d" % len(missing))
    for term, count, found in missing:
        print("  %4d  %-22s %s" % (count, term, dict(found)))

    if args.apply:
        added = 0
        for term, _count, found in missing:
            if len(found) != 1:
                print("!! %s has more than one form: %s" % (term, dict(found)))
                continue
            ru = list(found)[0]
            if ru in glossary.values():
                continue
            glossary[term] = ru
            added += 1
        ordered = dict(sorted(glossary.items(), key=lambda kv: kv[0].lower()))
        with io.open(GLOSSARY, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(ordered, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        print("glossary: %d entries, %d added" % (len(glossary), added))


if __name__ == "__main__":
    main()
