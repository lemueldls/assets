#!/usr/bin/env python3
"""
The website's catalogue, its Open Graph card and the `assets` unifont provider
all read one index of the published fonts. This script is where it comes from.

It reads the *build outputs* rather than the bucket, which is the point of it
living here instead of in the site's repo: every fact below — glyph counts,
feature tags, vertical metrics, measure, file size — is taken off the exact file
that is about to be uploaded, so the manifest cannot describe a face that is not
published. The build produces both a `truetype/` and a `woff2/` tree from the
same outlines, so preferring the web build is a filesystem choice rather than a
guess about what is on the origin.

Nothing is fetched. Each table is read straight out of the file at its record
offset, which is the same walk an HTTP range request would make, minus the HTTP.

    python3 fonts.py --out fonts.meta.json <pkg>/share ...

The manifest shape is the site's `Font` type in shared/assets.ts; change one and
change the other.
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
from pathlib import Path

ASSETS_BASE_URL = os.environ.get("ASSETS_BASE_URL", "https://assets.lemueldls.dev")

MAX_FACE_BYTES = 8 * 1024 * 1024

FAMILY_NAMES = {
    "AsterismText": "Asterism Text",
    "AsterismSlim": "Asterism Slim",
    "AsterismCode": "Asterism Code",
    "AsterismTerm": "Asterism Term",
    "AsterismRuby": "Asterism Ruby",
    "IosevkaBook": "Asterism Text",
    "IosevkaSlim": "Asterism Slim",
    "IosevkaCode": "Asterism Code",
    "IosevkaTerm": "Asterism Term",
    "Sarasa": "Asterism Ruby",
}

STYLE_WEIGHTS = {
    "Thin": 100,
    "ExtraLight": 200,
    "Light": 300,
    "Regular": 400,
    "Book": 450,
    "Medium": 500,
    "SemiBold": 600,
    "Bold": 700,
    "ExtraBold": 800,
    "Heavy": 900,
    "Black": 950,
}

DEFAULT_ON_TAGS = {
    "abvf",
    "abvs",
    "blwf",
    "blws",
    "calt",
    "ccmp",
    "cjct",
    "clig",
    "curs",
    "half",
    "kern",
    "liga",
    "locl",
    "mark",
    "mkmk",
    "pref",
    "pres",
    "pstf",
    "rclt",
    "rphf",
    "rvrn",
    "vatu",
}


def build_rank(path: Path) -> int:
    return 1 if path.name.startswith("Asterism") else 0


PATCH_SUFFIXES = {
    "NerdFont": "Nerd Fonts",
    "Pinyin": "Pinyin",
    "Romaji": "Romaji",
}

PATCH_ORDER = {"base": 0, "Nerd Fonts": 1, "Pinyin": 2, "Romaji": 3}


class Face:
    __slots__ = ("path", "family", "patch", "weight", "italic", "format", "url")

    def __init__(self, path: Path, root: Path):
        self.path = path
        extension = path.suffix.lower()
        self.format = "woff2" if extension == ".woff2" else "truetype"

        stem = path.name[: -len(extension)]
        cut = stem.rfind("-")
        key = stem if cut == -1 else stem[:cut]
        style_word = "Regular" if cut == -1 else stem[cut + 1 :]

        self.italic = style_word.endswith("Italic")
        base = (style_word[:-6] or "Regular") if self.italic else style_word
        if base not in STYLE_WEIGHTS:
            raise ValueError(f"{path.name}: unknown style word {base!r}")
        self.weight = STYLE_WEIGHTS[base]

        self.patch = "base"
        for suffix, patch in PATCH_SUFFIXES.items():
            if key.endswith(suffix):
                self.patch = patch
                key = key[: -len(suffix)]
                break

        self.family = FAMILY_NAMES.get(key) or _split_camel(key)
        self.url = f"{ASSETS_BASE_URL}/{_bucket_key(path, root)}"

    @property
    def slot(self) -> str:
        return f"{self.family}|{self.patch}|{self.weight}|{self.italic}"


def _split_camel(key: str) -> str:
    out, previous = [], ""
    for ch in key:
        if ch.isupper() and previous and not previous.isupper():
            out.append(" ")
        out.append(ch)
        previous = ch
    return "".join(out).strip()


def _bucket_key(path: Path, root: Path) -> str:
    """Path as the bucket keys it: everything under `share/`."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise ValueError(f"{path} is not under {root}")
    return str(relative)


