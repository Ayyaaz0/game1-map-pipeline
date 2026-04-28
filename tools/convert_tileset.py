from pathlib import Path
import json
from PIL import Image

MAP_JSON = Path("assets/maps/room0.tmj")
OUTPUT_DIR = Path("build")
MAP_NAME = "room0_tiles"

EMPTY_TILE_ID = 0
TILESET_DIR = Path("assets/tilesets/Chroma-Noir-8x8")

# ----------------------------
# Palette (your engine palette)
# ----------------------------
CHROMA_PALETTE = [
    (0x0D, 0x0D, 0x0D),
    (0x38, 0x38, 0x38),
    (0x4F, 0x4F, 0x4F),
    (0x82, 0x82, 0x82),
    (0xB5, 0xB5, 0xB5),
    (0xD9, 0xD9, 0xD9),
    (0x32, 0x8C, 0x25),
    (0x5D, 0xE3, 0x4A),
    (0x4C, 0x27, 0x12),
    (0x60, 0x36, 0x1D),
    (0xA8, 0x64, 0x37),
    (0xD7, 0x7C, 0x40),
    (0xE6, 0x4E, 0x35),
    (0xFB, 0x68, 0x4F),
    (0x63, 0x9B, 0xFF),
    (0x4D, 0xCC, 0xED),
]

# ----------------------------
# Utils
# ----------------------------

def load_map():
    return json.loads(MAP_JSON.read_text())

def colour_distance(a, b):
    return sum((a[i] - b[i])**2 for i in range(3))

def pixel_to_palette(pixel):
    r, g, b, a = pixel
    if a < 128:
        return 0

    best = 0
    best_dist = colour_distance((r,g,b), CHROMA_PALETTE[0])

    for i, p in enumerate(CHROMA_PALETTE[1:], start=1):
        d = colour_distance((r,g,b), p)
        if d < best_dist:
            best_dist = d
            best = i

    return best

# ----------------------------
# Tile extraction
# ----------------------------

def load_tilesets(map_data):
    tilesets = []

    for ts in map_data["tilesets"]:
        tilesets.append({
            "name": ts["name"],
            "firstgid": ts["firstgid"],
            "columns": ts["columns"],
            "tilewidth": ts["tilewidth"],
            "tileheight": ts["tileheight"],
            "image": TILESET_DIR / Path(ts["image"]).name,
            "tiles": ts.get("tiles", [])
        })

    return sorted(tilesets, key=lambda t: t["firstgid"])

def find_tileset(gid, tilesets):
    chosen = None
    for ts in tilesets:
        if gid >= ts["firstgid"]:
            chosen = ts
        else:
            break
    return chosen

def extract_tile(gid, tilesets, images):
    ts = find_tileset(gid, tilesets)

    local = gid - ts["firstgid"]
    w = ts["tilewidth"]
    h = ts["tileheight"]
    cols = ts["columns"]

    img = images[ts["name"]]

    x0 = (local % cols) * w
    y0 = (local // cols) * h

    pixels = []
    for y in range(h):
        for x in range(w):
            pixels.append(pixel_to_palette(img.getpixel((x0+x, y0+y))))

    return {
        "pixels": pixels,
        "width": w,
        "height": h
    }

# ----------------------------
# GID collection
# ----------------------------

def collect_gids(map_data):
    gids = set()

    # Tile layers
    for layer in map_data["layers"]:
        if layer["type"] == "tilelayer":
            gids.update([t for t in layer["data"] if t != 0])

    # Object sprites
    for layer in map_data["layers"]:
        if layer["type"] != "objectgroup":
            continue

        for obj in layer["objects"]:
            for prop in obj.get("properties", []):
                if prop["name"].strip() in (
                    "sprite_gid", "closed_gid", "opening_gid", "open_gid"
                ):
                    gids.add(int(prop["value"]))

    return gids

# ----------------------------
# Output generation
# ----------------------------

def generate_header(count, anim_count):
    return f"""
#ifndef ROOM0_TILES_H
#define ROOM0_TILES_H

#include <stdint.h>

#define ROOM0_TILES_COUNT {count}
#define ROOM0_TILES_ANIMATION_COUNT {anim_count}

typedef struct {{
  const uint8_t *pixels;
  uint8_t width;
  uint8_t height;
}} Game1_TileSprite;

const Game1_TileSprite *Game1_Tiles_Find(uint16_t tiled_id);
uint16_t Game1_Tiles_ResolveAnimation(uint16_t tiled_id, uint32_t frame);

#endif
"""

def generate_source(tile_ids, tile_data):
    out = ['#include "room0_tiles.h"\n\n']

    # raw pixel arrays
    for i, gid in enumerate(tile_ids):
        t = tile_data[gid]
        pixels = ", ".join(map(str, t["pixels"]))
        out.append(f"static const uint8_t t_{i}[] = {{ {pixels} }};\n")

    out.append("\ntypedef struct { uint16_t id; Game1_TileSprite s; } Entry;\n")

    out.append(f"static const Entry lookup[{len(tile_ids)}] = {{\n")

    for i, gid in enumerate(tile_ids):
        t = tile_data[gid]
        out.append(
            f"  {{ {gid}, {{ t_{i}, {t['width']}, {t['height']} }} }},\n"
        )

    out.append("};\n\n")

    out.append("""
const Game1_TileSprite *Game1_Tiles_Find(uint16_t id) {
  for (uint16_t i = 0; i < ROOM0_TILES_COUNT; i++) {
    if (lookup[i].id == id) return &lookup[i].s;
  }
  return 0;
}

uint16_t Game1_Tiles_ResolveAnimation(uint16_t id, uint32_t frame) {
  return id;
}
""")

    return "".join(out)

# ----------------------------
# MAIN
# ----------------------------

def main():
    map_data = load_map()
    tilesets = load_tilesets(map_data)

    images = {
        ts["name"]: Image.open(ts["image"]).convert("RGBA")
        for ts in tilesets
    }

    gids = sorted(collect_gids(map_data))

    tile_data = {
        gid: extract_tile(gid, tilesets, images)
        for gid in gids
    }

    OUTPUT_DIR.mkdir(exist_ok=True)

    (OUTPUT_DIR / "room0_tiles.h").write_text(
        generate_header(len(gids), 0)
    )
    (OUTPUT_DIR / "room0_tiles.c").write_text(
        generate_source(gids, tile_data)
    )

    print("Tileset export complete.")

if __name__ == "__main__":
    main()