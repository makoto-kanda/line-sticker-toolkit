import os
import zipfile
from PIL import Image

def select_target_directory():
    """final* に一致するディレクトリを検索し、番号で選択させる"""
    print("=== LINE Stamp Directory Selector ===")
    # カレントディレクトリから final* に一致するディレクトリを抽出
    candidates = [d for d in os.listdir('.') if os.path.isdir(d) and d.lower().startswith('final')]
    
    # もし一つも見つからない場合はデフォルトで 'final' を候補にする
    if not candidates:
        if os.path.exists('final'):
            candidates = ['final']
        else:
            print("❌ Error: No 'final*' directories found in the current directory.")
            return None

    if len(candidates) == 1:
        selected = candidates[0]
        print(f"📁 Target directory detected automatically: ./{selected}")
        return selected

    print("Multiple target directories found:")
    for idx, dir_name in enumerate(candidates, 1):
        print(f"  [{idx}] {dir_name}")
    
    while True:
        try:
            choice = input("\nSelect the target directory number: ").strip()
            if not choice:
                continue
            idx = int(choice)
            if 1 <= idx <= len(candidates):
                selected = candidates[idx - 1]
                print(f"📁 Selected: ./{selected}")
                return selected
            else:
                print(f"❌ Please enter a number between 1 and {len(candidates)}.")
        except ValueError:
            print("❌ Invalid input. Please enter a valid number.")

def validate_and_package_stamps():
    target_dir = select_target_directory()
    if not target_dir:
        return

    print(f"\n=== LINE Stamp Validation Tool ===")
    print(f"Checking directory: {target_dir}\n")
    
    files = os.listdir(target_dir)
    png_files = [f for f in files if f.lower().endswith('.png')]
    
    stamp_files = []
    main_found = False
    tab_found = False
    other_files = []
    
    for f in png_files:
        if f.lower() == "main.png":
            main_found = True
        elif f.lower() == "tab.png":
            tab_found = True
        elif f[:-4].isdigit():
            stamp_files.append(f)
        else:
            other_files.append(f)
            
    stamp_files.sort(key=lambda x: int(x[:-4]))
    
    errors = 0
    warnings = 0
    
    # 1. Check Stamp Count & Naming
    count = len(stamp_files)
    print(f"[1. Stamp Count Check]")
    print(f"   Found {count} numbered stamp files (e.g., 01.png to {stamp_files[-1] if stamp_files else 'None'}).")
    allowed_counts = [8, 16, 24, 32, 40]
    if count in allowed_counts:
        print(f"   ✅ Stamp count ({count}) is valid (allowed: {allowed_counts}).")
    else:
        print(f"   ❌ Stamp count ({count}) is INVALID. LINE requires 8, 16, 24, 32, or 40 stickers.")
        errors += 1
        
    expected_names = [f"{i:02d}.png" for i in range(1, count + 1)]
    actual_names = stamp_files
    if actual_names == expected_names:
        print(f"   ✅ Stamp file naming format is sequential (01.png, 02.png, ...).")
    else:
        print(f"   ⚠️ Warning: Stamp filenames are not strictly sequential two-digit format (01.png, 02.png...).")
        warnings += 1

    print("\n[2. Required Extra Images Check]")
    if main_found:
        print(f"   ✅ main.png found.")
    else:
        print(f"   ❌ main.png is MISSING.")
        errors += 1
        
    if tab_found:
        print(f"   ✅ tab.png found.")
    else:
        print(f"   ❌ tab.png is MISSING.")
        errors += 1

    if other_files:
        print(f"   ⚠️ Notice: Found other non-stamp PNG files (will be excluded from ZIP): {other_files}")

    print("\n[3. Detailed Image Specifications Check]")
    
    def check_image(path, expected_w, expected_h, label, exact_size=True, check_transparency=True):
        nonlocal errors, warnings
        if not os.path.exists(path):
            return
        try:
            with Image.open(path) as img:
                w, h = img.size
                mode = img.mode
                
                if exact_size:
                    size_ok = (w == expected_w and h == expected_h)
                else:
                    size_ok = (w <= 370 and h <= 320 and w % 2 == 0 and h % 2 == 0)
                
                if size_ok:
                    if exact_size:
                        print(f"   ✅ {label} size: {w}x{h} px (Correct)")
                    else:
                        print(f"   ✅ {label} size: {w}x{h} px (Within max 370x320, even numbers)")
                else:
                    if exact_size:
                        print(f"   ❌ {label} size: {w}x{h} px. Expected exactly {expected_w}x{expected_h} px.")
                    else:
                        print(f"   ❌ {label} size: {w}x{h} px. Must be <= 370x320 and even numbers.")
                    errors += 1
                
                if check_transparency:
                    if mode in ('RGBA', 'LA') or (mode == 'P' and 'transparency' in img.info):
                        print(f"   ✅ {label} has transparency (Mode: {mode}).")
                    else:
                        print(f"   ⚠️ Warning: {label} (Mode: {mode}) does not appear to have an alpha channel/transparency.")
                        warnings += 1
        except Exception as e:
            print(f"   ❌ Error reading {path}: {e}")
            errors += 1

    if main_found:
        check_image(os.path.join(target_dir, "main.png"), 240, 240, "main.png", exact_size=True)
        
    if tab_found:
        check_image(os.path.join(target_dir, "tab.png"), 96, 74, "tab.png", exact_size=True)

    print(f"   Checking {len(stamp_files)} stamp images...")
    for sf in stamp_files:
        path = os.path.join(target_dir, sf)
        check_image(path, 370, 320, sf, exact_size=False)

    print("\n=== Summary ===")
    if errors == 0:
        print(f"🎉 All checks passed successfully! (Warnings: {warnings})")
        
        # 4. ZIP Packaging (Only valid required files are included)
        zip_filename = f"{target_dir}_upload.zip"
        print(f"\n📦 Creating upload ZIP package: {zip_filename}...")
        
        try:
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add valid numbered stamps
                for sf in stamp_files:
                    file_path = os.path.join(target_dir, sf)
                    zipf.write(file_path, arcname=sf)
                # Add main.png and tab.png
                if main_found:
                    zipf.write(os.path.join(target_dir, "main.png"), arcname="main.png")
                if tab_found:
                    zipf.write(os.path.join(target_dir, "tab.png"), arcname="tab.png")
            
            print(f"   ✅ Successfully generated: {zip_filename}")
            print("   (Only required stamp files, main.png, and tab.png were packed, excluding any extra files.)")
        except Exception as e:
            print(f"   ❌ Failed to create ZIP file: {e}")
            
    else:
        print(f"❌ Found {errors} error(s) and {warnings} warning(s).")
        print("   ZIP packaging was skipped. Please fix the errors before generating the upload package.")

if __name__ == "__main__":
    validate_and_package_stamps()