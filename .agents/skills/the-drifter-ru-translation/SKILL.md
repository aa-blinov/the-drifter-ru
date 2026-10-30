---
name: the-drifter-ru-translation
description: Translate, revise, proofread, or QA the Russian text of The Drifter against its English source, the glossary, the literary voice, and the game's importer format. Use for dialogue, item descriptions, interface strings, terminology, and layout questions in this repository.
---

# Russian localization for The Drifter

Use this profile for Russian localization of The Drifter. It supplies this
game's facts, commands and traps. It does not authorize unrelated changes,
model calls, installation into a game directory, commits or releases.

## Before changing text

1. Read the repository `AGENTS.md` and `docs/style-guide.md`.
2. Read `docs/glossary.md` and `src/voice/glossary.json`. The glossary is
   frozen: a term is not renamed in one place to make a sentence read better.
3. Locate the exact English source in `corpus/english.csv` and check its
   repeats. One English line, one Russian line, in every place it occurs.
4. Keep the scope of the request. For a review, report the findings before
   editing unless the user asked for fixes.

## Translation and review

- Keep the noir voice: sober, tired, cynical, with the humour of the original.
  The narrator speaks in the first person.
- Keep the terms of the glossary. A glossary word is not replaced by a synonym.
- Keep the placeholders. Fifteen lines carry a `{0}`; a dropped placeholder is
  a broken line in the game.
- Do not invent lore. When the scene does not settle a question, the
  translation does not settle it either.
- Leave in Latin what the game's world is in: `Mulindji`, `Herr Doktor`,
  `MedCon`, `Quantum Cognition`, `Trinity Biotech`, `Wunyerra`.
- Persist every hand correction in both `translation/Russian/translation.csv`
  and `src/voice/manual_fixes.json`, then run the manual stage. A correction
  that lives only in the CSV is undone by the next run of the pipeline.

## The file the game reads

- The header is fixed: `Character,ID,File,Context,English,Русский`.
- The file is UTF-8 **with a BOM** and uses CRLF. The game's importer reads it
  as `Encoding.Default` with a BOM check; without the BOM the Cyrillic arrives
  as mojibake.
- The key of a line is the pair `(Character, ID)`, not the English string and
  not the line number.

## The fonts

The game's fonts carry no Cyrillic: a Russian line drawn with them comes out
as a row of runes. `scripts/install.py` merges the Cyrillic glyphs of Ark Pixel
Font into the game's fonts, on the pixel grid of each font. A translation
installed without the font patch is unreadable.

## Verification and reporting

Run the tests and the checks after edits:

```bash
python3 -m unittest discover -s tests -v
python3 src/drru/qa.py
```

Report the keys and files changed, the checks run, and the limits separately.
Never say that the translation is verified in the game when only the source
text was checked: no copy of the game is available in this repository, and
the width of a Russian line in a game panel has not been measured.

For the commands, the file format and the traps, read
[the project workflow reference](references/project-workflow.md).
