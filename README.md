# TFT Asset Extractor

A small Python script that extracts champion portraits and trait icons from a saved TFT Set 19 HTML page. It also generates JavaScript data files for the units and traits.

## Requirements

- Python 3.10+
- `beautifulsoup4`
- `Pillow`

Install dependencies:

```bash
pip install beautifulsoup4 Pillow
```

## Usage

Place the saved HTML file (for example, `units.html`) beside the script, then run:

```bash
python extract.py units.html
```

To choose a different output directory:

```bash
python extract.py units.html --output-dir ./output
```

Champion portraits are downloaded from their source URLs, so an internet connection is required. Trait icons are decoded from the Base64 image data embedded in the HTML.

## Output

The output directory contains:

```text
output/
├── units/
│   └── TFT19_{ChampionName}.TFT_Set19.png
├── traits/
│   └── {traitname}.png
├── units.js
└── traits.js
```

- `units/`: champion portraits converted to PNG.
- `traits/`: unique trait icons converted to PNG. Trait filenames are lowercase with spaces and punctuation removed.
- `units.js`: champion names, costs, IDs, and associated trait IDs.
- `traits.js`: unique trait names, IDs, image paths, and empty `breakpoints` / `tiers` arrays.

## Notes

- Duplicate champions and trait icons are skipped.
- The script reports missing portraits and image-processing/download errors in the terminal.
