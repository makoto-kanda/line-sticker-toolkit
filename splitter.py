from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2
import os
import glob
import json
import warnings
from html.parser import HTMLParser

# ==========================================
# Adjustment Parameters (Common)
# ==========================================
GRID_COLS = 5
GRID_ROWS = 5

CUT_TOP = 0
CUT_BOTTOM = 0
CUT_LEFT = 0
CUT_RIGHT = 0

PAD_TOP_RATIO = 0.10
PAD_BOTTOM_RATIO = 0.10
PAD_LEFT_RATIO = 0.10
PAD_RIGHT_RATIO = 0.10

MORPH_KERNEL_SIZE = (7, 7)

DEBRIS_MAX_AREA = 250000
EDGE_THRESHOLD = 5
# ==========================================

MAX_W, MAX_H = 370, 320
MARGIN = 10

# Font auto-fit settings
AUTO_FONT_MIN_SIZE = 1
AUTO_FONT_MAX_SIZE = 36


# ==========================================
# Select Input Image (*.png)
# ==========================================
input_files = sorted(glob.glob("*.png"))

if not input_files:
    raise FileNotFoundError(
        "No files matching '*.png' were found in the current directory."
    )

print("=== LINE Sticker Integrated Splitter ===")
print("Select an image file to process:")

for i, filename in enumerate(input_files):
    print(f"  [{i + 1}] {filename}")

choice = input("Enter number (1-{}): ".format(len(input_files))).strip()

try:
    choice_idx = int(choice) - 1
    if choice_idx < 0 or choice_idx >= len(input_files):
        raise ValueError()
except ValueError:
    raise ValueError("Invalid selection. Please enter a correct number.")

input_path = input_files[choice_idx]
start_num = 1


# ==========================================
# Detect and Select Configuration File
# ==========================================
json_files = sorted(glob.glob("config*.json"))
config = None
config_suffix = "notext"

print("\n--- Mode / Configuration Selection ---")
print("  [0] No Text (Extract images only)")

for i, jfile in enumerate(json_files):
    print(f"  [{i + 1}] {jfile} (Apply text overlay)")

json_choice = input(
    f"Select number (0-{len(json_files)}): "
).strip()

# Only selection-input errors are handled here. JSON parsing errors must
# never be mistaken for a request to run No Text Mode.
try:
    j_idx = int(json_choice)
except ValueError:
    raise ValueError(
        f"Invalid configuration selection: {json_choice!r}. "
        f"Enter a number from 0 to {len(json_files)}."
    )

if j_idx == 0:
    print("-> [No Text Mode] Extracting images without text")
    config = None
    config_suffix = "notext"

elif 1 <= j_idx <= len(json_files):
    config_path = json_files[j_idx - 1]

    # Do not catch JSONDecodeError here: it is a ValueError subclass.
    # Let the actual file/line/column error reach the user.
    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in '{config_path}' at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(config, dict):
        raise ValueError(
            f"Configuration '{config_path}' must contain a JSON object."
        )

    print(f"-> [Text Mode] Configuration file: {config_path}")

    base_name = os.path.basename(config_path)
    stem, _ = os.path.splitext(base_name)

    if stem.lower().startswith("config"):
        config_suffix = stem[len("config"):].lstrip("_")
    else:
        config_suffix = stem

    if not config_suffix:
        config_suffix = "text"

else:
    raise ValueError(
        f"Invalid configuration selection: {j_idx}. "
        f"Enter a number from 0 to {len(json_files)}."
    )

OUT_DIR = f"output_{config_suffix}" if config_suffix else "output_notext"
os.makedirs(OUT_DIR, exist_ok=True)


