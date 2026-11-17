#!/usr/bin/env python3
"""
Extract TFT Set 19 champion portraits, trait icons, and JS data from units.html.

Usage:
    python extract.py units.html

Optional:
    python extract.py units.html --output-dir ./tft19-assets

Dependencies:
    pip install beautifulsoup4 Pillow
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO


def clean_name(value: str) -> str:
    """Collapse whitespace and remove HTML comment artifacts."""
    return re.sub(r"\s+", " ", value or "").strip()


def make_id(value: str) -> str:
    """Create the lowercase, alphanumeric IDs used by the existing JS files."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def write_png(image_bytes: bytes, destination: Path) -> None:
    """Convert an input image (WebP, PNG, etc.) to PNG."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(image_bytes)) as image:
        image.convert("RGBA").save(destination, format="PNG")


def fetch_image(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; TFT19AssetExtractor/1.0)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def js_file(variable: str, records: list[dict]) -> str:
    """Write the same array/export structure as the supplied units.js/traits.js."""
    return (
        f"const {variable} = "
        + json.dumps(records, ensure_ascii=False, indent=2)
        + f";\n\nexport default {variable};\n"
    )


def extract(html_path: Path, output_dir: Path) -> None:
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    units_dir = output_dir / "units"
    traits_dir = output_dir / "traits"
    units_dir.mkdir(parents=True, exist_ok=True)
    traits_dir.mkdir(parents=True, exist_ok=True)

    units: list[dict] = []
    # Keep the first copy of each trait. A repeated trait icon is only saved once.
    traits: dict[str, dict] = {}
    seen_unit_ids: set[str] = set()
    unit_image_failures: list[tuple[str, str]] = []

    for section in soup.select("section[aria-label]"):
        section_label = clean_name(section.get("aria-label", ""))
        cost_match = re.search(r"(\d+)\s*cost", section_label, flags=re.I)
        if not cost_match:
            continue
        cost = int(cost_match.group(1))

        for button in section.select("button"):
            heading = button.select_one("h3")
            if heading is None:
                continue

            champion_name = clean_name(heading.get_text(" ", strip=True))
            if not champion_name:
                continue

            # The first non-data image in the champion button is the portrait.
            portrait = next(
                (
                    img for img in button.select("img[src]")
                    if img.get("src", "").startswith(("http://", "https://"))
                ),
                None,
            )
            if portrait is None:
                print(f"[WARN] No portrait URL found for {champion_name}", file=sys.stderr)
                continue

            portrait_url = portrait["src"]
            source_filename = Path(urlparse(portrait_url).path).name
            # TFTAcademy asset names are e.g. Elise.HASH.webp; use Elise as the
            # champion_name portion of the requested output filename.
            source_stem = source_filename.split(".", 1)[0]
            file_champion_name = source_stem or champion_name.replace(" ", "")
            unit_filename = f"TFT19_{file_champion_name}.TFT_Set19.png"
            unit_id = make_id(champion_name)

            if unit_id in seen_unit_ids:
                print(f"[WARN] Duplicate champion skipped: {champion_name}", file=sys.stderr)
                continue
            seen_unit_ids.add(unit_id)

            try:
                image_bytes = fetch_image(portrait_url)
                write_png(image_bytes, units_dir / unit_filename)
            except Exception as exc:
                unit_image_failures.append((champion_name, str(exc)))
                print(f"[ERROR] Could not download {champion_name}: {exc}", file=sys.stderr)

            unit_traits: list[str] = []
            for icon in button.select('img[src^="data:image/"]'):
                trait_name = clean_name(icon.get("alt") or icon.get("title") or "")
                if not trait_name:
                    continue

                trait_id = make_id(trait_name)
                if not trait_id:
                    continue
                if trait_id not in unit_traits:
                    unit_traits.append(trait_id)

                if trait_id not in traits:
                    data_url = icon.get("src", "")
                    match = re.match(
                        r"^data:image/[^;,]+;base64,(.+)$", data_url, flags=re.S
                    )
                    if not match:
                        print(f"[WARN] Invalid embedded image for trait {trait_name}", file=sys.stderr)
                        continue
                    try:
                        raw_image = base64.b64decode(match.group(1), validate=True)
                        trait_filename = f"{trait_id}.png"
                        write_png(raw_image, traits_dir / trait_filename)
                        traits[trait_id] = {
                            "id": trait_id,
                            "name": trait_name,
                            # The HTML provides the icon and name, but not trait
                            # breakpoints or tier metadata.
                            "breakpoints": [],
                            "tiers": [],
                            "image": f"/images/traits/{trait_filename}",
                        }
                    except Exception as exc:
                        print(f"[ERROR] Could not save trait {trait_name}: {exc}", file=sys.stderr)

            units.append({
                "id": unit_id,
                "name": champion_name,
                "cost": cost,
                "traits": unit_traits,
            })

    # Stable, readable ordering makes diffs easier to review.
    units.sort(key=lambda unit: (unit["cost"], unit["name"].casefold()))
    sorted_traits = sorted(traits.values(), key=lambda trait: trait["name"].casefold())

    (output_dir / "units.js").write_text(
        js_file("units", units), encoding="utf-8"
    )
    (output_dir / "traits.js").write_text(
        js_file("traits", sorted_traits), encoding="utf-8"
    )

    print(f"Champions parsed: {len(units)}")
    print(f"Unique traits parsed: {len(sorted_traits)}")
    print(f"Champion portraits saved: {len(list(units_dir.glob('*.png')))}")
    print(f"Trait icons saved: {len(list(traits_dir.glob('*.png')))}")
    print(f"JS files written: {output_dir / 'units.js'} and {output_dir / 'traits.js'}")
    if unit_image_failures:
        print(f"\nPortrait download failures: {len(unit_image_failures)}")
        for name, error in unit_image_failures:
            print(f"  - {name}: {error}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract TFT Set 19 units and traits from HTML.")
    parser.add_argument("html_file", type=Path, help="Path to the saved HTML file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Output root (default: current directory)",
    )
    args = parser.parse_args()

    if not args.html_file.is_file():
        parser.error(f"HTML file not found: {args.html_file}")
    extract(args.html_file, args.output_dir)


if __name__ == "__main__":
    main()
