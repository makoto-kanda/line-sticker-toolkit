from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2
import os
import glob
import json
import warnings

# ==========================================
# Adjustment Parameters (Common)
# ==========================================
GRID_COLS = 8
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

# ==========================================
# Select Input Image (*.png)
# ==========================================
input_files = sorted(glob.glob("*.png"))
if not input_files:
    raise FileNotFoundError("No files matching '*.png' were found in the current directory.")

print("=== LINE Sticker Integrated Splitter ===")
print("Select an image file to process:")
for i, filename in enumerate(input_files):
    print(f"  [{i + 1}] {filename}")

choice = input(f"Enter number (1-{len(input_files)}): ").strip()
try:
    choice_idx = int(choice) - 1
    if choice_idx < 0 or choice_idx >= len(input_files):
        raise ValueError()
except ValueError:
    raise ValueError("Invalid selection. Please enter a correct number.")

input_path = input_files[choice_idx]
start_num = 1

# ==========================================
# Detect and Select Configuration File (config*.json)
# ==========================================
json_files = sorted(glob.glob("config*.json"))
config = None
config_suffix = "notext"

print("\n--- Mode / Configuration Selection ---")
print("  [0] No Text (Extract images only)")
for i, jfile in enumerate(json_files):
    print(f"  [{i + 1}] {jfile} (Apply text overlay)")

json_choice = input(f"Select number (0-{len(json_files)}): ").strip()

try:
    j_idx = int(json_choice)
    if j_idx == 0:
        print("-> [No Text Mode] Extracting images without text")
    elif 1 <= j_idx <= len(json_files):
        config_path = json_files[j_idx - 1]
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        print(f"-> [Text Mode] Configuration file: {config_path}")
        
        # Extract the wildcard part from config*.json to append to output directory name
        base_name = os.path.basename(config_path)
        stem, _ = os.path.splitext(base_name)
        if stem.startswith("config"):
            config_suffix = stem[len("config"):]
            if config_suffix.startswith("_"):
                config_suffix = config_suffix[1:]
        if not config_suffix:
            config_suffix = "text"
    else:
        raise ValueError()
except ValueError:
    print("-> Invalid input detected. Defaulting to [No Text Mode]")

# Define output directory based on the JSON suffix or default mode
OUT_DIR = f"output_{config_suffix}" if config_suffix else "output_notext"
os.makedirs(OUT_DIR, exist_ok=True)

# ==========================================
# Validate Configuration (If JSON is selected)
# ==========================================
if config is not None:
    required_keys = [
        "font_path", "font_size", "text_color",
        "outline_color", "outline_width",
        "text_position", "text_alignment",
        "text_gap", "max_lines", "auto_shrink",
        "stickers"
    ]
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(f"Missing required keys in configuration file: {missing_keys}")

    font_path = config["font_path"]
    if not os.path.isabs(font_path):
        font_path = os.path.join(os.getcwd(), font_path)
    if not os.path.isfile(font_path):
        raise FileNotFoundError(f"Font file not found: {font_path}")

    font_size_default = int(config["font_size"])
    outline_color_default = config["outline_color"]
    outline_width_default = int(config["outline_width"])
    text_position_default = config["text_position"]
    text_alignment_default = config["text_alignment"]
    text_gap_default = int(config["text_gap"])
    max_lines_default = int(config["max_lines"])
    auto_shrink_default = bool(config["auto_shrink"])

    stickers_config = {}
    for item in config["stickers"]:
        number = int(item["number"])
        stickers_config[number] = item

    expected_total = GRID_COLS * GRID_ROWS
    expected_numbers = set(range(1, expected_total + 1))
    actual_numbers = set(stickers_config.keys())
    if actual_numbers != expected_numbers:
        missing = sorted(expected_numbers - actual_numbers)
        extra = sorted(actual_numbers - expected_numbers)
        raise ValueError(f"Sticker numbers do not match the grid. Missing: {missing} / Extra: {extra}")

# ==========================================
# Font Loading & Text Rendering Helpers (For JSON Mode)
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
                    axis_name = axis_name.decode("utf-8", errors="ignore")
                if str(axis_name).lower() in ("weight", "wght", "font weight"):
                    weight_axis_index = i
                    break
            if weight_axis_index is not None:
                axis = axes[weight_axis_index]
                target = max(float(axis["minimum"]), min(float(axis["maximum"]), float(weight)))
                values = [float(a.get("default", a.get("minimum", 0))) for a in axes]
                values[weight_axis_index] = target
                font.set_variation_by_axes(values)
        except Exception:
            if not warned_static_font:
                warnings.warn("Unable to apply Variable Font weight axis. Continuing with standard weight.", RuntimeWarning)
                warned_static_font = True
    font_cache[cache_key] = font
    return font

def measure_text(draw, text, font, stroke_width):
    return draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)

def text_width(draw, text, font, stroke_width):
    bbox = measure_text(draw, text, font, stroke_width)
    return bbox[2] - bbox[0]

