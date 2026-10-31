#!/usr/bin/env python
"""Проверки, которые идут в CI, над файлом, который читает игра.

Тесты читают translation/Russian/translation.csv так же, как его читает
игра: как файл с заголовком, BOM и CRLF. Пайплайн они не импортируют,
потому что в поставку идёт не пайплайн.
"""
from __future__ import annotations

import csv
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from drru import checks  # noqa: E402

TRANSLATION = os.path.join(ROOT, "translation", "Russian", "translation.csv")
CORPUS = os.path.join(ROOT, "corpus", "english.csv")


def read_translation():
    with open(TRANSLATION, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    return raw, rows


class TranslationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(TRANSLATION):
            raise unittest.SkipTest("перевод не собран: %s" % TRANSLATION)
        cls.raw, cls.rows = read_translation()
        cls.header = cls.rows[0]
        cls.data = cls.rows[1:]

    def test_the_file_has_a_bom(self):
        # Импортер игры читает файл как UTF-8, только если на месте маркер
        # порядка байтов. Без него кириллица приходит в виде мусора.
        self.assertTrue(self.raw.startswith(b"\xef\xbb\xbf"))

    def test_the_rows_are_separated_by_crlf(self):
        # Перевод строки внутри поля в кавычках принадлежит данным; разделитель
        # между строками это CRLF, и каждая строка на нём заканчивается.
        self.assertTrue(self.raw.endswith(b"\r\n"))
        self.assertEqual(self.raw.count(b"\r\n"), len(self.rows))

    def test_the_header_is_the_one_the_game_expects(self):
        self.assertEqual(self.header[:5],
                         ["Character", "ID", "File", "Context", "English"])
        self.assertEqual(self.header[5], "Русский")

    def test_every_row_has_the_same_number_of_columns(self):
        for index, row in enumerate(self.data):
            self.assertEqual(len(row), 6, "строка %d: %r" % (index, row))

    def test_the_row_count_is_the_corpus(self):
        with io.open(CORPUS, encoding="utf-8", newline="") as fh:
            corpus = list(csv.reader(fh))
        self.assertEqual(len(self.data), len(corpus) - 1)

    def test_the_keys_match_the_corpus(self):
        with io.open(CORPUS, encoding="utf-8", newline="") as fh:
            corpus = list(csv.reader(fh))[1:]
        for row, source in zip(self.data, corpus):
            self.assertEqual(row[0], source[0])
            self.assertEqual(row[1], source[1])
            self.assertEqual(row[2], source[2])
            self.assertEqual(row[3], source[3])
            self.assertEqual(row[4], source[4])

    def test_the_keys_are_unique(self):
        keys = [(row[0], row[1]) for row in self.data]
        self.assertEqual(len(keys), len(set(keys)))

    def test_no_line_is_empty(self):
        for row in self.data:
            self.assertTrue(row[5].strip(),
                            "пустой перевод для %s|%s" % (row[0], row[1]))

    def test_no_prose_line_survived_unchanged(self):
        # Строку, которую игра показывает как есть: идентификатор, числовую
        # последовательность, имя ключа, переводить нечего. Прозаическая строка,
        # которая вернулась без изменений, это строка, которую никто не перевёл.
        for row in self.data:
            if checks.is_code(row[4]):
                continue
            self.assertNotEqual(row[4].strip(), row[5].strip(),
                                "не переведено: %s|%s" % (row[0], row[1]))

    def test_the_placeholders_survive(self):
        for row in self.data:
            self.assertEqual(sorted(checks.PLACEHOLDER.findall(row[4])),
                             sorted(checks.PLACEHOLDER.findall(row[5])),
                             "потерян плейсхолдер в %s|%s" % (row[0], row[1]))

    def test_no_straight_quotes(self):
        for row in self.data:
            self.assertNotIn('"', row[5],
                             "прямая кавычка в %s|%s" % (row[0], row[1]))

    def test_no_three_dot_ellipsis(self):
        for row in self.data:
            self.assertNotIn("...", row[5],
                             "три точки в %s|%s" % (row[0], row[1]))

    def test_the_quotes_are_balanced(self):
        for row in self.data:
            self.assertEqual(row[5].count("«"), row[5].count("»"),
                             "непарные кавычки в %s|%s" % (row[0], row[1]))

    def test_no_word_is_fused_across_two_scripts(self):
        for row in self.data:
            found = checks.FUSED.findall(row[5])
            self.assertEqual(found, [], "склеенное слово в %s|%s: %r"
                             % (row[0], row[1], found))

    def test_the_only_latin_words_are_the_allowed_ones(self):
        for row in self.data:
            for word in checks.LATIN_WORD.findall(checks.strip_kept(row[5])):
                self.assertIn(word, checks.ALLOWED_LATIN,
                              "неожиданное латинское слово %r в %s|%s"
                              % (word, row[0], row[1]))

    def test_one_english_line_has_one_russian_line(self):
        variants = {}
        for row in self.data:
            variants.setdefault(row[4], set()).add(row[5])
        for english, ru in variants.items():
            # Строка из одного слова не несёт контекста. Игра использует одну
            # и ту же строку для разных слов: «Right» это ответ «Верно» в одной
            # сцене и команда «Вправо» в другой, и по самой строке их не отличить.
            if len(english.split()) < 2:
                continue
            self.assertEqual(len(ru), 1,
                             "непоследовательный перевод %r: %r" % (english, ru))


if __name__ == "__main__":
    unittest.main()
