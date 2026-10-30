#!/usr/bin/env python
"""Extract the English strings of the game into corpus/english.csv.

The game keeps its text in one MonoBehaviour inside
TheDrifter_Data/sharedassets1.assets: PowerTools.Quest.SystemText. Every
line of the game is one entry there, with the character who says it, the id
the game keys it by, the source file and the source function it came from.

The game files are the developer's. This script reads a copy the user owns
and writes only the text, never the assets.

    python3 src/drru/extract_corpus.py --game "C:/Program Files (x86)/Steam/steamapps/common/The Drifter"

Requires UnityPy. The output is sorted the way the game holds the strings,
so the indices of the corpus match the indices of the file.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys

SYSTEM_TEXT_CLASS = "PowerTools.Quest.SystemText"
# The path id of the SystemText MonoBehaviour in sharedassets1.assets.
SYSTEM_TEXT_PATH_ID = 28977


def load_systemtext(game_dir: str):
    import UnityPy
    assets = os.path.join(game_dir, "TheDrifter_Data", "sharedassets1.assets")
    if not os.path.exists(assets):
        raise SystemExit("not found: %s" % assets)
    env = UnityPy.load(assets)
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour" and obj.path_id == SYSTEM_TEXT_PATH_ID:
            return obj.read_typetree()
    raise SystemExit("SystemText not found in %s" % assets)


def strings_of(tree) -> list:
    out = []
    for entry in tree.get("m_strings", []):
        # The trailing spaces of a few strings are the game's own; the
        # importer keys on (character, id), so the corpus carries the text
        # without them.
        out.append({
            "character": entry.get("m_character", ""),
            "id": str(entry.get("m_id", "")),
            "file": entry.get("m_sourceFile", ""),
            "context": entry.get("m_sourceFunction", ""),
            "en": entry.get("m_string", "").rstrip(),
        })
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, help="the game's directory")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out = args.out or os.path.join(root, "corpus", "english.csv")

    tree = load_systemtext(args.game)
    rows = strings_of(tree)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["Character", "ID", "File", "Context", "English"])
        for row in rows:
            writer.writerow([row["character"], row["id"], row["file"],
                             row["context"], row["en"]])
    print("extract: %d strings -> %s" % (len(rows), out))


if __name__ == "__main__":
    main()
