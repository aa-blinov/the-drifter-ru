---
name: the-drifter-ru-translation
description: Translate, revise, proofread, or QA the Russian text of The Drifter against its English source, the glossary, the literary voice, and the game's own fonts and importer. Use for dialogue, item descriptions, interface strings, terminology, and layout questions in this repository.
---

# Russian localization for The Drifter

Use this profile for Russian localization of The Drifter. For the reusable
method — from glossary through editorial passes to runtime validation — also
follow [the game localization pipeline](../game-localization-pipeline/SKILL.md).
This profile supplies this game's facts, commands and traps; it does not
authorize unrelated changes, model calls, installation into a game directory,
commits or releases.

## Before changing text

1. Read the repository `AGENTS.md` and `docs/style-guide.md`.
2. Read `docs/glossary.md` and `src/voice/glossary.json`. The glossary is
   frozen: a term is not renamed in one place to make a sentence read better.
3. Locate the exact English source in `corpus/english.csv` and check its
   repeats. One English line, one Russian line, in every place it occurs.
4. Follow the requested scope. For a review, report the findings before
   editing unless the user asked for fixes. Do not rewrite unrelated strings.

## Translation and review

- Keep the noir voice: sober, tired, cynical, with the humour of the
  original. The narrator speaks in the first person.
- Keep the terms of the glossary. A glossary word is not replaced by a
  synonym.
- Keep the placeholders. Fifteen lines carry a `{0}`; a dropped placeholder
  is a broken line in the game.
- Do not invent lore. When the scene does not settle a question, the
  translation does not settle it either.
- The game is the primary source of its own lore. Where a published account
  of the game disagrees with it — the encyclopaedia, a review — the game is
  right and the translation follows the game. What was checked and what was
  fixed is written down in `docs/lore.md`.
- A term that the glossary does not hold is translated again in every file
  of the script, and every file invents its own word for it: the `phase-flip`
  of the game was written five ways in fifteen files, because the batches do
  not cross the files of the script and the term was not in the glossary when
  the bulk pass ran. Before the next translation run, every term of the world
  has to be in `src/voice/glossary.json` — including the ones the text has
  not used yet.
- Leave in Latin what the game's world is in: `Mulindji`, `Herr Doktor`,
  `MedCon`, `Quantum Cognition`, `Trinity Biotech`, `Wunyerra`.
- Persist every hand correction in both `translation/Russian/translation.csv`
  and `src/voice/manual_fixes.json`, then run the manual stage. A correction
  that lives only in the CSV is undone by the next run of the pipeline.

## The file the game reads

- The header is fixed: `Character,ID,File,Context,English,Русский`.
- The file is UTF-8 **with a BOM** and uses CRLF. The game's importer reads
  it as `Encoding.Default` with a BOM check; without the BOM the Cyrillic
  arrives as mojibake.
- The key of a line is the pair `(Character, ID)`, not the English string and
  not the line number.
- The name in the last column of the header is the name the game shows in
  Options → Language.

## The fonts

The game draws its text with seven fonts in its own assets, and none of them
carries a Cyrillic glyph: without the patch a Russian line is drawn with a
system font and looks foreign next to the English.

`scripts/patch_assets.py` merges the glyphs of Ark Pixel Font into those
seven fonts and scales them to the x-height of the Latin in the same font, so
a Russian line has the same weight and stands on the same baseline. The
assets are patched byte by byte: Unity's reader for that file loses the data
of the objects it did not parse, and the file comes back 1.3 MB instead of
30 MB, which is a game that does not start.

The other thirteen fonts of the game are for titles and icons. The Cyrillic
does not belong in them: a font without lowercase letters has no x-height to
match, and the scale that follows from it produces a font the game cannot
read.

## Verification and reporting

Run the tests and the checks after edits:

```bash
python3 -m unittest discover -s tests -v
python3 src/drru/qa.py
python3 scripts/check_terms.py
python3 scripts/check_fixes.py
python3 scripts/lore_inventory.py
python3 scripts/scan_ai_patterns.py
```

The lore and the chronology are checked apart:

```bash
python3 scripts/chronology.py --year      # the years the text names
python3 scripts/chronology.py --show "five"
```

A name that the glossary does not hold is a name that can drift: the
inventory shows which ones. A date that moved is a story that moved: the
chronology shows every time reference, and what carries it in Russian.

The proofreading stage reads every line against its English source:

```bash
python3 src/drru/proofread.py
```

It names the lines it doubts. Read every finding before it is changed: the
model is a detector, and a line it doubts and the source does not support is
left alone. The findings that are real go into `translation/Russian/translation.csv`
and into `src/voice/manual_fixes.json`, and the manual stage applies them.

The game itself is the last check. `scripts/screenshot.py` takes the window
of the running game, `scripts/click.py` clicks in it and `scripts/send_keys.py`
types in it:

```bash
python3 scripts/install.py --game "<path to The Drifter>"
python3 scripts/screenshot.py --out work/shots/scene.png
```

Report the keys and files changed, the checks run, and the limits separately.
Never say that the translation is verified in the game when only the source
text was checked.

For the commands, the file format and the traps, read
[the project workflow reference](references/project-workflow.md).