def empty_metrics() -> dict:
    return {"unitsPerEm": 0, "glyphs": 0, "ascender": 0, "descender": 0}


def table_directory(buf: bytes) -> dict[str, tuple[int, int]]:
    """sfnt table directory: tag -> (offset, length)."""
    if len(buf) < 12:
        return {}
    num_tables = struct.unpack(">H", buf[4:6])[0]
    directory = {}
    for i in range(num_tables):
        record = 12 + i * 16
        if record + 16 > len(buf):
            break
        tag = buf[record : record + 4].decode("latin-1").strip()
        offset, length = struct.unpack(">II", buf[record + 8 : record + 16])
        directory[tag] = (offset, length)
    return directory


def read_at(buf: bytes, offset: int, length: int) -> bytes:
    return buf[offset : offset + length]


def cmap_map(buf: bytes, directory: dict[str, tuple[int, int]]) -> dict[int, int]:
    """codepoint -> glyph id, from the best subtable the face packs."""
    if "cmap" not in directory:
        return {}
    start, length = directory["cmap"]
    table = read_at(buf, start, length)
    if len(table) < 4:
        return {}

    sub_tables = struct.unpack(">H", table[2:4])[0]
    best = None
    for i in range(sub_tables):
        entry = 4 + i * 8
        if entry + 8 > len(table):
            break
        platform, encoding = struct.unpack(">HH", table[entry : entry + 4])
        offset = struct.unpack(">I", table[entry + 4 : entry + 8])[0]
        score = (
            3 if platform == 3 and encoding in (10, 1) else 2 if platform == 0 else 1
        )
        if best is None or score > best[0]:
            best = (score, offset)
    if best is None:
        return {}

    sub = best[1]
    if sub + 2 > len(table):
        return {}
    fmt = struct.unpack(">H", table[sub : sub + 2])[0]
    mapping: dict[int, int] = {}

    if fmt == 4:
        seg_count_x2 = struct.unpack(">H", table[sub + 6 : sub + 8])[0]
        seg_count = seg_count_x2 // 2
        end_codes = sub + 14
        start_codes = end_codes + seg_count_x2 + 2
        id_deltas = start_codes + seg_count_x2
        id_range_offsets = id_deltas + seg_count_x2
        for s in range(seg_count):
            end = struct.unpack(">H", table[end_codes + s * 2 : end_codes + s * 2 + 2])[
                0
            ]
            start = struct.unpack(
                ">H", table[start_codes + s * 2 : start_codes + s * 2 + 2]
            )[0]
            delta = struct.unpack(
                ">h", table[id_deltas + s * 2 : id_deltas + s * 2 + 2]
            )[0]
            range_offset = struct.unpack(
                ">H", table[id_range_offsets + s * 2 : id_range_offsets + s * 2 + 2]
            )[0]
            for code in range(start, end + 1):
                if code == 0xFFFF:
                    continue
                if range_offset == 0:
                    glyph = (code + delta) & 0xFFFF
                else:
                    at = id_range_offsets + s * 2 + range_offset + (code - start) * 2
                    if at + 2 > len(table):
                        continue
                    glyph = struct.unpack(">H", table[at : at + 2])[0]
                    if glyph:
                        glyph = (glyph + delta) & 0xFFFF
                if glyph:
                    mapping[code] = glyph

    elif fmt == 12:
        if sub + 16 > len(table):
            return {}
        groups = struct.unpack(">I", table[sub + 12 : sub + 16])[0]
        for g in range(groups):
            entry = sub + 16 + g * 12
            if entry + 12 > len(table):
                break
            start, end, first = struct.unpack(">III", table[entry : entry + 12])
            for code in range(start, end + 1):
                mapping[code] = first + (code - start)

    return mapping


