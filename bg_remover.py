import os
import re
import cv2
import numpy as np

# ==========================================
# Adjustment Parameters
# ==========================================
# Tolerance value for floodFill (handles anti-aliased edges)
DIFF_VAL = 15
# ==========================================

def list_png_files():
    files = [f for f in os.listdir('.') if f.lower().endswith('.png')]
    return sorted(files)

def parse_coordinates(coord_str):
    pattern = r'\(?\s*(\d+)\s*,\s*(\d+)\s*\)?'
    matches = re.findall(pattern, coord_str)
    coords = []
    for m in matches:
        coords.append((int(m[0]), int(m[1])))
    return coords

def main():
    png_files = list_png_files()
    if not png_files:
        print("Error: No .png files found in the current directory.")
        return

    print("=== PNG File List in Current Directory ===")
    for idx, filename in enumerate(png_files):
        print(f"[{idx}] {filename}")
    
    try:
        selection = int(input("\nEnter the number of the file to process: "))
        if selection < 0 or selection >= len(png_files):
            print("Error: Invalid number selection.")
            return
    except ValueError:
        print("Error: Please enter a valid number.")
        return

    target_file = png_files[selection]
    print(f"Selected file: {target_file}")

    img = cv2.imread(target_file, cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"Error: Could not read the file '{target_file}'.")
        return

    if img.shape[2] == 3:
        b, g, r = cv2.split(img)
        alpha = np.full(b.shape, 255, dtype=np.uint8)
        img = cv2.merge([b, g, r, alpha])

    h, w = img.shape[:2]
    print(f"Image size: width (w) = {w}, height (h) = {h}")

    coord_input = input("\nEnter additional background seed coordinates to remove\nExample: (128,666),(480,640),(800,655),(450,225)\n> ")
    user_coords = parse_coordinates(coord_input)
    print(f"-> Parsed user coordinates: {user_coords}")

    # Four corners of the image (skipped if already transparent to prevent accidental removal)
    corners = [
        (0, 0),         # Top-left
        (w - 1, 0),     # Top-right
        (0, h - 1),     # Bottom-left
        (w - 1, h - 1)  # Bottom-right
    ]
    
    valid_corners = []
    for pt in corners:
        cx, cy = pt
        # Use corner as seed only if the alpha channel is greater than 0 (opaque background exists)
        if img[cy, cx, 3] > 0:
            valid_corners.append(pt)
        else:
            print(f"  [Info] Corner coordinate {pt} is already transparent; skipping.")

    all_seeds = valid_corners + user_coords
    print(f"\nRunning floodFill from a total of {len(all_seeds)} seed points...")

    bgr_img = np.ascontiguousarray(img[:, :, :3])
    flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY
    
    loDiff = (DIFF_VAL, DIFF_VAL, DIFF_VAL)
    upDiff = (DIFF_VAL, DIFF_VAL, DIFF_VAL)

    # Final mask for integration
    final_fill_mask = np.zeros((h, w), dtype=np.uint8)

    for idx, pt in enumerate(all_seeds):
        x, y = pt
        if 0 <= x < w and 0 <= y < h:
            pixel_color = bgr_img[y, x]
            print(f"  [{idx}] Coordinate {pt} -> Color (B,G,R): {pixel_color}", end="")
            
            single_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
            retval, image, single_mask, rect = cv2.floodFill(
                bgr_img, single_mask, (x, y), 0, 
                loDiff=loDiff, upDiff=upDiff, flags=flags
            )
            
            valid_mask = single_mask[1:h+1, 1:w+1]
            final_fill_mask = cv2.bitwise_or(final_fill_mask, valid_mask)
            print(f" -> Filled region (rect): {rect}")
        else:
            print(f"  [{idx}] Warning: Coordinate {pt} is out of image bounds (skipped).")

    # Mask valid values are 255, evaluated using > 0
    painted_count = np.sum(final_fill_mask > 0)
    print(f"\n[Debug] Total pixels filled by mask: {painted_count}")

    # Anti-aliasing processing (smooth transparency along boundaries)
    alpha_channel = img[:, :, 3].astype(np.float32)
    alpha_channel[final_fill_mask > 0] = 0.0

    float_fill_mask = (final_fill_mask > 0).astype(np.float32)
    blurred_mask = cv2.GaussianBlur(float_fill_mask, (3, 3), 0.5)
    
    for y in range(h):
        for x in range(w):
            if final_fill_mask[y, x] > 0:
                alpha_channel[y, x] = 0.0
            elif blurred_mask[y, x] > 0.01 and blurred_mask[y, x] < 0.99:
                factor = blurred_mask[y, x]
                alpha_channel[y, x] = alpha_channel[y, x] * (1.0 - factor)

    img[:, :, 3] = np.clip(alpha_channel, 0, 255).astype(np.uint8)

    base_name, _ = os.path.splitext(target_file)
    output_file = f"{base_name}_transparent.png"
    
    cv2.imwrite(output_file, img)
    print(f"\nProcessing complete!\nSaved file: {output_file}")

if __name__ == '__main__':
    main()