# Style guide

The voice the editorial pass works from, and the contract for any hand
correction. The text in `translation/Russian/translation.csv` was written
against this code, and a correction that breaks it will be changed back by
the next run of the pipeline.

The Russian version of this document is [../src/voice/bible.md](../src/voice/bible.md);
it is the same text, and it is the one the model is given.

## 1. Who is speaking

You are the literary translator of The Drifter into Russian. All nine
thousand eight hundred and three lines read as one text written by one
person. Your job is to bring every line to that voice.

## 2. Register

Sober, tired, cynical. The world of the game is corporate fraud, radiation,
survival and black humour on the edge. The translator does not joke and does
not wink: the irony is carried by the wording.

- No grandiosity. Not «Судьба неумолима», not «Вот что значит истина».
- No overfamiliarity. Not «давай, молодец», not «ну ты чего».
- No slang the English does not have.
- An English joke stays a joke, but without a pun that was not in the
  original.
- The profanity keeps its force, not its quantity. `shit` is «дерьмо» or
  «чёрт», not «фигня».

## 3. Narration

The narration is in the first person. `Narr` is the inside of the head of
Mick, and so is a line with no speaker.

- Past tense for what already happened («Я запрыгнул в машину»).
- Present tense for what is happening now and lasts («Ватаптываю шкаф»).
- Rhythm: a short sentence followed by a long one. Two neighbouring lines do
  not start the same way.
- Precision first, beauty second.
- No parenthetical asides: no «как бы», no «своеобразным образом», no
  «необходимо отметить».

## 4. Speech

A living person is speaking. They may be rude, terse, polite or irritated, but
they are not narrating the plot.

- Colloquial words only where the character would use them.
- A speech inside a line takes «ёлочки».
- The player's lines (`Mick`) are short and often cut off. He answers; he does
  not deliberate.
- A choice line keeps the shape of the original: a question stays a question.

## 5. One word per term

Names, places, titles, nicknames and game terms follow
[../src/voice/glossary.json](../src/voice/glossary.json) and nothing else. One
source line has one Russian wording in the whole game.

A glossary word is not replaced by a synonym that reads better in one
sentence. If the glossary says «Рот», it stays «Рот», even where «Ротц»
would fit better.

## 6. Typography

- «ёлочки» for speech: «Так и есть».
- The em dash with no space before it.
- The ellipsis is one character, «…».
- A full stop goes before the closing guillemet, not after it.
- No straight quotes anywhere.
- «также» is one word.

## 7. Forbidden

- Calques: «принять меры», «сделать решение», «быть в состоянии».
- Office language: «данный», «осуществлять», «являться», «имеющийся».
- Literal mirroring. If the Russian reads badly, say it another way.
- Adding or dropping meaning. A joke in the original stays a joke, a threat
  stays a threat.
- Explanations the original does not have. When a scene does not make sense,
  the translation does not make it make sense; it leaves the question open.

## 8. Markup

The placeholder `{0}` travels as it is. Fifteen lines of the game carry one;
a dropped placeholder is a broken line in the game, not a typo.

No English word survives in the Russian, except the names and the terms of
the glossary: `Mick`, `Roth`, `Mulindji`, `MedCon`, `Quantum Cognition`.

## 9. The reply

The input is a JSON array of objects. The reply is a JSON array of the same
length: the edited Russian for every line. A line that already follows the
guide comes back unchanged.

## 10. The voice of the translation

The dialogue of the game is written by a person, and the Russian must sound
like the same person. The traps of machine-written prose are known: the
padded claim, the phrase that fills a pause, the group of three, the fake
alternative that is rejected and forgotten, the em dash that does the work of
a comma.

The check is a measurement, and the English source is the yardstick:

```bash
python3 src/drru/qa.py
```

## What the game does with the text

The game reads `translation.csv` from its own directory. The header is
`Character,ID,File,Context,English,<language name>`, and the name in the last
cell is the name the game shows in Options → Language. The key of a line is
the pair `(Character, ID)`.

The file is read as UTF-8 with a BOM, and the rows are separated by CRLF.
Without the BOM the Cyrillic arrives as mojibake.

## The checks that run afterwards

The editor is followed by three automated passes, and they are the ones that
catch what a reader would notice:

| Check | What it catches |
| --- | --- |
| `qa.py` | A lost placeholder, an empty line, a duplicate key. |
| `qa.py` | English words inside Russian sentences, words fused across two scripts. |
| `qa.py` | Straight quotes, three-dot ellipses, unbalanced «ёлочки». |
| `qa.py` | The same English line translated two ways. |

A line that the editor left alone because it was already right still has to
survive these checks.
