# LINE Sticker Workflow Tools

A set of practical Python scripts designed to streamline the creation of LINE stickers (40-pack format). This toolkit automates grid-based image splitting, debris removal, JSON-driven text layout/rendering, and anti-aliased background removal.

## Workflow Overview

1. **Background Removal (`bg_remover.py`)**: Remove the solid background from your AI-generated grid image first to ensure clean transparency.
2. **Splitting & Text Overlay (`splitter.py`)**: Split the grid into individual sticker assets and optionally overlay translated text using a JSON configuration.

---

## Features

- **`splitter.py` (Integrated Splitter & Text Overlay)**
  - Automatically splits an 8x5 grid image into individual sticker files.
  - Cleans up edges and removes unwanted debris using morphological operations and connected component analysis.
  - **Flexible Modes:** 
    - **Text Mode:** Select a `config*.json` file to automatically wrap text, apply outline strokes, and render text (top/bottom) matching LINE guidelines.
    - **No Text Mode:** Skip JSON selection to extract raw, trimmed sticker images only.
  - Strictly adheres to LINE sticker dimension guidelines (max 370x320 with margins).

- **`bg_remover.py` (Transparent Background Utility)**
  - Interactive flood-fill tool to strip solid backgrounds from sticker sheets.
  - Protects transparent corners and applies Gaussian smoothing for smooth, anti-aliased boundaries.

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