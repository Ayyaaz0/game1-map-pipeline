from pathlib import Path
import json

from PIL import Image

# --- Configuration ---
MAP_JSON = Path("assets/maps/room0.tmj")
OUTPUT_DIR = Path("build")
MAP_NAME = "room0_tiles"

TILE_WIDTH = 8
TILE_HEIGHT = 8
EMPTY_TILE_ID = 0

TILESET_DIR = Path("assets/tilesets/Chroma-Noir-8x8")


def load_map_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Map file not found: {path}")

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def load_used_tile_ids(map_data: dict) -> list[int]:
    used_ids: set[int] = set()

    for layer in map_data["layers"]:
        if layer.get("name") != "MetaTile":
            continue

        for tile_id in layer.get("data", []):
            if tile_id != EMPTY_TILE_ID:
                used_ids.add(tile_id)

    return sorted(used_ids)


def load_tileset_config(map_data: dict) -> list[dict]:
    tilesets: list[dict] = []

    for tileset in map_data["tilesets"]:
        image_name = Path(tileset["image"]).name

        tilesets.append(
            {
                "name": tileset["name"],
                "firstgid": tileset["firstgid"],
                "columns": tileset["columns"],
                "path": TILESET_DIR / image_name,
            }
        )

    return sorted(tilesets, key=lambda item: item["firstgid"])


def load_tileset_images(tilesets: list[dict]) -> dict[str, Image.Image]:
    images: dict[str, Image.Image] = {}

    for tileset in tilesets:
        path = tileset["path"]

        if not path.exists():
            raise FileNotFoundError(
                f"Missing PNG: {path}\n"
                f"Place your tileset PNG files in {TILESET_DIR}"
            )

        images[tileset["name"]] = Image.open(path).convert("RGBA")

    return images


def find_tileset(global_tile_id: int, tilesets: list[dict]) -> dict:
    selected = None

    for tileset in tilesets:
        if global_tile_id >= tileset["firstgid"]:
            selected = tileset
        else:
            break

    if selected is None:
        raise ValueError(f"No tileset found for tile ID {global_tile_id}")

    return selected


def pixel_to_palette_index(pixel: tuple[int, int, int, int]) -> int:
    red, green, blue, alpha = pixel

    if alpha < 128:
        return 0

    if blue > red and blue > green:
        return 6

    if green > red and green > blue:
        return 2

    if red > green and red > blue:
        return 4

    if red > 180 and green > 120 and blue < 80:
        return 8

    brightness = (red + green + blue) // 3

    if brightness < 40:
        return 0
    if brightness < 100:
        return 1
    if brightness < 170:
        return 7

    return 15


def extract_tile(
    global_tile_id: int,
    tilesets: list[dict],
    tileset_images: dict[str, Image.Image],
) -> list[int]:
    tileset = find_tileset(global_tile_id, tilesets)

    local_tile_id = global_tile_id - tileset["firstgid"]
    columns = tileset["columns"]
    image = tileset_images[tileset["name"]]

    tile_x = (local_tile_id % columns) * TILE_WIDTH
    tile_y = (local_tile_id // columns) * TILE_HEIGHT

    if tile_x + TILE_WIDTH > image.width or tile_y + TILE_HEIGHT > image.height:
        raise ValueError(
            f"Tile ID {global_tile_id} is outside tileset image "
            f"'{tileset['name']}' at local ID {local_tile_id}."
        )

    pixels: list[int] = []

    for y in range(TILE_HEIGHT):
        for x in range(TILE_WIDTH):
            pixel = image.getpixel((tile_x + x, tile_y + y))
            pixels.append(pixel_to_palette_index(pixel))

    return pixels


def format_pixels(pixels: list[int]) -> str:
    rows: list[str] = []

    for index in range(0, len(pixels), TILE_WIDTH):
        row = pixels[index:index + TILE_WIDTH]
        rows.append("    " + ", ".join(map(str, row)) + ",")

    return "\n".join(rows)


def generate_header(tile_count: int) -> str:
    guard = f"{MAP_NAME.upper()}_H"

    return (
        f"#ifndef {guard}\n"
        f"#define {guard}\n\n"
        f"#include <stdint.h>\n\n"
        f"#define {MAP_NAME.upper()}_COUNT {tile_count}\n"
        f"#define {MAP_NAME.upper()}_WIDTH {TILE_WIDTH}\n"
        f"#define {MAP_NAME.upper()}_HEIGHT {TILE_HEIGHT}\n\n"
        f"const uint8_t *Game1_Tiles_Find(uint16_t tiled_id);\n\n"
        f"#endif // {guard}\n"
    )


def generate_source(tile_ids: list[int], tile_data: dict[int, list[int]]) -> str:
    parts: list[str] = [f'#include "{MAP_NAME}.h"\n\n']

    for index, tile_id in enumerate(tile_ids):
        parts.append(
            f"static const uint8_t t_{index}"
            f"[{MAP_NAME.upper()}_WIDTH * {MAP_NAME.upper()}_HEIGHT] = {{\n"
            f"{format_pixels(tile_data[tile_id])}\n"
            f"}};\n\n"
        )

    parts.append(
        "typedef struct {\n"
        "  uint16_t id;\n"
        "  const uint8_t *pixels;\n"
        "} TileEntry;\n\n"
    )

    parts.append(f"static const TileEntry lookup[{MAP_NAME.upper()}_COUNT] = {{\n")

    for index, tile_id in enumerate(tile_ids):
        parts.append(f"  {{ {tile_id}, t_{index} }},\n")

    parts.append("};\n\n")

    parts.append(
        "const uint8_t *Game1_Tiles_Find(uint16_t tiled_id) {\n"
        f"  for (uint16_t i = 0; i < {MAP_NAME.upper()}_COUNT; i++) {{\n"
        "    if (lookup[i].id == tiled_id) {\n"
        "      return lookup[i].pixels;\n"
        "    }\n"
        "  }\n\n"
        "  return 0;\n"
        "}\n"
    )

    return "".join(parts)


def main() -> None:
    try:
        map_data = load_map_json(MAP_JSON)

        used_tile_ids = load_used_tile_ids(map_data)

        if not used_tile_ids:
            print("No tiles found in 'MetaTile' layer.")
            return

        tilesets = load_tileset_config(map_data)
        tileset_images = load_tileset_images(tilesets)

        tile_data = {
            tile_id: extract_tile(tile_id, tilesets, tileset_images)
            for tile_id in used_tile_ids
        }

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        header_path = OUTPUT_DIR / f"{MAP_NAME}.h"
        source_path = OUTPUT_DIR / f"{MAP_NAME}.c"

        header_path.write_text(generate_header(len(used_tile_ids)), encoding="utf-8")
        source_path.write_text(
            generate_source(used_tile_ids, tile_data), encoding="utf-8"
        )

        print(f"Success! {len(used_tile_ids)} tiles processed.")
        print(f"Wrote {header_path}")
        print(f"Wrote {source_path}")

    except Exception as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()