#!/usr/bin/env python3
"""
One entry per wallpaper, keyed by file name, carrying the size the gallery lays
its grid out with, the quantised palette the accent thread and the ascii plate
are drawn from, and the accent chosen for each ground.

It reads the *build output* rather than the bucket. The package retints every
source image to catppuccin-mocha and catppuccin-latte and copies a curated cycle,
so the originals sitting at the root of `images/` are exactly what the manifest
describes — and the manifest cannot name a file that is not being uploaded.

Because the derivation is content-addressed there is no cache to keep: if the
images change nix re-runs this, and if they do not nix serves the previous
output. A wallpaper runs to 5MB and the answer is six colours, so the profile is
downscaled to 64×64 before the k-means rather than after.

    python3 walls-meta.py --out walls.meta.json <pkg>/share/wallpapers/...
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

ASSETS_BASE_URL = os.environ.get("ASSETS_BASE_URL", "https://assets.lemueldls.dev")

K = 6

INK = "#11111b"
PAPER = "#eff1f5"

PROFILE = 64

TAG_RULES = [
    (re.compile(r"^dominik-mayer"), "dominik-mayer"),
    (re.compile(r"^voyager"), "voyager"),
    (re.compile(r"^flowers"), "flowers"),
    (re.compile(r"^pixel-"), "pixel-art"),
    (re.compile(r"^voxel"), "voxel"),
    (re.compile(r"^sjml-"), "anime"),
    (
        re.compile(
            r"frieren|mushishi|kusuriya|koishi|maji-no-tabitabi|fumo|koi|lain|komorebi"
        ),
        "anime",
    ),
    (re.compile(r"touhou|sakura"), "anime"),
    (
        re.compile(r"hollow-knight|kaiju|dragon|samurai|knight|excalibur|sword"),
        "fantasy",
    ),
    (re.compile(r"lake-hylia|outset-island|zelda"), "gaming"),
    (
        re.compile(r"space|jupiter|black-hole|galaxy|eclipse|stars|comets|planet"),
        "space",
    ),
    (re.compile(r"city|street|market|station|subway|trolley|bus"), "urban"),
    (
        re.compile(
            r"forest|tree|valley|mountain|lake|river|sea|ocean|beach|cloud|wave"
        ),
        "landscape",
    ),
    (re.compile(r"sunset|sunrise|bluehour|horizon|glow"), "sunset"),
]


def tags_for(file: str) -> list[str]:
    stem = Path(file).stem.lower()
    return sorted({tag for pattern, tag in TAG_RULES if pattern.search(stem)})


def parse_hex(hex_code: str) -> tuple[int, int, int]:
    value = hex_code.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def to_hex(rgb) -> str:
    return "#" + "".join(f"{min(255, max(0, round(c))):02x}" for c in rgb)


def relative_luminance(rgb) -> float:
    def lin(channel: int) -> float:
        s = channel / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = relative_luminance(parse_hex(a)), relative_luminance(parse_hex(b))
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def shift_towards(hex_code: str, amount: float, towards: str) -> str:
    r, g, b = parse_hex(hex_code)
    channels = [r, g, b]
    out = [
        c + (255 - c) * amount if towards == "white" else c * (1 - amount)
        for c in channels
    ]
    return to_hex(out)


def clamp_accent(accent: str, ground: str, minimum: float = 4.5) -> str:
    """Nudge an accent until it clears `minimum` against `ground`.

    Wallpapers are allowed to be loud; text set in their accent is not. Walks
    lightness in whichever direction has further to travel, and falls back to the
    closest it reached rather than to the original, so a pathologically flat
    palette still returns something legible.
    """
    if contrast_ratio(accent, ground) >= minimum:
        return accent

    towards = "white" if relative_luminance(parse_hex(ground)) < 0.5 else "black"
    closest, best = accent, contrast_ratio(accent, ground)

    for step in range(1, 25):
        candidate = shift_towards(accent, step / 24, towards)
        ratio = contrast_ratio(candidate, ground)
        if ratio >= minimum:
            return candidate
        if ratio > best:
            best, closest = ratio, candidate

    return closest


def chroma(rgb) -> int:
    return int(max(rgb) - min(rgb))


def accent_score(rgb) -> float:
    """Chromata at mid luminance.

    "Most saturated" is the obvious rule and it is wrong: a photograph of pink
    roses contains dark green leaves, and dark green has the higher saturation, so
    the accent comes out olive. What actually reads as a wallpaper's colour is
    chroma at mid luminance — strong enough to have presence, light enough to be
    seen. The Gaussian around 0.45 penalises both ends.
    """
    return chroma(rgb) * math.exp(-((relative_luminance(rgb) - 0.45) ** 2) / 0.06)


def kmeans(pixels: np.ndarray, k: int, iterations: int = 12):
    """Deterministic Lloyd's; returns (centroids, populations), largest first."""
    if len(pixels) == 0:
        return np.zeros((0, 3)), np.zeros(0, dtype=int)

    indices = [(i * len(pixels)) // k for i in range(k)]
    centroids = pixels[indices].astype(float)

    assignment = np.zeros(len(pixels), dtype=int)
    for _ in range(iterations):
        weights = np.array([2.0, 4.0, 3.0])
        distances = ((pixels[:, None, :] - centroids[None, :, :]) ** 2 * weights).sum(
            axis=2
        )
        best = distances.argmin(axis=1)
        if np.array_equal(best, assignment):
            break
        assignment = best

        for c in range(k):
            members = pixels[assignment == c]
            if len(members):
                centroids[c] = members.mean(axis=0)

    populations = np.array([int((assignment == c).sum()) for c in range(k)])
    order = np.argsort(-populations, kind="stable")
    return centroids[order], populations[order]


def quantise(path: Path) -> list[str]:
    """Palette of a wallpaper, largest cluster first.

    A flat image yields one colour rather than six copies of it: the palette feeds
    the plate gradient and the accent pick, and six identical entries are a claim
    the image does not support.
    """
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((PROFILE, PROFILE), Image.LANCZOS)
        pixels = np.asarray(image, dtype=float).reshape(-1, 3)

    if len(pixels) == 0:
        return []

    centroids, _ = kmeans(pixels, K)
    palette: list[str] = []
    for centroid in centroids:
        colour = to_hex(centroid)
        if colour not in palette:
            palette.append(colour)
    return palette


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root", type=Path, help="`<pkg>/share/wallpapers/assets/contents/images`"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.root.is_dir():
        print(f"[walls-meta] {args.root} is not a directory", file=sys.stderr)
        return 1

    sources = sorted(
        path
        for path in args.root.iterdir()
        if path.is_file() and path.suffix.lower() in (".jpg", ".jpeg", ".png")
    )

    print(f"[walls-meta] {len(sources)} wallpapers")

    out: dict[str, dict] = {}
    for done, path in enumerate(sources, start=1):
        with Image.open(path) as image:
            width, height = image.size

        palette = quantise(path)
        if not palette:
            print(f"[walls-meta] {path.name}: no pixels", file=sys.stderr)
            continue

        most_characterful = max(palette, key=accent_score_of)

        out[path.name] = {
            "file": path.name,
            "width": width,
            "height": height,
            "bytes": path.stat().st_size,
            "palette": palette,
            "accent": clamp_accent(most_characterful, INK),
            "accentPaper": clamp_accent(most_characterful, PAPER),
            "tags": tags_for(path.name),
        }

        if done % 25 == 0 or done == len(sources):
            print(f"[walls-meta] {done}/{len(sources)}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"[walls-meta] wrote {args.out} ({len(out)} entries)")
    return 0


def accent_score_of(hex_code: str) -> float:
    return accent_score(parse_hex(hex_code))


if __name__ == "__main__":
    raise SystemExit(main())