# ==========================================
# Validate Configuration
# ==========================================
if config is not None:

    # ------------------------------------------------------
    # Common processing parameters (JSON overrides)
    # ------------------------------------------------------
    GRID_COLS = int(config.get("grid_cols", GRID_COLS))
    GRID_ROWS = int(config.get("grid_rows", GRID_ROWS))

    CUT_TOP = int(config.get("cut_top", CUT_TOP))
    CUT_BOTTOM = int(config.get("cut_bottom", CUT_BOTTOM))
    CUT_LEFT = int(config.get("cut_left", CUT_LEFT))
    CUT_RIGHT = int(config.get("cut_right", CUT_RIGHT))

    PAD_TOP_RATIO = float(config.get("pad_top_ratio", PAD_TOP_RATIO))
    PAD_BOTTOM_RATIO = float(config.get("pad_bottom_ratio", PAD_BOTTOM_RATIO))
    PAD_LEFT_RATIO = float(config.get("pad_left_ratio", PAD_LEFT_RATIO))
    PAD_RIGHT_RATIO = float(config.get("pad_right_ratio", PAD_RIGHT_RATIO))

    kernel_value = config.get("morph_kernel_size", MORPH_KERNEL_SIZE)
    if not isinstance(kernel_value, (list, tuple)) or len(kernel_value) != 2:
        raise ValueError(
            '"morph_kernel_size" must be a two-item array, e.g. [7, 7].'
        )
    MORPH_KERNEL_SIZE = tuple(int(v) for v in kernel_value)

    DEBRIS_MAX_AREA = int(config.get("debris_max_area", DEBRIS_MAX_AREA))
    EDGE_THRESHOLD = int(config.get("edge_threshold", EDGE_THRESHOLD))

    MAX_W = int(config.get("max_w", MAX_W))
    MAX_H = int(config.get("max_h", MAX_H))
    MARGIN = int(config.get("margin", MARGIN))

    AUTO_FONT_MIN_SIZE = int(
        config.get("auto_font_min_size", AUTO_FONT_MIN_SIZE)
    )
    AUTO_FONT_MAX_SIZE = int(
        config.get("auto_font_max_size", AUTO_FONT_MAX_SIZE)
    )

    # ------------------------------------------------------
    # Validate common parameters
    # ------------------------------------------------------
    if GRID_COLS < 1 or GRID_ROWS < 1:
        raise ValueError(
            '"grid_cols" and "grid_rows" must be positive integers.'
        )

    if min(CUT_TOP, CUT_BOTTOM, CUT_LEFT, CUT_RIGHT) < 0:
        raise ValueError("CUT values must be zero or positive.")

    if min(
        PAD_TOP_RATIO,
        PAD_BOTTOM_RATIO,
        PAD_LEFT_RATIO,
        PAD_RIGHT_RATIO
    ) < 0:
        raise ValueError("PAD ratios must be zero or positive.")

    if (
        min(MORPH_KERNEL_SIZE) < 1
        or any(v % 2 == 0 for v in MORPH_KERNEL_SIZE)
    ):
        raise ValueError(
            '"morph_kernel_size" values must be positive odd integers.'
        )

    if DEBRIS_MAX_AREA < 0 or EDGE_THRESHOLD < 0:
        raise ValueError(
            '"debris_max_area" and "edge_threshold" must be zero or positive.'
        )

    if MAX_W < 2 or MAX_H < 2:
        raise ValueError('"max_w" and "max_h" must be at least 2.')

    if MARGIN < 0 or (2 * MARGIN >= MAX_W) or (2 * MARGIN >= MAX_H):
        raise ValueError('"margin" is too large for max_w/max_h.')

    # ------------------------------------------------------
    # Required configuration keys
    # ------------------------------------------------------
    required_keys = ["font_path", "stickers"]
    missing_keys = [
        key for key in required_keys if key not in config
    ]

    if missing_keys:
        raise ValueError(
            f"Missing required keys in configuration file: {missing_keys}"
        )

    font_path = config["font_path"]

    if not os.path.isabs(font_path):
        font_path = os.path.join(os.getcwd(), font_path)

    if not os.path.isfile(font_path):
        raise FileNotFoundError(f"Font file not found: {font_path}")

    # ------------------------------------------------------
    # Text defaults
    # ------------------------------------------------------
    font_size_default = int(config.get("font_size", 48))
    text_color_default = config.get("text_color", "#000000")
    outline_color_default = config.get("outline_color", "#FFFFFF")
    outline_width_default = int(config.get("outline_width", 12))
    text_position_default = config.get("text_position", "bottom")
    text_alignment_default = config.get("text_alignment", "center")
    max_lines_default = int(config.get("max_lines", 2))
    text_width_ratio_default = float(config.get("text_width_ratio", 4.0))
    max_text_height_ratio_default = float(
        config.get("max_text_height_ratio", 1.0)
    )
    auto_shrink_default = bool(config.get("auto_shrink", True))

    auto_font_min_size = AUTO_FONT_MIN_SIZE
    auto_font_max_size = AUTO_FONT_MAX_SIZE

    # Inline rich-text defaults. Per-sticker values override these.
    inline_scale_defaults = {
        "small_scale": float(config.get("small_scale", 0.8)),
        "big_scale": float(config.get("big_scale", 1.2)),
        "sub_scale": float(config.get("sub_scale", 0.7)),
        "sup_scale": float(config.get("sup_scale", 0.7)),
    }

    for key, value in inline_scale_defaults.items():
        if value <= 0:
            raise ValueError(f'"{key}" must be greater than 0.')

    if text_width_ratio_default <= 0:
        raise ValueError('"text_width_ratio" must be greater than 0.')

    if max_text_height_ratio_default <= 0:
        raise ValueError('"max_text_height_ratio" must be greater than 0.')

    if auto_font_min_size < 1 or auto_font_max_size < auto_font_min_size:
        raise ValueError('Invalid auto font size range.')

    # ------------------------------------------------------
    # overlap_ratio supports both the legacy numeric format
    # and the line-count-specific dictionary format.
    # ------------------------------------------------------
    DEFAULT_OVERLAP_RATIOS = {
        1: 0.50,
        2: 0.65,
        3: 0.70
    }

    overlap_ratio_config = config.get(
        "overlap_ratio",
        DEFAULT_OVERLAP_RATIOS
    )

    if isinstance(overlap_ratio_config, (int, float)):
        # Legacy format: one ratio for every line count.
        overlap_ratio_default = float(overlap_ratio_config)

    elif isinstance(overlap_ratio_config, dict):
        # New format: override defaults for specific line counts.
        overlap_ratio_default = DEFAULT_OVERLAP_RATIOS.copy()

        for key, value in overlap_ratio_config.items():
            try:
                line_count = int(key)
                ratio = float(value)
            except (TypeError, ValueError):
                raise ValueError(
                    "Invalid overlap_ratio entry. Expected positive "
                    "line-count keys and numeric values."
                )

            if line_count < 1:
                raise ValueError(
                    "overlap_ratio line-count keys must be positive integers."
                )

            overlap_ratio_default[line_count] = ratio

    else:
        raise ValueError(
            '"overlap_ratio" must be a number or an object keyed by line count.'
        )

    # Compatibility warnings for deprecated configuration keys.
    if "text_gap" in config:
        print(
            'WARNING: "text_gap" is deprecated and will be ignored.'
        )

    stickers_config = {}

    for item in config["stickers"]:
        number = int(item["number"])

        if "color" in item:
            print(
                f'WARNING: Sticker {number}: "color" is deprecated. '
                'Use "text_color" instead.'
            )

        if "text_gap" in item:
            print(
                f'WARNING: Sticker {number}: "text_gap" is deprecated and will be ignored.'
            )

        stickers_config[number] = item

    expected_total = GRID_COLS * GRID_ROWS
    expected_numbers = set(range(1, expected_total + 1))
    actual_numbers = set(stickers_config.keys())

    if actual_numbers != expected_numbers:
        missing = sorted(expected_numbers - actual_numbers)
        extra = sorted(actual_numbers - expected_numbers)

        raise ValueError(
            f"Sticker numbers do not match the grid. "
            f"Missing: {missing} / Extra: {extra}"
        )