def read_facts(path: Path) -> tuple[list[str], dict]:
    """Feature tags and design metrics for a source build."""
    buf = path.read_bytes()
    if buf[:4] == b"ttcf":
        return [], empty_metrics()

    directory = table_directory(buf)
    if not directory:
        return [], empty_metrics()

    facts: dict = {}
    deferred: dict = {}

    units_per_em = 1000
    if "head" in directory:
        start, length = directory["head"]
        if length >= 20:
            units_per_em = (
                struct.unpack(">H", read_at(buf, start, length)[18:20])[0] or 1000
            )
    facts["unitsPerEm"] = units_per_em

    glyphs = 0
    if "maxp" in directory:
        start, length = directory["maxp"]
        if length >= 6:
            glyphs = struct.unpack(">H", read_at(buf, start, length)[4:6])[0]
    facts["glyphs"] = glyphs

    ascender = descender = 0
    number_of_h_metrics = 0
    if "hhea" in directory:
        start, length = directory["hhea"]
        table = read_at(buf, start, length)
        if len(table) >= 8:
            ascender, descender = struct.unpack(">hh", table[4:8])
        if len(table) >= 36:
            number_of_h_metrics = struct.unpack(">H", table[34:36])[0]
    facts["ascender"] = ascender
    facts["descender"] = descender

    if "OS/2" in directory:
        start, length = directory["OS/2"]
        table = read_at(buf, start, length)
        if len(table) >= 2:
            version = struct.unpack(">H", table[0:2])[0]
            if version >= 2 and len(table) >= 90:
                deferred["xHeight"], deferred["capHeight"] = struct.unpack(
                    ">hh", table[86:90]
                )

    measure = spacing = None
    if number_of_h_metrics and "hmtx" in directory:
        start, length = directory["hmtx"]
        hmtx = read_at(buf, start, min(length, number_of_h_metrics * 4))

        def advance_of(glyph: int) -> int:
            at = (glyph if glyph < number_of_h_metrics else number_of_h_metrics - 1) * 4
            return struct.unpack(">H", hmtx[at : at + 2])[0]

        cmap = cmap_map(buf, directory)
        probes = [cmap[ord(code)] for code in "inW0" if ord(code) in cmap]
        advances = {advance_of(g) for g in probes}
        if len(advances) == 1:
            spacing = "monospaced"
        elif advances:
            spacing = "proportional"

        n = cmap.get(0x6E)
        if n is not None:
            measure = round(advance_of(n) / units_per_em, 3)

    facts.update(deferred)
    if measure is not None:
        facts["measure"] = measure
    if spacing is not None:
        facts["spacing"] = spacing

    features: list[str] = []
    if "GSUB" in directory:
        start, length = directory["GSUB"]
        table = read_at(buf, start, length)
        if len(table) >= 8:
            feature_list = struct.unpack(">H", table[6:8])[0]
            if feature_list + 2 <= len(table):
                count = struct.unpack(">H", table[feature_list : feature_list + 2])[0]
                for i in range(count):
                    record = feature_list + 2 + i * 6
                    if record + 6 > len(table):
                        break
                    tag = table[record : record + 4].decode("latin-1").strip()
                    if tag and tag not in DEFAULT_ON_TAGS:
                        features.append(tag)

    return features, facts


