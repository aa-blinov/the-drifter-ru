# Contributing

Thanks for looking at the-drifter-ru.

## Before you open a pull request

- **Open an issue first** for anything larger than a fix. A design that is
  discussed in an issue costs less than a design that is discovered to be
  wrong after it is built.
- **One concern per pull request.** A fix and a refactor are two pull
  requests.
- **Match the existing code.** Read a file in full before changing it, and
  follow the conventions you find there rather than the ones you would
  choose.

## Changing a line of the translation

1. Find the English source in `corpus/english.csv` and check its repeats. The
   same English line appears in several places, and all of them must carry the
   same Russian.
2. Fix the line in `translation/Russian/translation.csv`.
3. Put the same wording in `src/voice/manual_fixes.json`, keyed by
   `Character|ID`. Without that, the next run of the pipeline will put the old
   wording back. The stage that applies them is
   `python src/drru/translate.py --stage manual`.
4. Keep the placeholders. Fifteen lines carry a `{0}`; a dropped placeholder is
   a broken line in the game, not a typo.
5. Run the checks:

   ```bash
   python3 -m unittest discover -s tests -v
   python3 src/drru/qa.py
   ```

6. Add an entry to `CHANGELOG.md` if the change is visible to a player.

## Changing the pipeline

- The stages do not import each other. Each reads a file and writes a file;
  the intermediate files under `work/` are the record of what each one did.
- Every model call is cached by the hash of model, system and user. A change
  to a prompt invalidates the cache of that stage and nothing else.
- `minimax-m3` with reasoning on spends 186 seconds on a batch of forty lines
  and 4.6 seconds with it off. The client sets `reasoning: {"effort": "none"}`; a
  stage that needs the model to think asks for it explicitly.
- A batch never crosses a source file. That is what keeps the dialogue of one
  scene together.

## House rules for the pull request

- `README.md` still describes what the project actually does. If your change
  alters the behaviour, the README changes in the same pull request.
- `CHANGELOG.md` has an entry, if the change is visible to a user.
- `docs/style-guide.md` still describes the voice. If your change alters the
  voice, the style guide and the glossary change with it.
- No dependency without a reason written down next to it.
- The game's files are the developer's. Nothing from a copy of the game is
  committed, and the installer backs up everything it touches.

## The code

- Python 3.10 or newer. The pipeline uses only the standard library; the
  installer needs UnityPy and fonttools.
- Comments explain *why*, never *what*.
- No emoji, in any file.
- There is no formatter and no linter. Follow the style of the neighbouring
  code and run the tests before you open the pull request.
