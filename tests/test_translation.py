#!/usr/bin/env python
"""The checks that run in CI, over the file the game reads.

The tests read translation/Russian/translation.csv the way the game reads
it: as a file with a header, a BOM and CRLF. They never import the
pipeline, because the pipeline is not what ships.
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
            raise unittest.SkipTest("translation not built: %s" % TRANSLATION)
        cls.raw, cls.rows = read_translation()
        cls.header = cls.rows[0]
        cls.data = cls.rows[1:]

    def test_the_file_has_a_bom(self):
        # The game's importer reads the file as UTF-8 only when the byte
        # order mark is there. Without it the Cyrillic arrives as mojibake.
        self.assertTrue(self.raw.startswith(b"\xef\xbb\xbf"))

    def test_the_rows_are_separated_by_crlf(self):
        # A newline inside a quoted field is the data's own; the separator
        # between the rows is CRLF, and every row ends with one.
        self.assertTrue(self.raw.endswith(b"\r\n"))
        self.assertEqual(self.raw.count(b"\r\n"), len(self.rows))

    def test_the_header_is_the_one_the_game_expects(self):
        self.assertEqual(self.header[:5],
                         ["Character", "ID", "File", "Context", "English"])
        self.assertEqual(self.header[5], "Русский")

    def test_every_row_has_the_same_number_of_columns(self):
        for index, row in enumerate(self.data):
            self.assertEqual(len(row), 6, "row %d: %r" % (index, row))

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
                            "empty translation for %s|%s" % (row[0], row[1]))

    def test_no_prose_line_survived_unchanged(self):
        # A line the game shows as it is — an identifier, a number sequence,
        # a key name — has nothing to translate. A line of prose that came
        # back unchanged is a line nobody translated.
        for row in self.data:
            if checks.is_code(row[4]):
                continue
            self.assertNotEqual(row[4].strip(), row[5].strip(),
                                "untranslated: %s|%s" % (row[0], row[1]))

    def test_the_placeholders_survive(self):
        for row in self.data:
            self.assertEqual(sorted(checks.PLACEHOLDER.findall(row[4])),
                             sorted(checks.PLACEHOLDER.findall(row[5])),
                             "placeholder lost in %s|%s" % (row[0], row[1]))

    def test_no_straight_quotes(self):
        for row in self.data:
            self.assertNotIn('"', row[5],
                             "straight quote in %s|%s" % (row[0], row[1]))

    def test_no_three_dot_ellipsis(self):
        for row in self.data:
            self.assertNotIn("...", row[5],
                             "three dots in %s|%s" % (row[0], row[1]))

    def test_the_quotes_are_balanced(self):
        for row in self.data:
            self.assertEqual(row[5].count("«"), row[5].count("»"),
                             "unbalanced quotes in %s|%s" % (row[0], row[1]))

    def test_no_word_is_fused_across_two_scripts(self):
        for row in self.data:
            found = checks.FUSED.findall(row[5])
            self.assertEqual(found, [], "fused word in %s|%s: %r"
                             % (row[0], row[1], found))

    def test_the_only_latin_words_are_the_allowed_ones(self):
        for row in self.data:
            for word in checks.LATIN_WORD.findall(checks.strip_kept(row[5])):
                self.assertIn(word, checks.ALLOWED_LATIN,
                              "unexpected latin word %r in %s|%s"
                              % (word, row[0], row[1]))

    def test_one_english_line_has_one_russian_line(self):
        variants = {}
        for row in self.data:
            variants.setdefault(row[4], set()).add(row[5])
        for english, ru in variants.items():
            self.assertEqual(len(ru), 1,
                             "inconsistent rendering of %r: %r" % (english, ru))


if __name__ == "__main__":
    unittest.main()