def wrap_text(text, draw, font, stroke_width, max_width):
    lines = []
    for paragraph in text.split("\n"):
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            candidate = current + char
            if current and text_width(draw, candidate, font, stroke_width) > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines

def prepare_text(item, draw, available_width):
    text = item.get("text", "")
    if text == "":
        return None, []
    color = item.get("color", config["text_color"])
    outline_color = item.get("outline_color", outline_color_default)
    outline_width = int(item.get("outline_width", outline_width_default))
    size = int(item.get("font_size", font_size_default))
    weight = item.get("font_weight", config.get("font_weight"))
    max_lines = int(item.get("max_lines", max_lines_default))
    auto_shrink = bool(item.get("auto_shrink", auto_shrink_default))

    while True:
        font = load_font(size, weight)
        lines = wrap_text(text, draw, font, outline_width, available_width)
        widest = max((text_width(draw, line, font, outline_width) for line in lines), default=0)
        if widest <= available_width and len(lines) <= max_lines:
            break
        if not auto_shrink or size <= 8:
            raise ValueError(f"Sticker {item['number']}: Text exceeds available area.")
        size -= 1

    return {
        "font": font, "color": color, "outline_color": outline_color,
        "outline_width": outline_width, "position": item.get("position", text_position_default),
        "alignment": item.get("alignment", text_alignment_default),
        "gap": int(item.get("text_gap", text_gap_default)), "max_lines": max_lines
    }, lines

def draw_text_block(canvas, lines, style, y_top, horizontal_margin):
    if not lines:
        return
    font = style["font"]
    stroke_width = style["outline_width"]
    draw = ImageDraw.Draw(canvas)
    y = y_top

    for line in lines:
        if not line:
            bbox = draw.textbbox((0, 0), "国Ag", font=font, stroke_width=stroke_width)
            y += bbox[3] - bbox[1]
            continue

        nominal_bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        nominal_w = max(1, nominal_bbox[2] - nominal_bbox[0])
        nominal_h = max(1, nominal_bbox[3] - nominal_bbox[1])
        temp_pad = max(8, stroke_width + 4)
        temp = Image.new("RGBA", (nominal_w + temp_pad * 2, nominal_h + temp_pad * 2), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp)
        temp_draw.text((temp_pad - nominal_bbox[0], temp_pad - nominal_bbox[1]), line, font=font, fill=style["color"], stroke_width=stroke_width, stroke_fill=style["outline_color"])
        
        actual_bbox = temp.getbbox()
        if actual_bbox is None:
            y += nominal_h
            continue
        rendered = temp.crop(actual_bbox)
        rendered_w, rendered_h = rendered.size

        alignment = style["alignment"]
        if alignment == "left":
            x = horizontal_margin
        elif alignment == "right":
            x = canvas.width - horizontal_margin - rendered_w
        else:
            x = (canvas.width - rendered_w) // 2

        x = max(horizontal_margin, min(x, canvas.width - horizontal_margin - rendered_w))
        canvas.alpha_composite(rendered, (int(x), int(y)))
        y += rendered_h
    return y - y_top

# ==========================================
# Main Processing
# ==========================================
print(f"\n-> Target file: {input_path} (Layout: {GRID_COLS}x{GRID_ROWS})")
img = Image.open(input_path).convert("RGBA")
orig_W, orig_H = img.size

cropped_img = img.crop((CUT_LEFT, CUT_TOP, orig_W - CUT_RIGHT, orig_H - CUT_BOTTOM))
W, H = cropped_img.size

cell_w = W / float(GRID_COLS)
cell_h = H / float(GRID_ROWS)
total_stamps = GRID_COLS * GRID_ROWS

measure_canvas = Image.new("RGBA", (MAX_W, MAX_H), (0, 0, 0, 0))
measure_draw = ImageDraw.Draw(measure_canvas)

