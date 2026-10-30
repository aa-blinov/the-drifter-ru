# Release process

The repository uses semantic versions. The release artifact is one file,
`translation/Russian/translation.csv`, plus the scripts that install it.

## Choose a version

- **Patch** (`0.1.1`): proofreading, terminology and documentation fixes that
  do not change the format of the file or the way it is installed.
- **Minor** (`0.2.0`): a substantial new pass over the text, or a new tool
  that stays compatible with the existing installation.
- **Major** (`1.0.0`): a change that breaks the format of the file or the
  instructions for installing it.

## Publish

1. Merge the reviewed pull request to `main` after `Check and test` and
   `House style` pass.
2. Move the release entries from `Unreleased` to a dated version section in
   `CHANGELOG.md`.
3. Push an annotated tag named `vX.Y.Z` at the release commit. The release
   workflow runs the tests, packages `translation/Russian/translation.csv` and
   publishes it.
4. Verify that the workflow succeeded and that the release has the expected
   archive before announcing it.

Do not reuse a published tag. If a release build fails, fix the cause in a
new commit and use a new version; do not move the tag.

## What is in the release

- `translation/Russian/translation.csv` — the file the game reads.
- `scripts/install.py` and `scripts/fetch_fonts.py` — the installation.
- `docs/` — the style guide, the glossary, the layout record.

The game itself is not in the release, and neither are the pixel fonts: the
fonts are fetched from their own project, under their own licence.

## The version of the game

The translation is built against the English corpus of a specific build of the
game. A game update that adds or changes lines leaves the new lines in
English. When the game updates, re-extract the corpus, translate what is new,
and record the build in `CHANGELOG.md`.
