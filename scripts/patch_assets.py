#!/usr/bin/env python
"""The Cyrillic glyphs, patched into the fonts inside the game's assets.

The game keeps its fonts in `TheDrifter_Data/sharedassets1.assets`. The
fonts are raw byte arrays inside their objects, and the objects are
addressed by their place in the file.

Unity's reader for that file rebuilds it from the parsed objects, and the
rebuild loses the data of the objects it did not parse: the file comes back
a fraction of its size, and the game does not start. So the file is not
rebuilt from the parsed objects. Every object keeps its own bytes, and
only the fonts are replaced:

  1. the font of an object is read, the Cyrillic is merged into it, and
     the new bytes are put back into the object;
  2. the objects are written out with their own bytes, so that everything
     the file holds besides the fonts survives unchanged;
  3. the result is read back, every object is compared with the original,
     and the file is only put in place when they all match.

The result is written next to the original, read back, and only then put
in place.
"""
from __future__ import annotations

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from font_merge import merge, source_for  # noqa: E402
from font_metrics import Metrics, load_font  # noqa: E402


def font_objects(env):
    """Every font of the file, with the bytes it holds."""
    for obj in env.objects:
        if obj.type.name != "Font":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        raw = bytes(tree.get("m_FontData") or b"")
        if not raw:
            continue
        yield obj, tree.get("m_Name"), raw


def find_font_data(raw: bytes, font: bytes):
    """Where the font sits in the bytes of its object, and the length field
    that says how long it is."""
    offset = raw.find(font)
    if offset < 4:
        return None, None
    length = struct.unpack("<i", raw[offset - 4:offset])[0]
    if length != len(font):
        return None, None
    return offset, offset - 4


def patch_object(data: bytes, font: bytes, new_font: bytes):
    """The object with the new font in it, or None when it was not found."""
    offset, length_at = find_font_data(data, font)
    if offset is None:
        return None
    return (data[:length_at] + struct.pack("<i", len(new_font)) + new_font
            + data[offset + len(font):])


def patch_assets(assets_path: str, mode: str = "metric", fonts=None):
    """The file with the Cyrillic in its fonts."""
    import UnityPy

    env = UnityPy.load(assets_path)
    objects = list(env.objects)

    # Every object keeps its own bytes. Without this the writer rebuilds the
    # objects it did not parse, and the file loses most of its data.
    for obj in objects:
        try:
            obj.set_raw_data(obj.get_raw_data())
        except Exception:
            pass

    patched = 0
    for obj, name, raw_font in font_objects(env):
        if fonts and name not in fonts:
            continue
        target_metrics = Metrics(load_font(raw_font))
        source_path, _source_metrics = source_for(target_metrics)
        new_font, added, scale = merge(raw_font, source_path, mode)
        data = obj.get_raw_data()
        result = patch_object(data, raw_font, new_font)
        if result is None:
            print("!! could not find the font bytes of %s" % name)
            continue
        obj.set_raw_data(result)
        print("patched %-28s +%d glyphs, x-height scaled %.3f (%s)"
              % (name, added, scale, target_metrics.describe()))
        patched += 1

    if not patched:
        raise SystemExit("no font was patched")

    data = env.file.save()

    # The reader holds the file open, and Windows will not replace a file
    # that is held open.
    release(env)
    return data, patched


def release(env) -> None:
    """Let go of the files the reader holds.

    The reader keeps the file open, and Windows will not replace a file that
    is held open. The stream under the reader is the one that has to be
    closed.
    """
    for reader in env.file.files.values():
        stream = getattr(getattr(reader, "reader", None), "stream", None)
        if stream is not None and hasattr(stream, "close"):
            try:
                stream.close()
            except Exception:
                pass
    import gc
    gc.collect()


def verify(path: str, original_path: str) -> None:
    """The written file has to hold the same objects as the original."""
    import UnityPy

    before_env = UnityPy.load(original_path)
    before = {obj.path_id: obj for obj in before_env.objects}
    after_env = UnityPy.load(path)
    objects = list(after_env.objects)
    by_id = {obj.path_id: obj for obj in objects}

    if len(objects) != len(before):
        raise SystemExit("the written file holds %d objects, the original held %d"
                         % (len(objects), len(before)))

    differing = 0
    cyrillic = 0
    for path_id, obj in before.items():
        try:
            old = obj.get_raw_data()
            new = by_id[path_id].get_raw_data()
        except Exception:
            continue
        if old != new:
            differing += 1
        if obj.type.name == "Font":
            cyrillic += count_cyrillic(by_id[path_id])

    if differing > len(before) // 10:
        raise SystemExit("%d of %d objects changed: the patch is not a font patch"
                         % (differing, len(before)))
    if cyrillic < 1000:
        raise SystemExit("the written file holds %d Cyrillic glyphs, expected "
                         "more than a thousand" % cyrillic)
    print("verified: %d objects, %d changed, %d Cyrillic glyphs"
          % (len(objects), differing, cyrillic))

    # The reader keeps the file open, and Windows will not replace a file
    # that is held open.
    for env in (before_env, after_env):
        release(env)
    del before_env, after_env


def count_cyrillic(obj) -> int:
    """The Cyrillic glyphs a font object holds.

    The object holds the font as a byte array inside a larger structure, so
    the font is looked up by its own bytes rather than parsed out of the
    object.
    """
    try:
        tree = obj.read_typetree()
    except Exception:
        return 0
    raw = bytes(tree.get("m_FontData") or b"")
    if not raw:
        return 0
    try:
        font = load_font(raw)
    except Exception:
        return 0
    return len([c for c in font.getBestCmap() if 0x400 <= c <= 0x4FF])


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--mode", default="metric", choices=["metric", "grid"])
    parser.add_argument("--fonts", default="",
                        help="comma separated names of the fonts to patch")
    args = parser.parse_args()

    wanted = {name.strip() for name in args.fonts.split(",") if name.strip()}
    data, patched = patch_assets(args.assets, args.mode, wanted or None)

    with open(args.out, "wb") as fh:
        fh.write(data)
    print("wrote %s (%d bytes, was %d)"
          % (args.out, len(data), os.path.getsize(args.assets)))
    verify(args.out, args.assets)


if __name__ == "__main__":
    main()
