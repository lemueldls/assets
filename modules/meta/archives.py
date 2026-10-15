#!/usr/bin/env python3
"""
One archive per cut and per format, plus one per annotation set of the language
variant, each holding that build's files and the license. Two formats because
they are two jobs rather than two qualities: a truetype archive is what a desktop
installs and what a self-hoster feeds through fonttools, a woff2 archive is what
a webpage loads and it is a quarter of the weight.

The woff2 set is the published one wherever the build produces it, and a
conversion where it does not — a row with a hole in it is worse than a
conversion that differs by a few kilobytes. Every cut builds WOFF2 today
(`features = "full"` and `webfontFormats` in `modules/fonts/asterism`), so the
conversion path is now a safety net rather than the route Code and Term take.

Granularity stops at cut x format on purpose. One weight per archive is a thing
nobody installs, and the per-face link on the catalogue already covers picking a
single weight or style.

    python3 archives.py --out <dir> --ofl OFL.txt \
        --cuts cuts.json   # [{name, pkg, glob}, ...]

Writes `<name>-truetype.zip`, `<name>-woff2.zip` and `archives.json` into the
output directory. The manifest is that JSON: it is written here, beside the
archives, so the size on a download link is the size of the file rather than an
estimate.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

from fontTools.ttLib import TTFont

COMPRESSION = zipfile.ZIP_STORED


def build_archive(
    out: Path, name: str, formats: dict[str, list[Path]], ofl: Path
) -> list[dict]:
    written: list[dict] = []

    for fmt, files in formats.items():
        target = out / f"{name}-{fmt}.zip"
        with zipfile.ZipFile(target, "w", COMPRESSION) as zf:
            zf.writestr("OFL.txt", ofl.read_bytes())
            for path in files:
                zf.writestr(path.name, path.read_bytes())
        written.append({"format": fmt, "bytes": target.stat().st_size})
        print(f"[archives] {target.name}: {target.stat().st_size / 1e6:.1f} MB")

    return written


def to_woff2(ttf: Path, dest_dir: Path) -> Path:
    font = TTFont(str(ttf))
    font.flavor = "woff2"
    target = dest_dir / f"{ttf.stem}.woff2"
    font.save(str(target))
    font.close()
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ofl", type=Path, required=True)
    parser.add_argument(
        "--cuts",
        type=Path,
        required=True,
        help="a JSON list of {name, pkg, glob} triples",
    )
    args = parser.parse_args()

    work = Path("work")
    args.out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, list[dict]] = {}

    for cut in json.loads(args.cuts.read_text()):
        name = cut["name"]
        pkg = cut["pkg"]
        glob = cut["glob"]

        truetype = sorted((Path(pkg) / "share/fonts/truetype").glob(glob))
        if not truetype:
            print(f"[archives] {name}: no files match {glob}", file=sys.stderr)
            return 1

        work.joinpath(name, "truetype").mkdir(parents=True, exist_ok=True)
        for font in truetype:
            work.joinpath(name, "truetype", font.name).write_bytes(font.read_bytes())

        web = sorted(
            (Path(pkg) / "share/fonts/woff2").glob(glob.replace("ttf", "woff2"))
        )
        work.joinpath(name, "woff2").mkdir(parents=True, exist_ok=True)
        if web:
            for font in web:
                work.joinpath(name, "woff2", font.name).write_bytes(font.read_bytes())
        else:
            for font in work.joinpath(name, "truetype").glob("*.ttf"):
                to_woff2(font, work.joinpath(name, "woff2"))

        formats = {
            "truetype": sorted(work.joinpath(name, "truetype").iterdir()),
            "woff2": sorted(work.joinpath(name, "woff2").iterdir()),
        }
        manifest[name] = build_archive(args.out, name, formats, args.ofl)

    (args.out / "archives.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"[archives] {len(manifest)} cuts, {sum(len(v) for v in manifest.values())} archives"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
