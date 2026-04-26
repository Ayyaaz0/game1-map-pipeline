from pathlib import Path
import json

from PIL import Image

MAP_JSON = Path("assets/maps/room0.tmj")
OUTPUT_DIR = Path("build")
MAP_NAME = "room0_tiles"

TILE_WIDTH = 8
TILE_HEIGHT = 8
EMPTY_TILE_ID = 0

TILESET_DIR = Path("assets/tilesets/Chroma-Noir-8x8")


CHROMA_PALETTE = [
    (0x0D, 0x0D, 0x0D),  # 0 black
    (0x38, 0x38, 0x38),  # 1 dark grey
    (0x4F, 0x4F, 0x4F),  # 2 grey
    (0x82, 0x82, 0x82),  # 3 light grey
    (0xB5, 0xB5, 0xB5),  # 4 pale grey
    (0xD9, 0xD9, 0xD9),  # 5 white

    (0x32, 0x8C, 0x25),  # 6 dark green
    (0x5D, 0xE3, 0x4A),  # 7 light green

    (0x4C, 0x27, 0x12),  # 8 dark brown
    (0x60, 0x36, 0x1D),  # 9 brown
    (0xA8, 0x64, 0x37),  # 10 light brown
    (0xD7, 0x7C, 0x40),  # 11 sand

    (0xE6, 0x4E, 0x35),  # 12 red
    (0xFB, 0x68, 0x4F),  # 13 light red

    (0x63, 0x9B, 0xFF),  # 14 blue
    (0x4D, 0xCC, 0xED),  # 15 cyan
]


def load_map_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Map file not found: {path}")

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def load_used_tile_ids(map_data: dict) -> set[int]:
    used_ids: set[int] = set()

    for layer in map_data["layers"]:
        if layer.get("name") != "MetaTile":
            continue

        for tile_id in layer.get("data", []):
            if tile_id != EMPTY_TILE_ID:
                used_ids.add(tile_id)

    return used_ids


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
                "tiles": tileset.get("tiles", []),
            }
        )

    return sorted(tilesets, key=lambda item: item["firstgid"])


def load_animation_table(tilesets: list[dict]) -> dict[int, list[int]]:
    animations: dict[int, list[int]] = {}

    for tileset in tilesets:
        firstgid = tileset["firstgid"]

        for tile in tileset["tiles"]:
            if "animation" not in tile:
                continue

            base_gid = firstgid + tile["id"]
            frame_gids = [
                firstgid + frame["tileid"]
                for frame in tile["animation"]
            ]

            animations[base_gid] = frame_gids

    return animations


def add_animation_frames(
    used_ids: set[int],
    animations: dict[int, list[int]],
) -> set[int]:
    expanded_ids = set(used_ids)

    for animated_gid, frame_gids in animations.items():
        if animated_gid not in used_ids:
            continue

        expanded_ids.update(frame_gids)

    return expanded_ids


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


def colour_distance_squared(
    colour_a: tuple[int, int, int],
    colour_b: tuple[int, int, int],
) -> int:
    red_diff = colour_a[0] - colour_b[0]
    green_diff = colour_a[1] - colour_b[1]
    blue_diff = colour_a[2] - colour_b[2]

    return red_diff * red_diff + green_diff * green_diff + blue_diff * blue_diff


def pixel_to_palette_index(pixel: tuple[int, int, int, int]) -> int:
    red, green, blue, alpha = pixel

    if alpha < 128:
        return 0

    source_colour = (red, green, blue)

    best_index = 0
    best_distance = colour_distance_squared(source_colour, CHROMA_PALETTE[0])

    for index, palette_colour in enumerate(CHROMA_PALETTE[1:], start=1):
        distance = colour_distance_squared(source_colour, palette_colour)

        if distance < best_distance:
            best_distance = distance
            best_index = index

    return best_index


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


def generate_header(tile_count: int, animation_count: int) -> str:
    guard = f"{MAP_NAME.upper()}_H"

    return (
        f"#ifndef {guard}\n"
        f"#define {guard}\n\n"
        f"#include <stdint.h>\n\n"
        f"#define {MAP_NAME.upper()}_COUNT {tile_count}\n"
        f"#define {MAP_NAME.upper()}_ANIMATION_COUNT {animation_count}\n"
        f"#define {MAP_NAME.upper()}_WIDTH {TILE_WIDTH}\n"
        f"#define {MAP_NAME.upper()}_HEIGHT {TILE_HEIGHT}\n\n"
        f"const uint8_t *Game1_Tiles_Find(uint16_t tiled_id);\n"
        f"uint16_t Game1_Tiles_ResolveAnimation(uint16_t tiled_id, uint32_t frame_counter);\n\n"
        f"#endif // {guard}\n"
    )


def generate_source(
    tile_ids: list[int],
    tile_data: dict[int, list[int]],
    animations: dict[int, list[int]],
) -> str:
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
        "}\n\n"
    )

    parts.append(
        "typedef struct {\n"
        "  uint16_t id;\n"
        "  uint8_t frame_count;\n"
        "  const uint16_t *frames;\n"
        "} AnimationEntry;\n\n"
    )

    for index, (animated_gid, frame_gids) in enumerate(animations.items()):
        parts.append(
            f"static const uint16_t animation_{index}_frames[] = {{ "
            f"{', '.join(map(str, frame_gids))} "
            f"}};\n"
        )

    parts.append(f"\nstatic const AnimationEntry animations[{MAP_NAME.upper()}_ANIMATION_COUNT] = {{\n")

    for index, (animated_gid, frame_gids) in enumerate(animations.items()):
        parts.append(
            f"  {{ {animated_gid}, {len(frame_gids)}, animation_{index}_frames }},\n"
        )

    parts.append("};\n\n")

    parts.append(
        "uint16_t Game1_Tiles_ResolveAnimation(uint16_t tiled_id, uint32_t frame_counter) {\n"
        f"  for (uint16_t i = 0; i < {MAP_NAME.upper()}_ANIMATION_COUNT; i++) {{\n"
        "    if (animations[i].id == tiled_id) {\n"
        "      uint8_t frame_index = frame_counter % animations[i].frame_count;\n"
        "      return animations[i].frames[frame_index];\n"
        "    }\n"
        "  }\n\n"
        "  return tiled_id;\n"
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
        animations = load_animation_table(tilesets)

        used_animations = {
            animated_gid: frame_gids
            for animated_gid, frame_gids in animations.items()
            if animated_gid in used_tile_ids
        }

        export_tile_ids = sorted(add_animation_frames(used_tile_ids, used_animations))

        tileset_images = load_tileset_images(tilesets)

        tile_data = {
            tile_id: extract_tile(tile_id, tilesets, tileset_images)
            for tile_id in export_tile_ids
        }

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        header_path = OUTPUT_DIR / f"{MAP_NAME}.h"
        source_path = OUTPUT_DIR / f"{MAP_NAME}.c"

        header_path.write_text(
            generate_header(len(export_tile_ids), len(used_animations)),
            encoding="utf-8",
        )

        source_path.write_text(
            generate_source(export_tile_ids, tile_data, used_animations),
            encoding="utf-8",
        )

        print(f"Success! {len(export_tile_ids)} tiles processed.")
        print(f"Animations exported: {len(used_animations)}")
        print(f"Wrote {header_path}")
        print(f"Wrote {source_path}")

    except Exception as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()