# ==========================================
# Font Loading & Text Rendering Helpers
# ==========================================
font_cache = {}
warned_static_font = False


def load_font(size, weight=None):
    global warned_static_font

    size = max(1, int(size))
    cache_key = (size, weight)

    if cache_key in font_cache:
        return font_cache[cache_key]

    font = ImageFont.truetype(font_path, size=size)

    if weight is not None:
        try:
            axes = font.get_variation_axes()
            weight_axis_index = None

            for i, axis in enumerate(axes):
                axis_name = axis.get("name", "")

                if isinstance(axis_name, bytes):
                    axis_name = axis_name.decode(
                        "utf-8", errors="ignore"
                    )

                if str(axis_name).lower() in (
                    "weight", "wght", "font weight"
                ):
                    weight_axis_index = i
                    break

            if weight_axis_index is not None:
                axis = axes[weight_axis_index]

                target = max(
                    float(axis["minimum"]),
                    min(float(axis["maximum"]), float(weight))
                )

                values = [
                    float(a.get("default", a.get("minimum", 0)))
                    for a in axes
                ]

                values[weight_axis_index] = target
                font.set_variation_by_axes(values)

        except Exception:
            if not warned_static_font:
                warnings.warn(
                    "Unable to apply Variable Font weight axis. "
                    "Continuing with standard weight.",
                    RuntimeWarning
                )
                warned_static_font = True

    font_cache[cache_key] = font
    return font


def measure_text_pure(draw, text, font, stroke_width=0):
    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
        stroke_width=stroke_width
    )

    return bbox[2] - bbox[0], bbox[3] - bbox[1]


