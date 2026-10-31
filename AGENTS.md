# AGENTS.md, the agent context for `the-drifter-ru`

Русская локализация The Drifter: 9 803 строки в `translation/Russian/translation.csv`
и пайплайн, который их производит.

## Run / build / test

```bash
python3 -m unittest discover -s tests        # check the shipped CSV
python3 src/drru/qa.py                        # the checks, with the findings
python3 scripts/check_terms.py                # one term, one word
python3 src/drru/build.py                     # the corpus becomes the CSV
python3 scripts/fetch_fonts.py                # download the pixel fonts
python3 scripts/install.py --game "<path>"    # install into a copy of the game
```

The game itself: `python3 scripts/screenshot.py --out work/shots/scene.png`
takes the window of the running game, `scripts/click.py --at 960,515` clicks
in it, and `scripts/send_keys.py --keys "{ENTER}"` types in it.

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
python3 src/drru/proofread.py
python3 src/drru/translate.py --stage manual
python3 src/drru/qa.py
python3 src/drru/build.py
```

The stages write `work/corpus/*.jsonl`, and each one reads the file the
previous one wrote: `bulk` → `edit` → `canon` → `typo` → `polish` →
`final`. The build reads `final`.

The proofread stage is the reading pass: every line of the translation is read
against its English source, and the model names the lines it doubts. Every
finding is read by a human before it is changed.

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
  true. A line of one word is the exception: the game reuses the same string
  for different words («Right» is «Верно» in one scene and «Вправо» in
  another), and there is nothing in the line itself to tell them apart.
- **The importer wants UTF-8 with a BOM and CRLF.** Without the BOM the
  Cyrillic arrives as mojibake, and it is not a typo: it is the encoding.
- **The game reads `translation.csv` from its own directory**, and the name in
  the last column of the header is the name it shows in Options → Language.
- **The assets file is patched byte by byte, never rebuilt.** Unity's reader
  for it loses the data of the objects it did not parse: the file comes back
  1.3 MB instead of 30 MB, and the game does not start. The patch writes the
  bytes of the font data over the old ones and moves everything that follows.
- **Only the seven text fonts carry the Cyrillic.** The other thirteen are for
  titles and icons; a font without lowercase letters has no x-height to match,
  and the scale that follows from it produces a font the game cannot read.
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
- **One term, one word.** The glossary says a name has one Russian form, and
  the text has to agree with it. `scripts/check_terms.py` reads the lines
  where a term appears and names the ones rendered another way; the case
  endings are not a drift, but two spellings of one name are.
- **A term the glossary does not hold is translated again in every file of
  the script.** The batches do not cross the files of the script, so each
  file invents its own word for the term: `phase-flip` was written five ways
  in fifteen files, and `receptionist` four ways in six. The number of
  variants of a term is the number of files that mention it. Fill the
  glossary before the translation, not after — including the terms the text
  has not used yet.
- **The narrator speaks in the first person, the others in the third.** A
  line that begins with an English `He` or `She` about somebody else must not
  begin with a Russian `Я`. The proofreading pass finds these; they are the
  most common defect in the text.

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
- **The measured width of the Russian text is below the English one.** The
  median ratio is 0.85 to 0.96 and the ninety-ninth percentile is below 0.55;
  `docs/layout.md` holds the numbers and how they were taken.