for row in range(GRID_ROWS):
    for col in range(GRID_COLS):
        idx = row * GRID_COLS + col
        num = start_num + idx

        base_x0 = col * cell_w
        base_x1 = (col + 1) * cell_w
        base_y0 = row * cell_h
        base_y1 = (row + 1) * cell_h

        x0 = max(0, int(base_x0 - cell_w * PAD_LEFT_RATIO))
        x1 = min(W, int(base_x1 + cell_w * PAD_RIGHT_RATIO))
        y0 = max(0, int(base_y0 - cell_h * PAD_TOP_RATIO))
        y1 = min(H, int(base_y1 + cell_h * PAD_BOTTOM_RATIO))

        sub_img = cropped_img.crop((x0, y0, x1, y1))
        sub_arr = np.array(sub_img)
        sub_alpha = sub_arr[:, :, 3]
        fg = sub_alpha > 10

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, MORPH_KERNEL_SIZE)
        fg_separated = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, kernel) > 0

        n_sub, sub_labels, sub_stats, sub_centroids = cv2.connectedComponentsWithStats(fg_separated.astype(np.uint8))
        if n_sub > 1:
            areas = sub_stats[1:, cv2.CC_STAT_AREA]
            main_label = 1 + np.argmax(areas)
            clean_mask = np.zeros_like(fg, dtype=bool)
            roi_h, roi_w = fg.shape

            for s_id in range(1, n_sub):
                area = sub_stats[s_id, cv2.CC_STAT_AREA]
                bx = sub_stats[s_id, cv2.CC_STAT_LEFT]
                by = sub_stats[s_id, cv2.CC_STAT_TOP]
                bw = sub_stats[s_id, cv2.CC_STAT_WIDTH]
                bh = sub_stats[s_id, cv2.CC_STAT_HEIGHT]
                is_main = (s_id == main_label)
                touches_edge = (bx <= EDGE_THRESHOLD) or (by <= EDGE_THRESHOLD) or \
                               ((bx + bw) >= roi_w - EDGE_THRESHOLD) or ((by + bh) >= roi_h - EDGE_THRESHOLD)
                is_debris = (not is_main) and touches_edge and (area < DEBRIS_MAX_AREA)
                if not is_debris:
                    clean_mask |= (sub_labels == s_id)

            if not np.any(clean_mask):
                clean_mask = (sub_labels == main_label)
            final_pixel_mask = fg & clean_mask
            sub_arr[:, :, 3] = np.where(final_pixel_mask, sub_alpha, 0)
            sub_img = Image.fromarray(sub_arr, "RGBA")

        bbox = sub_img.getbbox()
        im_sticker = sub_img.crop(bbox) if bbox else sub_img

        # ------------------------------------------
        # Branch: With Text Overlay or No Text
        # ------------------------------------------
        if config is not None:
            item = stickers_config[num]
            available_text_width = MAX_W - 2 * MARGIN
            style, lines = prepare_text(item, measure_draw, available_text_width)

            text_block_h = 0
            if style and lines:
                bboxes = [measure_text(measure_draw, line, style["font"], style["outline_width"]) for line in lines]
                text_block_h = sum(b[3] - b[1] for b in bboxes)
                char_max_h = MAX_H - 2 * MARGIN - style["gap"] - text_block_h
            else:
                char_max_h = MAX_H - 2 * MARGIN

            char_max_w = MAX_W - 2 * MARGIN
            cw0, ch0 = im_sticker.size
            scale = min(1.0, char_max_w / cw0, char_max_h / ch0)
            if scale < 1.0:
                im_sticker = im_sticker.resize((max(1, int(cw0 * scale)), max(1, int(ch0 * scale))), Image.Resampling.LANCZOS)

            char_w, char_h = im_sticker.size
            actual_text_w = max((text_width(measure_draw, line, style["font"], style["outline_width"]) for line in lines), default=0) if (style and lines) else 0

            canvas_w = max(char_w, actual_text_w) + 2 * MARGIN
            canvas_h = (char_h + style["gap"] + text_block_h + 2 * MARGIN) if (style and lines) else (char_h + 2 * MARGIN)

            if canvas_w % 2: canvas_w += 1
            if canvas_h % 2: canvas_h += 1

            canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            char_x = (canvas_w - char_w) // 2

            if style and lines and style["position"] == "top":
                draw_text_block(canvas, lines, style, MARGIN, MARGIN)
                char_y = MARGIN + text_block_h + style["gap"]
            else:
                char_y = MARGIN

            canvas.alpha_composite(im_sticker, (char_x, char_y))

            if style and lines and style["position"] == "bottom":
                draw_text_block(canvas, lines, style, char_y + char_h + style["gap"], MARGIN)

            final_scale = min(1.0, MAX_W / canvas.width, MAX_H / canvas.height)
            if final_scale < 1.0:
                canvas = canvas.resize((max(2, int(canvas.width * final_scale)), max(2, int(canvas.height * final_scale))), Image.Resampling.LANCZOS)

        else:
            # No Text Mode
            w, h = im_sticker.size
            scale = min(1.0, (MAX_W - 2 * MARGIN) / w, (MAX_H - 2 * MARGIN) / h)
            if scale < 1.0:
                im_sticker = im_sticker.resize((max(2, int(w * scale)), max(2, int(h * scale))), Image.Resampling.LANCZOS)

            mw, mh = im_sticker.size
            canvas = Image.new('RGBA', (mw + 2 * MARGIN, mh + 2 * MARGIN), (0, 0, 0, 0))
            canvas.alpha_composite(im_sticker, (MARGIN, MARGIN))
            cw, ch = canvas.size
            if cw % 2 != 0 or ch % 2 != 0:
                canvas2 = Image.new('RGBA', (cw + cw % 2, ch + ch % 2), (0, 0, 0, 0))
                canvas2.alpha_composite(canvas, (0, 0))
                canvas = canvas2

        out_path = os.path.join(OUT_DIR, f'{num:02d}.png')
        canvas.save(out_path, 'PNG', optimize=True)
        print(f"  -> Saved: {out_path}")

print(f"\nAll processing complete. (Total: {total_stamps} images)")