class InlineMarkupParser(HTMLParser):
    """Parse a small, deliberately strict subset of HTML-like text markup."""

    ALLOWED_TAGS = {"small", "big", "b", "s", "u", "sub", "sup"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = [{
            "tag": None,
            "scale": 1.0,
            "bold": False,
            "strike": False,
            "underline": False,
            "italic": False,
            "shift": 0
        }]
        self.runs = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.ALLOWED_TAGS:
            raise ValueError(f"Unsupported inline tag <{tag}>.")

        if attrs:
            raise ValueError(f"Attributes are not supported in <{tag}>.")

        parent = self.stack[-1].copy()
        parent["tag"] = tag

        if tag == "small":
            parent["scale_tag"] = "small"
        elif tag == "big":
            parent["scale_tag"] = "big"
        elif tag == "sub":
            parent["scale_tag"] = "sub"
            parent["shift"] = 1
        elif tag == "sup":
            parent["scale_tag"] = "sup"
            parent["shift"] = -1
        elif tag == "b":
            parent["bold"] = True
        elif tag == "s":
            parent["strike"] = True
        elif tag == "u":
            parent["underline"] = True

        self.stack.append(parent)

    def handle_endtag(self, tag):
        if len(self.stack) == 1 or self.stack[-1]["tag"] != tag:
            raise ValueError(
                f"Unexpected or mismatched closing tag </{tag}>."
            )

        self.stack.pop()

    def handle_data(self, data):
        if not data:
            return

        style = self.stack[-1].copy()
        style.pop("tag", None)

        if self.runs and self.runs[-1]["style"] == style:
            self.runs[-1]["text"] += data
        else:
            self.runs.append({"text": data, "style": style})

    def close(self):
        super().close()

        if len(self.stack) != 1:
            tag = self.stack[-1]["tag"]
            raise ValueError(f"Unclosed inline tag <{tag}>.")


def parse_inline_text(text, scales, sticker_number):
    parser = InlineMarkupParser()

    try:
        parser.feed(text)
        parser.close()
    except ValueError as exc:
        raise ValueError(f"Sticker {sticker_number}: {exc}") from exc

    # Split runs on explicit newlines while retaining each run's formatting.
    lines = [[]]

    for run in parser.runs:
        pieces = run["text"].split("\n")

        for index, piece in enumerate(pieces):
            if piece:
                style = run["style"].copy()
                scale_tag = style.pop("scale_tag", None)

                if scale_tag in scales:
                    style["scale"] = scales[scale_tag]
                else:
                    style["scale"] = 1.0

                lines[-1].append({
                    "text": piece,
                    "style": style
                })

            if index < len(pieces) - 1:
                lines.append([])

    return lines


def run_font_size(base_size, run):
    return max(
        1,
        int(round(base_size * run["style"].get("scale", 1.0)))
    )


def measure_rich_lines(draw, lines, base_size, weight, outline_width):
    """Measure mixed-size runs using their actual glyph bounds and shared baseline."""
    measured = []

    for line in lines:
        run_data = []

        if not line:
            blank_font = load_font(base_size, weight)
            blank_ascent, blank_descent = blank_font.getmetrics()

            measured.append({
                "runs": [],
                "width": 0,
                "height": max(
                    1,
                    blank_ascent + blank_descent + 2 * outline_width
                ),
                "ascent": blank_ascent + outline_width,
                "descent": blank_descent + outline_width
            })
            continue

        # Measure the actual glyph bounds relative to the shared baseline.
        # This includes the outline and also accounts for sub/superscript shifts.
        min_top = 0
        max_bottom = 0

        for run in line:
            font = load_font(run_font_size(base_size, run), weight)
            shift = run["style"].get("shift", 0)

            # Sub/sup offsets are proportional to the run's own font size.
            baseline_shift = int(round(font.size * 0.22 * shift))

            bbox = draw.textbbox(
                (0, 0),
                run["text"],
                font=font,
                anchor="ls",
                stroke_width=outline_width
            )

            run_top = bbox[1] + baseline_shift
            run_bottom = bbox[3] + baseline_shift

            min_top = min(min_top, run_top)
            max_bottom = max(max_bottom, run_bottom)

            width = float(draw.textlength(run["text"], font=font))
            width += 2 * outline_width

            run_data.append((run, font, width, baseline_shift))

        line_ascent = -min_top
        line_descent = max_bottom

        measured.append({
            "runs": run_data,
            "width": sum(entry[2] for entry in run_data),
            "height": max(1, line_ascent + line_descent),
            "ascent": line_ascent,
            "descent": line_descent
        })

    widest = max(
        (line["width"] for line in measured),
        default=0
    )
    total_height = sum(line["height"] for line in measured)

    return measured, widest, total_height

def wrap_rich_lines(draw, lines, base_size, weight, outline_width,
                    max_allowed_width):
    """
    Automatically wrap rich-text lines to fit the allowed width.

    Japanese text is wrapped character by character.
    Whitespace is preferred as a break point for languages such as English.
    Inline formatting is preserved.
    """
    wrapped_lines = []

    def append_atom(target, atom):
        if target and target[-1]["style"] == atom["style"]:
            target[-1]["text"] += atom["text"]
        else:
            target.append({
                "text": atom["text"],
                "style": atom["style"].copy()
            })

    def atom_width(atom):
        font = load_font(
            run_font_size(base_size, atom),
            weight
        )
        return (
            float(draw.textlength(atom["text"], font=font))
            + 2 * outline_width
        )

    for original_line in lines:
        # Preserve explicitly empty lines.
        if not original_line:
            wrapped_lines.append([])
            continue

        atoms = []

        for run in original_line:
            for char in run["text"]:
                atoms.append({
                    "text": char,
                    "style": run["style"].copy()
                })

        current = []

        for atom in atoms:
            candidate = current + [atom]

            candidate_runs = []
            for entry in candidate:
                append_atom(candidate_runs, entry)

            _, candidate_width, _ = measure_rich_lines(
                draw,
                [candidate_runs],
                base_size,
                weight,
                outline_width
            )

            if candidate_width <= max_allowed_width or not current:
                current.append(atom)
                continue

            # Prefer breaking at the last whitespace in the current line.
            whitespace_index = None

            for i in range(len(current) - 1, -1, -1):
                if current[i]["text"].isspace():
                    whitespace_index = i
                    break

            if whitespace_index is not None:
                left = current[:whitespace_index]
                right = current[whitespace_index + 1:]

                if left:
                    line_runs = []
                    for entry in left:
                        append_atom(line_runs, entry)
                    wrapped_lines.append(line_runs)

                current = right
                current.append(atom)

            else:
                # No suitable whitespace: break before the new character.
                line_runs = []
                for entry in current:
                    append_atom(line_runs, entry)

                wrapped_lines.append(line_runs)
                current = [atom]

        if current:
            # Remove trailing whitespace at the end of the visual line.
            while current and current[-1]["text"].isspace():
                current.pop()

            if current:
                line_runs = []
                for entry in current:
                    append_atom(line_runs, entry)
                wrapped_lines.append(line_runs)
            else:
                wrapped_lines.append([])

    return wrapped_lines

def prepare_text_auto_fit(item, draw, max_allowed_width, max_allowed_height):
    """
    Fit rich text into the allowed area.

    Priority:
    1. Preserve explicit newlines and shrink the font if necessary.
    2. Without explicit newlines, try a single line first.
    3. If a single line cannot fit, automatically wrap the text.
    4. Respect max_lines and the available width/height.
    """
    raw_text = str(item.get("text", "")).strip()

    if not raw_text:
        return None, []

    sticker_number = item.get("number", "?")

    color = item.get("text_color", item.get("color", text_color_default))
    outline_color = item.get("outline_color", outline_color_default)
    outline_width = max(
        0,
        int(item.get("outline_width", outline_width_default))
    )
    weight = item.get("font_weight", config.get("font_weight"))
    max_lines = max(1, int(item.get("max_lines", max_lines_default)))
    position = item.get("position", text_position_default)
    alignment = item.get("alignment", text_alignment_default)

    scales = inline_scale_defaults.copy()

    for key in scales:
        if key in item:
            scales[key] = float(item[key])

            if scales[key] <= 0:
                raise ValueError(
                    f"Sticker {sticker_number}: "
                    f"{key} must be greater than 0."
                )

    tag_scales = {
        "small": scales["small_scale"],
        "big": scales["big_scale"],
        "sub": scales["sub_scale"],
        "sup": scales["sup_scale"],
    }

    lines = parse_inline_text(
        raw_text,
        tag_scales,
        sticker_number
    )

    has_explicit_newline = "\n" in raw_text

    if len(lines) > max_lines:
        raise ValueError(
            f"Sticker {sticker_number}: text has "
            f"{len(lines)} explicit lines, "
            f"but max_lines is {max_lines}."
        )

    width_ratio = float(
        item.get("text_width_ratio", text_width_ratio_default)
    )
    height_ratio = float(
        item.get("max_text_height_ratio", max_text_height_ratio_default)
    )

    if width_ratio <= 0 or height_ratio <= 0:
        raise ValueError(
            f"Sticker {sticker_number}: "
            "text size ratios must be greater than 0."
        )

    fixed_size = "font_size" in item
    auto_shrink = bool(item.get("auto_shrink", auto_shrink_default))

    if fixed_size:
        sizes = [max(1, int(item["font_size"]))]
    elif auto_shrink:
        sizes = range(
            auto_font_max_size,
            auto_font_min_size - 1,
            -1
        )
    else:
        sizes = [font_size_default]

    chosen = None
    last_measure = None
    last_line_count = len(lines)

    # ------------------------------------------------------
    # Phase 1:
    # Try the original line structure first.
    # This means explicit newlines are preserved, and text
    # without newlines is kept on one line whenever possible.
    # ------------------------------------------------------
    for size in sizes:
        measured, widest, total_height = measure_rich_lines(
            draw,
            lines,
            size,
            weight,
            outline_width
        )

        last_measure = (widest, total_height, size)
        last_line_count = len(lines)

        if (
            widest <= max_allowed_width
            and total_height <= max_allowed_height
        ):
            chosen = (size, measured, lines)
            break

    # ------------------------------------------------------
    # Phase 2:
    # If there were no explicit newlines and the original
    # line could not fit, try automatic wrapping.
    # ------------------------------------------------------
    if chosen is None and not has_explicit_newline:
        for size in sizes:
            wrapped_lines = wrap_rich_lines(
                draw,
                lines,
                size,
                weight,
                outline_width,
                max_allowed_width
            )

            if len(wrapped_lines) > max_lines:
                last_line_count = len(wrapped_lines)
                continue

            measured, widest, total_height = measure_rich_lines(
                draw,
                wrapped_lines,
                size,
                weight,
                outline_width
            )

            last_measure = (widest, total_height, size)
            last_line_count = len(wrapped_lines)

            if (
                widest <= max_allowed_width
                and total_height <= max_allowed_height
            ):
                chosen = (size, measured, wrapped_lines)
                break

    # ------------------------------------------------------
    # Error handling
    # ------------------------------------------------------
    if chosen is None:
        if last_measure is None:
            widest = 0
            total_height = 0
            attempted_size = 0
        else:
            widest, total_height, attempted_size = last_measure

        raise ValueError(
            f"Sticker {sticker_number}: text cannot fit "
            f"within the allowed area. "
            f"At font size ({attempted_size}px), measured text is "
            f"{int(widest)}x{int(total_height)}px; allowed area is "
            f"{int(max_allowed_width)}x{int(max_allowed_height)}px. "
            f"Line count: {last_line_count}; max_lines: {max_lines}. "
            "Try reducing outline width, increasing the allowed text "
            "area, or increasing max_lines."
        )

    chosen_size, chosen_measured, chosen_lines = chosen

    # ------------------------------------------------------
    # Determine overlap ratio using the final visual line count.
    # ------------------------------------------------------
    if "overlap_ratio" in item:
        try:
            overlap_ratio = float(item["overlap_ratio"])
        except (TypeError, ValueError):
            raise ValueError(
                f"Sticker {sticker_number}: "
                "overlap_ratio must be numeric."
            )

    elif isinstance(overlap_ratio_default, dict):
        overlap_ratio = overlap_ratio_default.get(
            len(chosen_lines),
            overlap_ratio_default.get(3, 0.70)
        )

    else:
        overlap_ratio = overlap_ratio_default

    if not 0 <= overlap_ratio < 1:
        raise ValueError(
            f"Sticker {sticker_number}: "
            "overlap_ratio must be >= 0 and < 1."
        )

    return {
        "color": color,
        "outline_color": outline_color,
        "outline_width": outline_width,
        "position": position,
        "alignment": alignment,
        "overlap_ratio": overlap_ratio,
        "font_size": chosen_size,
        "font_weight": weight,
        "measured_lines": chosen_measured,
    }, chosen_lines

def render_text_image(lines, style, render_scale=1.0):
    """Render rich text using each font's metrics and a shared baseline."""
    if not lines:
        return None

    render_scale = max(float(render_scale), 1e-6)
    stroke_width = max(
        0,
        int(round(style["outline_width"] * render_scale))
    )
    rendered_lines = []

    for measured_line in style["measured_lines"]:
        line_width = max(
            1,
            int(round(measured_line["width"] * render_scale))
        )
        line_height = max(
            1,
            int(round(measured_line["height"] * render_scale))
        )
        ascent = int(round(measured_line["ascent"] * render_scale))

        line_img = Image.new(
            "RGBA",
            (line_width + 8, line_height + 8),
            (0, 0, 0, 0)
        )
        draw = ImageDraw.Draw(line_img)

        x = 4
        baseline_y = 4 + ascent

        for run, measured_font, run_width, baseline_shift in measured_line["runs"]:
            size = max(
                1,
                int(round(measured_font.size * render_scale))
            )
            font = load_font(size, style.get("font_weight"))
            shift = int(round(baseline_shift * render_scale))
            run_text = run["text"]
            run_style = run["style"]
            run_stroke = stroke_width

            # Draw the white/selected outline first, then the fill.
            # Bold is simulated by a tiny same-color overdraw.
            draw.text(
                (x, baseline_y + shift),
                run_text,
                font=font,
                fill=style["color"],
                anchor="ls",
                stroke_width=run_stroke,
                stroke_fill=style["outline_color"]
            )

            if run_style.get("bold"):
                draw.text(
                    (
                        x + max(1, int(round(render_scale))),
                        baseline_y + shift
                    ),
                    run_text,
                    font=font,
                    fill=style["color"],
                    anchor="ls"
                )

            if run_style.get("strike") or run_style.get("underline"):
                text_w = int(round(draw.textlength(run_text, font=font)))
                ascent_px, descent_px = font.getmetrics()

                if run_style.get("strike"):
                    line_y = baseline_y + shift - int(ascent_px * 0.35)
                    draw.line(
                        (x, line_y, x + text_w, line_y),
                        fill=style["color"],
                        width=max(1, int(round(render_scale * 2)))
                    )

                if run_style.get("underline"):
                    line_y = (
                        baseline_y
                        + shift
                        + max(1, int(descent_px * 0.25))
                    )
                    draw.line(
                        (x, line_y, x + text_w, line_y),
                        fill=style["color"],
                        width=max(1, int(round(render_scale * 2)))
                    )

            x += int(round(run_width * render_scale))

        bbox = line_img.getbbox()
        rendered_lines.append(
            line_img.crop(bbox) if bbox else line_img
        )

    total_w = max(img.width for img in rendered_lines)
    total_h = sum(img.height for img in rendered_lines)

    text_img = Image.new(
        "RGBA",
        (total_w, total_h),
        (0, 0, 0, 0)
    )

    y = 0

    for img in rendered_lines:
        if style["alignment"] == "left":
            x = 0
        elif style["alignment"] == "right":
            x = total_w - img.width
        else:
            x = (total_w - img.width) // 2

        text_img.alpha_composite(img, (x, y))
        y += img.height

    return text_img


# ==========================================
# Final LINE Canvas
# ==========================================
def make_line_canvas(content):
    """
    Fit content into the LINE maximum canvas while preserving aspect ratio.

    The output has an even width and height. One outer dimension is exactly
    MAX_W or MAX_H (rounded down to even if configured as an odd number).
    MARGIN is reserved inside the canvas on all four sides.
    """
    if content is None:
        raise ValueError("Cannot create output canvas from an empty image.")

    bbox = content.getchannel("A").getbbox()

    if bbox:
        content = content.crop(bbox)

    src_w, src_h = content.size

    if src_w < 1 or src_h < 1:
        raise ValueError("Sticker content has zero width or height.")

    target_max_w = MAX_W - (MAX_W % 2)
    target_max_h = MAX_H - (MAX_H % 2)

    if target_max_w < 2 or target_max_h < 2:
        raise ValueError(
            "MAX_W and MAX_H must allow at least 2-pixel even dimensions."
        )

    # Select the limiting outer dimension, preserving the content aspect ratio.
    if (src_w / src_h) >= (target_max_w / target_max_h):
        canvas_w = target_max_w
        canvas_h = max(
            2,
            int((src_h * canvas_w / src_w) // 2) * 2
        )
    else:
        canvas_h = target_max_h
        canvas_w = max(
            2,
            int((src_w * canvas_h / src_h) // 2) * 2
        )

    # Protect against floating-point rounding exceeding configured bounds.
    canvas_w = min(canvas_w, target_max_w)
    canvas_h = min(canvas_h, target_max_h)

    # For unusually narrow/tall stickers, reduce the effective margin only
    # as much as needed to keep a positive inner area.
    effective_margin = min(
        MARGIN,
        max(0, (canvas_w - 1) // 2),
        max(0, (canvas_h - 1) // 2)
    )

    inner_w = canvas_w - 2 * effective_margin
    inner_h = canvas_h - 2 * effective_margin

    # Upscale or downscale as needed so the content uses the available area.
    scale = min(
        inner_w / src_w,
        inner_h / src_h
    )

    out_w = max(1, int(round(src_w * scale)))
    out_h = max(1, int(round(src_h * scale)))

    if (out_w, out_h) != content.size:
        content = content.resize(
            (out_w, out_h),
            Image.Resampling.LANCZOS
        )

    canvas = Image.new(
        "RGBA",
        (canvas_w, canvas_h),
        (0, 0, 0, 0)
    )

    x = max(effective_margin, (canvas_w - out_w) // 2)
    y = max(effective_margin, (canvas_h - out_h) // 2)

    canvas.alpha_composite(content, (x, y))

    return canvas


# ==========================================
# Main Processing
# ==========================================
print(
    f"\n-> Target file: {input_path} "
    f"(Layout: {GRID_COLS}x{GRID_ROWS})"
)

img = Image.open(input_path).convert("RGBA")
orig_W, orig_H = img.size

cropped_img = img.crop((
    CUT_LEFT,
    CUT_TOP,
    orig_W - CUT_RIGHT,
    orig_H - CUT_BOTTOM
))

W, H = cropped_img.size

cell_w = W / float(GRID_COLS)
cell_h = H / float(GRID_ROWS)

total_stamps = GRID_COLS * GRID_ROWS

measure_canvas = Image.new(
    "RGBA",
    (MAX_W, MAX_H),
    (0, 0, 0, 0)
)

measure_draw = ImageDraw.Draw(measure_canvas)


for row in range(GRID_ROWS):
    for col in range(GRID_COLS):
        idx = row * GRID_COLS + col
        num = start_num + idx

        base_x0 = col * cell_w
        base_x1 = (col + 1) * cell_w
        base_y0 = row * cell_h
        base_y1 = (row + 1) * cell_h

        x0 = max(
            0,
            int(base_x0 - cell_w * PAD_LEFT_RATIO)
        )

        x1 = min(
            W,
            int(base_x1 + cell_w * PAD_RIGHT_RATIO)
        )

        y0 = max(
            0,
            int(base_y0 - cell_h * PAD_TOP_RATIO)
        )

        y1 = min(
            H,
            int(base_y1 + cell_h * PAD_BOTTOM_RATIO)
        )

        sub_img = cropped_img.crop((x0, y0, x1, y1))
        sub_arr = np.array(sub_img)

        sub_alpha = sub_arr[:, :, 3]
        fg = sub_alpha > 10

        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            MORPH_KERNEL_SIZE
        )

        fg_separated = cv2.morphologyEx(
            fg.astype(np.uint8),
            cv2.MORPH_OPEN,
            kernel
        ) > 0

        n_sub, sub_labels, sub_stats, sub_centroids = (
            cv2.connectedComponentsWithStats(
                fg_separated.astype(np.uint8)
            )
        )

        if n_sub > 1:
            areas = sub_stats[1:, cv2.CC_STAT_AREA]
            main_label = 1 + np.argmax(areas)

            clean_mask = np.zeros_like(fg, dtype=bool)
            roi_h, roi_w = fg.shape

            for s_id in range(1, n_sub):
                area = sub_stats[
                    s_id, cv2.CC_STAT_AREA
                ]

                bx = sub_stats[
                    s_id, cv2.CC_STAT_LEFT
                ]

                by = sub_stats[
                    s_id, cv2.CC_STAT_TOP
                ]

                bw = sub_stats[
                    s_id, cv2.CC_STAT_WIDTH
                ]

                bh = sub_stats[
                    s_id, cv2.CC_STAT_HEIGHT
                ]

                is_main = (s_id == main_label)

                touches_edge = (
                    (bx <= EDGE_THRESHOLD)
                    or (by <= EDGE_THRESHOLD)
                    or (
                        (bx + bw)
                        >= roi_w - EDGE_THRESHOLD
                    )
                    or (
                        (by + bh)
                        >= roi_h - EDGE_THRESHOLD
                    )
                )

                is_debris = (
                    (not is_main)
                    and touches_edge
                    and (area < DEBRIS_MAX_AREA)
                )

                if not is_debris:
                    clean_mask |= (sub_labels == s_id)

            if not np.any(clean_mask):
                clean_mask = (sub_labels == main_label)

            final_pixel_mask = fg & clean_mask

            sub_arr[:, :, 3] = np.where(
                final_pixel_mask,
                sub_alpha,
                0
            )

            sub_img = Image.fromarray(sub_arr, "RGBA")

        bbox = sub_img.getbbox()

        im_sticker = (
            sub_img.crop(bbox) if bbox else sub_img
        )

        # ------------------------------------------
        # Branch: With Text Overlay or No Text
        # ------------------------------------------
        if config is not None:
            item = stickers_config[num]
            cw, ch = im_sticker.size

            width_ratio = float(
                item.get("text_width_ratio", text_width_ratio_default)
            )
            height_ratio = float(
                item.get(
                    "max_text_height_ratio",
                    max_text_height_ratio_default
                )
            )

            explicit_line_count = max(
                1,
                len(str(item.get("text", "")).strip().split("\n"))
            )

            if "overlap_ratio" in item:
                anticipated_overlap = float(item["overlap_ratio"])

            elif isinstance(overlap_ratio_default, dict):
                anticipated_overlap = float(
                    overlap_ratio_default.get(
                        explicit_line_count,
                        overlap_ratio_default.get(3, 0.70)
                    )
                )

            else:
                anticipated_overlap = float(overlap_ratio_default)

            anticipated_overlap = min(
                0.95,
                max(0.0, anticipated_overlap)
            )

            # Reserve enough room for character + anticipated text overlap.
            # All dimensions here are virtual final-output pixels.
            content_max_w = max(1, MAX_W - 2 * MARGIN)
            content_max_h = max(1, MAX_H - 2 * MARGIN)

            has_text = bool(str(item.get("text", "")).strip())

            virtual_total_height = (
                ch * (
                    1.0
                    + height_ratio * (1.0 - anticipated_overlap)
                )
                if has_text else ch
            )

            output_scale = min(
                1.0,
                content_max_w / max(1, cw),
                content_max_h / max(1.0, virtual_total_height)
            )

            output_scale = max(output_scale, 1e-6)

            final_char_w = cw * output_scale
            final_char_h = ch * output_scale

            max_text_width = min(
                float(content_max_w),
                max(1.0, final_char_w * width_ratio)
            )

            max_text_height = min(
                float(content_max_h),
                max(1.0, final_char_h * height_ratio * explicit_line_count * 1.05)
            )

            print(
                f"[DEBUG Sticker {num}] "
                f"content_max_h={content_max_h:.2f}, "
                f"final_char_h={final_char_h:.2f}, "
                f"height_ratio={height_ratio:.3f}, "
                f"explicit_line_count={explicit_line_count}, "
                f"calculated_height={final_char_h * height_ratio * explicit_line_count * 1.05:.2f}, "
                f"max_text_height={max_text_height:.2f}"
            )

            style, lines = prepare_text_auto_fit(
                item,
                measure_draw,
                max_text_width,
                max_text_height
            )

            render_scale = 1.0 / output_scale

            text_img = (
                render_text_image(
                    lines,
                    style,
                    render_scale=render_scale
                )
                if lines and style else None
            )

            if text_img is not None:
                tw, th = text_img.size
                overlap_h = int(
                    round(th * style["overlap_ratio"])
                )

                canvas_w = max(cw, tw)
                canvas_h = ch + th - overlap_h

                highres_canvas = Image.new(
                    "RGBA",
                    (canvas_w, canvas_h),
                    (0, 0, 0, 0)
                )

                char_x = (canvas_w - cw) // 2
                text_x = (canvas_w - tw) // 2

                if style["position"] == "top":
                    char_y = th - overlap_h

                    # Draw the character first (back layer).
                    highres_canvas.alpha_composite(
                        im_sticker,
                        (char_x, char_y)
                    )

                    # Draw the text afterwards (front layer).
                    highres_canvas.alpha_composite(
                        text_img,
                        (text_x, 0)
                    )

                else:
                    # Draw the character first (back layer).
                    highres_canvas.alpha_composite(
                        im_sticker,
                        (char_x, 0)
                    )

                    text_y = ch - overlap_h

                    # Draw the text afterwards (front layer).
                    highres_canvas.alpha_composite(
                        text_img,
                        (text_x, text_y)
                    )

            else:
                highres_canvas = im_sticker

            # Apply one final LANCZOS resize to the complete composition.
            final_scale = min(
                output_scale,
                content_max_w / max(1, highres_canvas.width),
                content_max_h / max(1, highres_canvas.height)
            )

            final_w = max(
                1,
                int(round(highres_canvas.width * final_scale))
            )
            final_h = max(
                1,
                int(round(highres_canvas.height * final_scale))
            )

            if (final_w, final_h) != highres_canvas.size:
                content = highres_canvas.resize(
                    (final_w, final_h),
                    Image.Resampling.LANCZOS
                )
            else:
                content = highres_canvas

            # Create the final LINE-compliant canvas.
            # One dimension reaches MAX_W or MAX_H; both are even.
            canvas = make_line_canvas(content)

        else:
            # No Text Mode uses the same final sizing rules.
            canvas = make_line_canvas(im_sticker)

        out_path = os.path.join(
            OUT_DIR,
            f"{num:02d}.png"
        )

        canvas.save(
            out_path,
            "PNG",
            optimize=True
        )

        print(
            f"  -> Saved: {out_path} "
            f"({canvas.width}x{canvas.height})"
        )


print(
    f"\nAll processing complete. "
    f"(Total: {total_stamps} images)"
)