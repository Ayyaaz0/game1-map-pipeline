from pathlib import Path
import json

from PIL import Image

MAP_JSON = Path("assets/maps/room0.tmj")
OUTPUT_DIR = Path("build")
MAP_NAME = "room0_tiles"

EMPTY_TILE_ID = 0
TILESET_DIR = Path("assets/tilesets/Chroma-Noir-8x8")


def load_map_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Map file not found: {path}")

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def load_used_tile_ids(map_data: dict) -> set[int]:
    used_ids: set[int] = set()

    for layer in map_data["layers"]:
        if layer.get("type") != "tilelayer":
            continue

        for tile_id in layer.get("data", []):
            if tile_id != EMPTY_TILE_ID:
                used_ids.add(tile_id)

    return used_ids


def load_object_sprite_ids(map_data: dict) -> set[int]:
    used_ids: set[int] = set()

    for layer in map_data["layers"]:
        if layer.get("type") != "objectgroup":
            continue

        for obj in layer.get("objects", []):
            for prop in obj.get("properties", []):
                name = prop.get("name", "").strip()

                if name in ("sprite_gid", "closed_gid", "opening_gid", "open_gid"):
                    value = int(prop.get("value", 0))
                    if value != EMPTY_TILE_ID:
                        used_ids.add(value)

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
                "tilewidth": tileset["tilewidth"],
                "tileheight": tileset["tileheight"],
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
            frame_gids = [firstgid + frame["tileid"] for frame in tile["animation"]]

            animations[base_gid] = frame_gids

    return animations


def add_animation_frames(used_ids: set[int], animations: dict[int, list[int]],) -> set[int]:
    expanded_ids = set(used_ids)

    for animated_gid, frame_gids in animations.items():
        if animated_gid in used_ids:
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


def colour_distance_squared(colour_a: tuple[int, int, int], colour_b: tuple[int, int, int],) -> int:
    red_diff = colour_a[0] - colour_b[0]
    green_diff = colour_a[1] - colour_b[1]
    blue_diff = colour_a[2] - colour_b[2]

    return red_diff * red_diff + green_diff * green_diff + blue_diff * blue_diff


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
) -> dict:
    tileset = find_tileset(global_tile_id, tilesets)

    local_tile_id = global_tile_id - tileset["firstgid"]
    columns = tileset["columns"]
    tile_width = tileset["tilewidth"]
    tile_height = tileset["tileheight"]
    image = tileset_images[tileset["name"]]

    tile_x = (local_tile_id % columns) * tile_width
    tile_y = (local_tile_id // columns) * tile_height

    if tile_x + tile_width > image.width or tile_y + tile_height > image.height:
        raise ValueError(
            f"Tile ID {global_tile_id} is outside tileset image "
            f"'{tileset['name']}' at local ID {local_tile_id}."
        )

    pixels: list[int] = []

    for y in range(tile_height):
        for x in range(tile_width):
            pixel = image.getpixel((tile_x + x, tile_y + y))
            pixels.append(pixel_to_palette_index(pixel))

    return {
        "pixels": pixels,
        "width": tile_width,
        "height": tile_height,
    }


def format_pixels(tile: dict) -> str:
    rows: list[str] = []
    pixels = tile["pixels"]
    width = tile["width"]

    for index in range(0, len(pixels), width):
        row = pixels[index:index + width]
        rows.append("    " + ", ".join(map(str, row)) + ",")

    return "\n".join(rows)


def generate_header(tile_count: int, animation_count: int) -> str:
    guard = f"{MAP_NAME.upper()}_H"

    return (
        f"#ifndef {guard}\n"
        f"#define {guard}\n\n"
        f"#include <stdint.h>\n\n"
        f"#define {MAP_NAME.upper()}_COUNT {tile_count}\n"
        f"#define {MAP_NAME.upper()}_ANIMATION_COUNT {animation_count}\n\n"
        "typedef struct {\n"
        "  const uint8_t *pixels;\n"
        "  uint8_t width;\n"
        "  uint8_t height;\n"
        "} Game1_TileSprite;\n\n"
        "const Game1_TileSprite *Game1_Tiles_Find(uint16_t tiled_id);\n"
        "uint16_t Game1_Tiles_ResolveAnimation(uint16_t tiled_id, "
        "uint32_t frame_counter);\n\n"
        f"#endif // {guard}\n"
    )


def generate_source(
    tile_ids: list[int],
    tile_data: dict[int, dict],
    animations: dict[int, list[int]],
) -> str:
    parts: list[str] = [f'#include "{MAP_NAME}.h"\n\n']

    for index, tile_id in enumerate(tile_ids):
        tile = tile_data[tile_id]
        pixel_count = tile["width"] * tile["height"]

        parts.append(
            f"static const uint8_t t_{index}[{pixel_count}] = {{\n"
            f"{format_pixels(tile)}\n"
            f"}};\n\n"
        )

    parts.append(
        "typedef struct {\n"
        "  uint16_t id;\n"
        "  Game1_TileSprite sprite;\n"
        "} TileEntry;\n\n"
    )

    parts.append(f"static const TileEntry lookup[{MAP_NAME.upper()}_COUNT] = {{\n")

    for index, tile_id in enumerate(tile_ids):
        tile = tile_data[tile_id]
        parts.append(
            f"  {{ {tile_id}, {{ t_{index}, {tile['width']}, {tile['height']} }} }},\n"
        )

    parts.append("};\n\n")

    parts.append(
        "const Game1_TileSprite *Game1_Tiles_Find(uint16_t tiled_id) {\n"
        f"  for (uint16_t i = 0; i < {MAP_NAME.upper()}_COUNT; i++) {{\n"
        "    if (lookup[i].id == tiled_id) {\n"
        "      return &lookup[i].sprite;\n"
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

    for index, (_, frame_gids) in enumerate(animations.items()):
        frame_text = ", ".join(map(str, frame_gids))
        parts.append(
            f"static const uint16_t animation_{index}_frames[] = {{ "
            f"{frame_text} "
            f"}};\n"
        )

    parts.append(
        f"\nstatic const AnimationEntry animations"
        f"[{MAP_NAME.upper()}_ANIMATION_COUNT] = {{\n"
    )

    for index, (animated_gid, frame_gids) in enumerate(animations.items()):
        parts.append(
            f"  {{ {animated_gid}, {len(frame_gids)}, "
            f"animation_{index}_frames }},\n"
        )

    parts.append("};\n\n")

    parts.append(
        "uint16_t Game1_Tiles_ResolveAnimation(uint16_t tiled_id, "
        "uint32_t frame_counter) {\n"
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
        used_tile_ids.update(load_object_sprite_ids(map_data))

        if not used_tile_ids:
            print("No tile IDs found.")
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