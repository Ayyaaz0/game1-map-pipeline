from pathlib import Path
import csv
from PIL import Image

# --- Configuration ---
MAP_CSV = Path("assets/maps/room0.csv")  
OUTPUT_DIR = Path("build")
MAP_NAME = "room0_tiles"
TILE_WIDTH = 8
TILE_HEIGHT = 8

# --- Tileset Mapping (Extracted from  room0.tmx and .tsx files) ---
# Note: Ensure these paths point to where your .png files are stored on your PC
TILESET_CONFIG = [
    {"name": "Patterns",       "firstgid": 25201, "columns": 8,  "path": "assets/tilesets/Patterns-and-Symbols.png"},
    {"name": "Overworld",      "firstgid": 28143, "columns": 35, "path": "assets/tilesets/Overworld.png"},
    {"name": "Water",          "firstgid": 29263, "columns": 22, "path": "assets/tilesets/Water.png"},
]

def load_used_tile_ids(path: Path) -> list[int]:
    used_ids: set[int] = set()
    if not path.exists():
        print(f"Warning: {path} not found.")
        return []

    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        for row in reader:
            for value in row:
                val = value.strip()
                if not val or val == "-1" or val == "0":
                    continue
                used_ids.add(int(val))
    return sorted(used_ids)

def pixel_to_palette_index(pixel: tuple[int, int, int, int]) -> int:
    r, g, b, a = pixel
    if a < 128: # Transparency check
        return 0
    # Simple grayscale conversion for your 16-color monochrome-style palette
    brightness = (r + g + b) // 3
    return min(15, brightness // 16)

def extract_tile(global_tile_id: int, tileset_images: dict) -> list[int]:
    # 1. Identify which tileset this ID belongs to
    ts = None
    for config in reversed(TILESET_CONFIG):
        if global_tile_id >= config["firstgid"]:
            ts = config
            break
    
    if not ts:
        return [0] * (TILE_WIDTH * TILE_HEIGHT)

    # 2. Get the local ID relative to the start of that image
    local_id = global_tile_id - ts["firstgid"]
    img = tileset_images[ts["name"]]
    
    # 3. Calculate X/Y using that specific sheet's column count
    tile_x = (local_id % ts["columns"]) * TILE_WIDTH
    tile_y = (local_id // ts["columns"]) * TILE_HEIGHT

    tile_pixels = []
    for y in range(TILE_HEIGHT):
        for x in range(TILE_WIDTH):
            try:
                pixel = img.getpixel((tile_x + x, tile_y + y))
                tile_pixels.append(pixel_to_palette_index(pixel))
            except IndexError:
                tile_pixels.append(0) # Safety for IDs that might exceed image bounds
                
    return tile_pixels

def generate_header(tile_ids: list[int]) -> str:
    guard = f"{MAP_NAME.upper()}_H"

    return (
        f"#ifndef {guard}\n"
        f"#define {guard}\n\n"
        f"#include <stdint.h>\n\n"
        f"#define {MAP_NAME.upper()}_COUNT {len(tile_ids)}\n"
        f"#define {MAP_NAME.upper()}_WIDTH {TILE_WIDTH}\n"
        f"#define {MAP_NAME.upper()}_HEIGHT {TILE_HEIGHT}\n\n"
        f"const uint8_t *Game1_Tiles_Find(uint16_t tiled_id);\n\n"
        f"#endif // {guard}\n"
    )
def generate_source(tile_ids: list[int], tiles_data: dict) -> str:
    parts = [f'#include "{MAP_NAME}.h"\n\n']
    
    # Write pixel data for each used tile
    for i, tid in enumerate(tile_ids):
        pixels = ", ".join(map(str, tiles_data[tid]))
        parts.append(f"static const uint8_t t_{i}[64] = {{ {pixels} }};\n")

    # Entry table mapping GID to pixels
    parts.append("\ntypedef struct { uint16_t id; const uint8_t *p; } TileMap;\n")
    parts.append(f"static const TileMap lookup[{len(tile_ids)}] = {{\n")
    for i, tid in enumerate(tile_ids):
        parts.append(f"    {{ {tid}, t_{i} }},\n")
    parts.append("};\n\n")

    # Lookup function
    parts.append(
        "const uint8_t *Game1_Tiles_Find(uint16_t tiled_id) {\n"
        f"    for(int i=0; i<{len(tile_ids)}; i++) {{\n"
        "        if(lookup[i].id == tiled_id) return lookup[i].p;\n"
        "    }\n"
        "    return 0;\n"
        "}\n"
    )
    return "".join(parts)

def main():
    used_ids = load_used_tile_ids(MAP_CSV)
    print(f"Found {len(used_ids)} unique tiles in map.")

    # Pre-load all tileset images
    images = {}
    for ts in TILESET_CONFIG:
        try:
            images[ts["name"]] = Image.open(ts["path"]).convert("RGBA")
        except FileNotFoundError:
            print(f"Error: Could not find {ts['path']}")
            return

    # Extract all tile pixels
    tiles_data = {tid: extract_tile(tid, images) for tid in used_ids}

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / f"{MAP_NAME}.h").write_text(generate_header(used_ids))
    (OUTPUT_DIR / f"{MAP_NAME}.c").write_text(generate_source(used_ids, tiles_data))
    print(f"Done! Files written to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()