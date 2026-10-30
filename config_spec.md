# `config.json` Specification

## 1. Overview

`config.json` controls text rendering for individual stickers and provides global defaults for the Text Mode of `splitter.py`.

The configuration supports:

- Global typography and layout settings.
- Per-sticker text and style overrides.
- Automatic font sizing based on phrase length and available image width.
- Inline rich-text markup.
- Per-sticker overrides for automatic sizing and layout behavior.

All settings are optional unless explicitly stated otherwise. Per-sticker settings override the corresponding global settings.

## 2. Configuration Structure

```json
{
  "version": 1,

  "font_path": "fonts/KosugiMaru-Regular.ttf",
  "bold_font_path": null,

  "text_color": "#34495E",
  "font_weight": 700,
  "outline_color": "#FFFFFF",
  "outline_width": 4,

  "text_position": "bottom",
  "text_alignment": "center",

  "text_width_ratio": 1.0,
  "max_text_height_ratio": 0.30,
  "max_lines": 2,
  "auto_shrink": true,
  "overlap_ratio": 0.0,

  "small_scale": 0.8,
  "big_scale": 1.2,
  "sub_scale": 0.7,
  "sup_scale": 0.7,

  "stickers": [
    {
      "number": 1,
      "text": "Example phrase"
    },
    {
      "number": 2,
      "text": "Another phrase",
      "text_color": "#FF0000",
      "font_size": 36
    }
  ]
}
```

## 3. Global Settings

### Grid Configuration

| Key | Default | Description |
|---|---:|---|
| `grid_cols` | `5` | Number of columns in the source sticker sheet. |
| `grid_rows` | `5` | Number of rows in the source sticker sheet. |

Both values must be positive integers. If omitted, the script uses its built-in defaults.

The expected number of stickers is calculated as `grid_cols Å~ grid_rows`.

### Font

| Key | Description |
|---|---|
| `font_path` | Path to the regular font file. |
| `bold_font_path` | Optional path to a dedicated bold font file. If omitted, the renderer may use synthetic bold styling. |
| `font_weight` | Font weight. A value of `700` represents bold styling. |

### Text Appearance

| Key | Description |
|---|---|
| `text_color` | Default text color in hexadecimal format. |
| `outline_color` | Text outline color in hexadecimal format. |
| `outline_width` | Width of the text outline. |

`text_color` is the canonical color setting. The legacy per-sticker key `color` may be accepted for backward compatibility, but should not be used in new configurations.

### Text Position and Alignment

| Key | Description |
|---|---|
| `text_position` | Vertical placement of the text. Supported positions include `top` and `bottom`. |
| `text_alignment` | Horizontal alignment, such as `left`, `center`, or `right`. |

### Automatic Font Sizing and Layout

| Key | Default | Description |
|---|---:|---|
| `text_width_ratio` | `1.0` | Maximum proportion of the available image width that the text may occupy. |
| `max_text_height_ratio` | `0.30` | Maximum text block height relative to the reference image height. |
| `max_lines` | `2` | Maximum permitted number of text lines. |
| `auto_shrink` | `true` | Automatically reduce font size when the text does not fit. |
| `overlap_ratio` | `0.0` | Controls the permitted overlap between the text area and the character/image area. |

### Font Size Behavior

Font size is determined automatically by default.

The renderer measures the actual rendered text width and adjusts the font size to fit the available area. The calculation takes phrase length, available image width, and the applicable layout constraints into account.

`AUTO_FONT_MAX_SIZE` acts as an upper limit for automatically calculated font sizes.

An explicit `font_size` setting can be used when a fixed size is desired. It may also be specified for an individual sticker.

## 4. Per-Sticker Settings

Each entry in the `stickers` array represents one sticker.

### Required Fields

| Key | Description |
|---|---|
| `number` | Sticker number. |
| `text` | Text to render on the sticker. |

### Optional Overrides

A sticker may override applicable global settings, including:

- `font_size`
- `font_path`
- `bold_font_path`
- `text_color`
- `font_weight`
- `outline_color`
- `outline_width`
- `text_position`
- `text_alignment`
- `text_width_ratio`
- `max_text_height_ratio`
- `max_lines`
- `auto_shrink`
- `overlap_ratio`
- `small_scale`
- `big_scale`
- `sub_scale`
- `sup_scale`

Only the settings that need to differ from the global defaults need to be specified.

For example:

```json
{
  "number": 3,
  "text": "A very long phrase",
  "text_width_ratio": 0.9,
  "max_lines": 3,
  "auto_shrink": true
}
```

A sticker without an explicit `font_size` uses automatic font sizing.

## 5. Inline Rich-Text Markup

Text strings support inline HTML-like markup to apply different styles or sizes to individual portions of a phrase.

The following tags are supported:

| Tag | Effect |
|---|---|
| `<small>...</small>` | Smaller text. Default scale: `0.8Å~`. |
| `<big>...</big>` | Larger text. Default scale: `1.2Å~`. |
| `<b>...</b>` | Bold text. |
| `<s>...</s>` | Strikethrough. |
| `<u>...</u>` | Underlined text. |
| `<sub>...</sub>` | Subscript text. Default scale: `0.7Å~`. |
| `<sup>...</sup>` | Superscript text. Default scale: `0.7Å~`. |

### Examples

```json
{
  "number": 4,
  "text": "This is <small>small</small> text"
}
```

```json
{
  "number": 5,
  "text": "This is <big>BIG</big> text"
}
```

```json
{
  "number": 6,
  "text": "This is <b>bold</b> and <u>underlined</u>"
}
```

```json
{
  "number": 7,
  "text": "H<sub>2</sub>O"
}
```

```json
{
  "number": 8,
  "text": "E = mc<sup>2</sup>"
}
```

Tags can be nested:

```json
{
  "number": 9,
  "text": "<big>IMPORTANT <b>NOTICE</b></big>"
}
```

### Markup Scale Overrides

The default scale factors can be changed globally or for individual stickers.

| Key | Default |
|---|---:|
| `small_scale` | `0.8` |
| `big_scale` | `1.2` |
| `sub_scale` | `0.7` |
| `sup_scale` | `0.7` |

For example:

```json
{
  "number": 10,
  "text": "<small>Fine print</small> Main text",
  "small_scale": 0.65
}
```

### Markup Rules

- Ordinary text outside tags retains the normal text style.
- Explicit newline characters are preserved.
- Text measurement accounts for the different sizes of inline segments.
- Baselines are aligned using font metrics so that mixed-size text is rendered consistently.
- Unsupported tags, invalid attributes, mismatched closing tags, and unclosed tags are treated as configuration/text errors.

## 6. Text Normalization

Text is normalized using Unicode NFC normalization before rendering.

This helps ensure consistent handling of visually equivalent Unicode characters.

Explicit line breaks in the text are preserved.

## 7. Output Size and Margins

The output canvas is tightly fitted to the actual rendered content.

- `MAX_W` and `MAX_H` are independent maximum dimensions, not fixed output dimensions.
- The output should use only the space required by the rendered content.
- `MARGIN` is retained around the content.
- Unnecessary transparent space must not be added merely to fill the maximum canvas dimensions.

The final output dimensions must not exceed the configured maximum width or height.

## 8. Configuration Principles

1. Global settings define the default behavior.
2. Per-sticker settings override global settings only where specified.
3. Automatic font sizing is the default; fixed font sizes are optional.
4. Inline markup is intended for local emphasis and size variation within a phrase.
5. The same layout and sizing rules apply consistently across stickers.
6. Maximum dimensions are constraints, not target dimensions.
