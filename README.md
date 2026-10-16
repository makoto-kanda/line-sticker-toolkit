# LINE Sticker Workflow Tools

A set of practical Python scripts designed to streamline the creation of LINE stickers (40-pack format). This toolkit automates grid-based image splitting, debris removal, JSON-driven text layout/rendering, anti-aliased background removal, and official LINE specification compliance checks.

## Workflow Overview

1. **Background Removal (`bg_remover.py`)**: Remove the solid background from your AI-generated grid image first to ensure clean transparency.
2. **Splitting & Text Overlay (`splitter.py`)**: Split the grid into individual sticker assets and optionally overlay translated text using a JSON configuration.
3. **Validation & Packaging (`validator.py`)**: Check that the final sticker directory (`final*`) meets all official LINE submission technical standards (dimensions, format, counts, transparency) and automatically bundle them into a ready-to-upload ZIP file.

---

## Features

- **`bg_remover.py` (Transparent Background Utility)**
  - Interactive flood-fill tool to strip solid backgrounds from sticker sheets.
  - Protects transparent corners and applies Gaussian smoothing for smooth, anti-aliased boundaries.

- **`splitter.py` (Integrated Splitter & Text Overlay)**
  - Automatically splits an 8x5 grid image into individual sticker files.
  - Cleans up edges and removes unwanted debris using morphological operations and connected component analysis.
  - **Flexible Modes:** 
    - **Text Mode:** Select a `config*.json` file to automatically wrap text, apply outline strokes, and render text (top/bottom) matching LINE guidelines.
    - **No Text Mode:** Skip JSON selection to extract raw, trimmed sticker images only.
  - Strictly adheres to LINE sticker dimension guidelines (max 370x320 with margins).

- **`validator.py` (LINE Compliance Checker & Packager)**
  - **Interactive Directory Selector:** Automatically scans and lets you select from available target directories (e.g., `final`, `final_ja`, `final_ko`).
  - **Technical Auditing:** Verifies stamp counts (8, 16, 24, 32, 40), sequential naming (`01.png`〜), exact sizes for `main.png` (240x240 px) and `tab.png` (96x74 px), max dimension limits (<= 370x320, even numbers), and alpha channel transparency.
  - **Auto-Packaging:** If all checks pass successfully, automatically generates a clean upload-ready `.zip` file containing only the required valid assets (excluding any extraneous files).

---

## Requirements

- Python 3.x
- Libraries:
  - `Pillow`
  - `numpy`
  - `opencv-python` (`cv2`)

Install dependencies via pip:
```bash
pip install Pillow numpy opencv-python