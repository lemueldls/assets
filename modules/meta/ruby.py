#!/usr/bin/env python3
"""
Asterism Ruby is the language variant: the Asterism cuts, annotated with pinyin
or romaji ruby above and below the Han characters. It is produced in three steps
that each belong where they are strongest:

  1. **rubify** annotates the Sarasa collection — it renders the ruby glyphs from
     the Asterism face, splits the collection, subsets to the annotated
     characters, and compresses. rubify is an annotation tool; it stops there.
  2. **this script** merges each annotated face with its Asterism counterpart and
     renames the result. Merging is a general operation with real subtleties —
     glyph renumbering, cmap closure, hmtx and layout reconciliation, name
     conflicts — and fonttools already solves them. `FontTools.merge` takes
     OS/2, name and panose from the *first* font, so the Asterism face leads and
     the annotated glyphs are added to it.
  3. the derivation installs a `truetype/` and a `woff2/` tree, the same shape the
     other cuts export, so the site's font generator treats Ruby as a normal cut
     rather than a special case.

Two things the merge needs that are not obvious:

  * The subset's **name table is empty** — rubify's subsetting strips it, so
    without the rename below the merged font has no family name at all and
    nothing can select it. This is also why renaming belongs here rather than in
    rubify: by the time a merge exists, the name is gone.
  * Only the weights the two families *share* are built. Sarasa publishes
    200/300/400/600/700; Asterism publishes 400/500/600/700/800/950. Synthesising
    a weight neither family ships would be a lie the manifest then records, so
    the overlap is what the catalogue gets, and the manifest says so.

    python3 ruby.py --work <rubify output> --asterism <slim>/share/fonts/truetype \
                    --out <pkg>/share/fonts --family "Asterism Ruby" --patch pinyin

Rubify is asked to keep only the annotated characters (`--subset`), which for
pinyin and romaji is the whole CJK Unified Ideographs block — around 21,000
glyphs. The merge with the Asterism face is what makes the result usable: about
4MB compressed per weight, Latin and Han alike, with both fonts' OpenType
features intact.
"""

from __future__ import annotations

import argparse
import sys
from io import BytesIO
from pathlib import Path

from fontTools.merge import Merger
from fontTools.ttLib import TTFont

DESIGN = "Sarasa-Gothic-CL"

STYLE_WEIGHTS = {
    "ExtraLight": 200,
    "Light": 300,
    "Regular": 400,
    "Medium": 500,
    "SemiBold": 600,
    "Bold": 700,
    "ExtraBold": 800,
    "Heavy": 900,
    "Black": 950,
}
WEIGHT_WORDS = {weight: word for word, weight in STYLE_WEIGHTS.items()}


def weight_of(path: Path) -> int | None:
    """Weight from `Sarasa-Gothic-CL-SemiBoldItalic`."""
    stem = path.stem
    if not stem.startswith(f"{DESIGN}-"):
        return None
    style = stem[len(DESIGN) + 1 :]
    if style.endswith("Italic"):
    return STYLE_WEIGHTS.get(style)


def merge(asterism: Path, subset: Path, out_dir: Path, family: str, patch: str, weight: int) -> None:
    """Merge the annotated subset into the Asterism face, and name it.

    Asterism goes first: the merger takes OS/2, panose and the name table from the
    first font, so the Latin face leads and the Han glyphs are added to it.
    """
    word = WEIGHT_WORDS.get(weight, "Regular")
    stem = f"{family.replace(' ', '')}{patch}-{word}"

    merged = Merger().merge([str(asterism), str(subset)])

    full = f"{family} {word}".replace(" Regular", "").strip()
    values = {
        1: family,
        2: word,
        3: f"{family.replace(' ', '')}-{patch}-{weight}",
        4: full,
        6: full.replace(" ", "-"),
        16: family,
        17: word,
    }

    languages = [
        (r.platformID, r.platEncID, r.langID) for r in merged["name"].names if r.nameID in values
    ]

    for name_id in (1, 2, 3, 4, 6, 16, 17):
        for platform, encoding, lang in languages:
            merged["name"].setName(values[name_id], name_id, platform, encoding, lang)

    plain = out_dir / "truetype" / f"{stem}.ttf"
    merged.save(str(plain))
    merged.close()

    compressed = TTFont(str(plain))
    compressed.flavor = "woff2"
    compressed.save(str(out_dir / "woff2" / f"{stem}.woff2"))
    compressed.close()
    return plain


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True, help="rubify's output directory")
    parser.add_argument("--asterism", type=Path, required=True, help="`<slim>/share/fonts/truetype`")
    parser.add_argument("--out", type=Path, required=True, help="`<pkg>/share/fonts`")
    parser.add_argument("--family", default="Asterism Ruby")
    parser.add_argument("--patch", required=True, help="annotation set, in the file name")
    args = parser.parse_args()

    for tree in ("truetype", "woff2"):
        (args.out / tree).mkdir(parents=True, exist_ok=True)

    built: list[tuple[int, Path]] = []
    for subset in sorted(args.work.glob("*.woff2")):
        weight = weight_of(subset)
        if weight is None:
            continue
        word = WEIGHT_WORDS[weight]
        asterism = args.asterism / f"AsterismSlim-{word}.ttf"
        if not asterism.exists():
            print(f"[ruby] no Asterism Slim face at {weight} — skipping")
            continue

        plain = merge(asterism, subset, args.out, args.family, args.patch, weight)
        built.append((weight, plain))
        woff2 = args.out / "woff2" / f"{plain.stem}.woff2"
        print(
            f"[ruby] {plain.name}: {plain.stat().st_size / 1e6:.1f} MB ttf, "
            f"{woff2.stat().st_size / 1e6:.1f} MB woff2"
        )

    if not built:
        print("[ruby] nothing to merge", file=sys.stderr)
        return 1

    weights = ", ".join(str(w) for w, _ in built)
    total = sum(p.stat().st_size for _, p in built)
    print(f"[ruby] {len(built)} faces at weights {weights}, {total / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
