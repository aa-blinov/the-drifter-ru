#!/usr/bin/env python
"""Опись лора: все имена, которые использует текст, и то, чем они переданы.

Глоссарий держит решённые термины. Текст держит больше: имена, которые
никогда не записывали, титулы, места и слова мира. Скрипт читает корпус и
записывает, что там есть и чем оно стало, чтобы разъезд в имени, которое
глоссарий забыл, был виден.

    python3 scripts/lore_inventory.py            # опись
    python3 scripts/lore_inventory.py --drift    # термины, переданные двумя способами
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

TOKEN = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
# Слова, открывающие предложение, с большой буквы по правилам грамматики и
# ничего не говорят о мире.
STOP = {
    "The", "A", "An", "And", "But", "So", "If", "I", "You", "He", "She", "It",
    "We", "They", "There", "This", "That", "These", "Those", "When", "Where",
    "What", "Who", "Why", "How", "Not", "Now", "Then", "Yes", "No", "Oh", "Ah",
    "Well", "Come", "Go", "Get", "Got", "Give", "Gave", "Take", "Took", "See",
    "Saw", "Look", "Know", "Knew", "Think", "Thought", "Want", "Need", "Make",
    "Made", "Say", "Said", "Tell", "Told", "Can", "Could", "Would", "Should",
    "Will", "May", "Might", "Must", "Has", "Had", "Have", "Was", "Were", "Are",
    "Is", "Am", "Be", "Been", "Do", "Does", "Did", "My", "Your", "His", "Her",
    "Its", "Our", "Their", "Me", "Him", "Us", "Them", "Mine", "Yours", "Just",
    "Like", "Even", "Still", "Back", "Down", "Up", "Out", "Over", "Under",
    "About", "After", "Before", "Between", "From", "For", "With", "Without",
    "Into", "Onto", "Off", "One", "Two", "Three", "Four", "Five", "Six",
    "Seven", "Eight", "Nine", "Ten", "Very", "More", "Most", "Some", "Any",
    "All", "Each", "Every", "No", "Not", "Nothing", "Something", "Anything",
    "Everything", "Someone", "Anyone", "Everyone", "Nobody", "Right", "Wrong",
    "Good", "Bad", "Better", "Best", "Worse", "Worst", "Great", "Hello", "Goodbye",
    "Sorry", "Please", "Thank", "Thanks", "Yeah", "Okay", "Ok", "Hey", "Hi",
    "Come", "On", "In", "Out", "Of", "To", "At", "By", "As", "So", "Or", "Nor",
    "Yet", "Never", "Always", "Sometimes", "Often", "Once", "Twice", "Here",
    "There", "Now", "Then", "Today", "Tonight", "Tomorrow", "Yesterday",
    "Mr", "Mrs", "Ms", "Dr", "Sir", "Lord", "God", "Jesus", "Christ", "Fuck",
    "Shit", "Damn", "Hell", "Christ", "Heck", "Gosh", "Ah", "Oh", "Ooh", "Oof",
    "Come", "Look", "Listen", "Watch", "Wait", "Stop", "Start", "Begin", "End",
    "Head", "Hand", "Eye", "Face", "Door", "Room", "House", "Home", "Street",
    "Road", "City", "Town", "Country", "World", "Water", "Air", "Fire", "Light",
    "Dark", "Night", "Day", "Morning", "Evening", "Time", "Year", "Month",
    "Week", "Hour", "Minute", "Second", "Name", "Word", "Thing", "People",
    "Person", "Man", "Woman", "Men", "Women", "Child", "Kids", "Boy", "Girl",
    "Dad", "Mum", "Mom", "Dad", "Ma", "Pa", "Bro", "Sis", "Tommy", "Tilly",
    "Please", "Sorry", "Excuse", "Welcome", "Hello", "Farewell", "Goodbye",
    "K", "M", "OK", "Let's", "Don't", "Doesn't", "Didn't", "Can't", "Won't",
    "Couldn't", "Wouldn't", "Shouldn't", "Isn't", "Aren't", "Wasn't", "Weren't",
    "Hasn't", "Haven't", "Hadn't", "I'll", "I've", "I'd", "I'll", "I'm",
    "He's", "She's", "It's", "We're", "They're", "There's", "Who's", "What's",
    "Where's", "How's", "That's", "Here's", "There's", "Let's", "Gonna", "Wanna",
    "Gimme", "Lemme", "C'mon", "Y'know", "Y'all", "Ain't", "Don't", "Didn't",
    "Freakin", "Hell", "Shit", "Fucking", "Bloody", "Goddamn", "Christ",
    "Maybe", "You're", "Sure", "Looks", "Guess", "Wonder", "We'll", "You'll",
    "Ugh", "Let", "Another", "Ha", "Huh", "Gotta", "We've", "Alright", "Only",
    "Though", "He'll", "You've", "Hmm", "Too", "Agh", "Found", "Empty", "Ahh",
    "Seems", "Hold", "Hey", "Sure", "Want", "Help", "Come", "Did", "Does",
    "Don't", "Can't", "Won't", "Isn't", "Aren't", "Wasn't", "Didn't", "Couldn't",
    "Wouldn't", "Shouldn't", "Haven't", "Hasn't", "Hadn't", "Let's", "That's",
    "Here's", "There's", "What's", "Who's", "Where's", "How's", "I'd", "I've",
    "I'll", "I'm", "He's", "She's", "It's", "They're", "You're", "Gonna",
    "Wanna", "Ain't", "Freakin", "Fucking", "Bloody", "Christ", "Yeah", "Okay",
    "Ok", "Hi", "Hello", "Sorry", "Please", "Thanks", "Thank", "Guess",
    "Nothing", "Something", "Anything", "Everything", "Anyone", "Everyone",
    "Nobody", "Somebody", "Anybody", "Everybody", "Now", "Then", "Here",
    "There", "Today", "Tonight", "Tomorrow", "Yesterday", "Right", "Left",
    "Up", "Down", "Back", "Away", "Over", "Under", "Out", "Off", "In", "On",
    "Of", "To", "At", "By", "As", "Or", "Nor", "Yet", "So", "If", "And", "But",
    "For", "With", "From", "Into", "Onto", "About", "After", "Before",
    "Between", "Through", "During", "Without", "Against", "Around", "Above",
    "Below", "Under", "Inside", "Outside", "Beside", "Behind", "Beyond",
    "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "First", "Second", "Third", "Fourth", "Last", "Next", "Every",
    "Each", "Both", "All", "Any", "Some", "Most", "More", "Less", "Other",
    "Another", "Such", "Very", "Too", "Just", "Even", "Still", "Already",
    "Never", "Always", "Often", "Sometimes", "Once", "Twice", "Again",
    "Sure", "Right", "Wrong", "Well", "Good", "Bad", "Better", "Best",
    "Worse", "Worst", "Great", "Nice", "Fine", "Real", "True", "False",
    "Only", "Whole", "Half", "Whole", "Whole", "Enough", "Plenty",
}


def terms_of(english: str):
    """Написанные с большой буквы слова строки и их места."""
    out = []
    words = TOKEN.findall(english)
    for index, word in enumerate(words):
        if not word[:1].isupper():
            continue
        if word in STOP:
            continue
        if word.isupper() and len(word) > 2:
            # Аббревиатура: метка интерфейса.
            continue
        out.append(word)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", default="",
                        help="строки, которые упоминают термин")
    parser.add_argument("--limit", type=int, default=3,
                        help="сколько упоминаний показать")
    parser.add_argument("--min", type=int, default=3,
                        help="наименьшее число упоминаний у термина")

    args = parser.parse_args()

    with io.open(CORPUS, encoding="utf-8", newline="") as fh:
        corpus = list(csv.reader(fh))[1:]
    with io.open(TRANSLATION, encoding="utf-8-sig", newline="") as fh:
        table = list(csv.reader(fh))
    ru_col = table[0].index("Русский")
    translation = {"%s|%s" % (r[0], r[1]): r[ru_col] for r in table[1:]}
    glossary = json.load(io.open(GLOSSARY, encoding="utf-8"))

    # термины источника и строки, которые их упоминают
    mentions = collections.defaultdict(list)
    for row in corpus:
        english = row[4]
        russian = translation.get("%s|%s" % (row[0], row[1]), "")
        if not english or not russian:
            continue
        for term in terms_of(english):
            mentions[term].append((row[0], row[1], english, russian))

    if args.show:
        wanted = args.show.lower()
        for term in sorted(mentions, key=lambda t: -len(mentions[t])):
            if wanted not in term.lower():
                continue
            print("=" * 78)
            print("%s: %d упоминаний, в глоссарии: %s"
                  % (term, len(mentions[term]), glossary.get(term, "нет")))
            for character, ident, english, russian in mentions[term][:args.limit]:
                print("  EN: %s" % english[:92])
                print("  RU: %s" % russian[:92])
        return

    print("терминов источника: %d" % len(mentions))
    print()
    print("%-28s %6s  %s" % ("термин", "число", "в глоссарии"))
    for term in sorted(mentions, key=lambda t: -len(mentions[t])):
        if len(mentions[term]) < args.min:
            continue
        print("%-28s %6d  %s"
              % (term, len(mentions[term]), glossary.get(term, "нет")))


if __name__ == "__main__":
    main()