def collect(roots: list[Path]) -> tuple[list[Face], list[Face], list[str]]:
    """Chosen faces, every published face, and the paths skipped and why.

    The second list is what the probe reads: facts are taken from a source build,
    so a face of a cut whose *web* build is the woff2 still needs its truetype
    sibling examined even though the manifest ships the woff2.

    Each root is a package's `share/`, so a bucket key is the path under it —
    `fonts/truetype/…`, the same key the origin holds it under.
    """
    skipped: list[str] = []
    everything: list[Face] = []
    chosen: dict[str, Face] = {}

    for root in roots:
        for fmt_dir in ("fonts/truetype", "fonts/woff2"):
            base = root / fmt_dir
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*")):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in (".ttf", ".ttc", ".woff2"):
                    continue
                if path.suffix.lower() == ".ttc":
                    skipped.append(
                        f"{_bucket_key(path, root)} — a collection, not a web build"
                    )
                    continue
                try:
                    face = Face(path, root)
                except ValueError as exc:
                    skipped.append(f"{exc}")
                    continue
                everything.append(face)

                existing = chosen.get(face.slot)
                if (
                    existing is None
                    or build_rank(face.path) > build_rank(existing.path)
                    or (
                        build_rank(face.path) == build_rank(existing.path)
                        and existing.format == "truetype"
                        and face.format == "woff2"
                    )
                ):
                    chosen[face.slot] = face

    faces = list(chosen.values())
    keep = [
        face
        for face in sorted(
            faces,
            key=lambda f: (f.family, PATCH_ORDER.get(f.patch, 9), f.weight, f.italic),
        )
        if face.path.stat().st_size <= MAX_FACE_BYTES
    ]
    return keep, everything, skipped


def _root_of(path: Path) -> Path:
    """The package root that `share/` hangs under, for report paths."""
    parts = path.parts
    for i, part in enumerate(parts):
        if part == "share":
            return Path(*parts[:i])
    return path.parent


def to_font(face: Face, features: list[str], metrics: dict) -> dict:
    font = {
        "name": face.family,
        "src": [{"url": face.url, "format": face.format}],
        "format": face.format,
        "weight": face.weight,
        "patch": face.patch,
        "features": features,
        "metrics": metrics,
        "bytes": face.path.stat().st_size,
    }
    if face.italic:
        font["style"] = "italic"
    return font


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path, help="`<pkg>/share` directories")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    for root in args.roots:
        if not root.is_dir():
            print(f"[fonts-meta] {root} is not a directory", file=sys.stderr)
            return 1

    faces, published_faces, skipped = collect(args.roots)

    from collections import defaultdict

    by_key: dict[str, list[Face]] = defaultdict(list)
    for face in published_faces:
        by_key[f"{face.family}|{face.patch}"].append(face)

    facts_cache: dict[str, tuple[list[str], dict]] = {}
    for key, group in by_key.items():
        probes = sorted(
            (f for f in group if f.format == "truetype" and not f.italic),
            key=lambda f: f.weight,
        )
        facts_cache[key] = (
            read_facts(probes[0].path) if probes else ([], empty_metrics())
        )

    meta: dict[str, list[dict]] = {}
    for face in faces:
        features, metrics = facts_cache[f"{face.family}|{face.patch}"]
        meta.setdefault(face.family, []).append(to_font(face, features, metrics))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(meta, indent=2) + "\n")

    total = sum(f.path.stat().st_size for f in faces)
    print(
        f"[fonts-meta] {len(meta)} families, {len(faces)} faces, {total / 1048576:.1f} MB"
    )
    for family, fonts in meta.items():
        facts = fonts[0]["metrics"]
        patches = sorted({f["patch"] for f in fonts})
        print(
            f"  {family:<18} {len(fonts):>2} faces  "
            f"{str(facts.get('spacing', '?')):<13} n {facts.get('measure', '?')}em  "
            f"{facts.get('glyphs', 0):>5} glyphs  {len(fonts[0]['features'])} features  "
            f"[{', '.join(patches)}]"
        )
    if skipped:
        print(f"[fonts-meta] skipped {len(set(skipped))} published paths:")
        for line in sorted(set(skipped)):
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
