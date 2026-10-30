# AGENTS.md, the agent context for `the-drifter-ru`

Русская локализация The Drifter: 9 803 строки в `translation/Russian/translation.csv`
и пайплайн, который их производит.

## Run / build / test

```bash
python3 -m unittest discover -s tests        # check the shipped CSV
python3 src/drru/qa.py                        # the checks, with the findings
python3 src/drru/build.py                     # the corpus becomes the CSV
python3 scripts/fetch_fonts.py                # download the pixel fonts
python3 scripts/install.py --game "<path>"    # install into a copy of the game
```

The pipeline needs a model endpoint. `src/drru/llm_client.py` reads it from
`DRRU_BASE_URL` (default `http://127.0.0.1:8788/v1`) and `DRRU_MODEL` (default
`minimax-m3`). Every call is cached under `work/cache/`, so a re-run costs
nothing until the prompt changes.

Full run:

```bash
python3 src/drru/extract_corpus.py --game "<path to The Drifter>"
python3 src/drru/translate.py --stage bulk
python3 src/drru/translate.py --stage editorial
python3 src/drru/canonicalise.py
python3 src/drru/typography.py
python3 src/drru/polish.py
python3 src/drru/translate.py --stage manual
python3 src/drru/qa.py
python3 src/drru/build.py
```

The stages write `work/corpus/*.jsonl`, and each one reads the file the
previous one wrote: `bulk` → `edit` → `canon` → `typo` → `polish` →
`final`. The build reads `final`.

## Where things live

| Path | What it is |
| --- | --- |
| `translation/Russian/translation.csv` | The file the game reads. The artifact. |
| `corpus/english.csv` | The English corpus, with the keys and the context. |
| `src/drru/` | The pipeline: corpus, translation, editorial pass, QA, build. |
| `src/voice/` | The style code, the frozen glossary, the hand corrections. |
| `scripts/` | The installer, the font download. |
| `tests/` | The checks that run in CI. |
| `docs/` | The architecture, the style guide, the glossary, the layout record. |
| `work/` | Scratch: the corpus, the cache, the intermediate passes. Not committed. |

## Traps

- **The game keys its text by (Character, ID).** Not by the English string, not
  by the line number. The same English line appears in several places, and the
  translation has to be the same in all of them. `src/drru/canonicalise.py`
  enforces that; running it after any hand edit is the cheapest way to keep it
  true.
- **The importer wants UTF-8 with a BOM and CRLF.** Without the BOM the
  Cyrillic arrives as mojibake, and it is not a typo: it is the encoding.
- **The column code is the language code.** The header is
  `Character,ID,File,Context,English,Русский`, and the last cell is what the
  game shows in Options → Language.
- **The game's fonts carry no Cyrillic.** The game draws a Russian line in its
  own font as a row of runes, the same way it draws a missing glyph. The
  installer merges the Cyrillic glyphs in; a translation installed without the
  font patch is unreadable.
- **The build reads `final.jsonl`.** Building from an earlier stage ships the
  defects the typography and the polish stage exist to remove.
- **The model's reasoning trace is expensive.** `minimax-m3` spends 186 seconds
  on a batch of forty lines with reasoning on and 4.6 seconds with it off. The
  client sets `reasoning: {"effort": "none"}` by default.
- **The placeholders are `{0}`.** Fifteen lines carry one. A dropped
  placeholder is a broken line in the game, not a typo.
- **The English source is the yardstick.** A Russian line that carries a word
  the English does not carry is a wrong line. The QA stage looks for Latin
  words inside a Russian sentence.
- **`Mulindji`, `Herr Doktor`, `MedCon` stay in Latin.** They are the world's
  words, not the translation's.

## Style / safety rails

- **Comments explain *why*, never *what*.**
- **No emojis**, in any file.
- **Do not add a dependency without a reason written down next to it.**
- **Do not remove functionality that looks intentional.** Ask first.
- **The voice is fixed.** `docs/style-guide.md` is the contract with the
  editor; a hand edit that breaks it will be corrected by the next run of the
  editorial pass.
- **A correction goes into the CSV file and into
  `src/voice/manual_fixes.json`**, or the next run of the pipeline will undo
  it.
- **The game's files are the developer's.** The repository holds the text and
  the tooling. The installer reads a copy the user owns and backs up what it
  touches.
