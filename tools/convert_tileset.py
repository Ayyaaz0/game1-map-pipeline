from pathlib import Path
import json

from PIL import Image

MAP_JSON = Path("assets/maps/room0.tmj")
OUTPUT_DIR = Path("build")
MAP_NAME = "room0_tiles"

EMPTY_TILE_ID = 0
TILESET_DIR = Path("assets/tilesets/Chroma-Noir-8x8")

# Engine palette index map.
# These indices must match your Chroma palette order in LCD.c / LCD.h.
EXACT_COLOUR_MAP = {
    # Greys
    (0x0D, 0x0D, 0x0D): 0,   # black
    (0x38, 0x38, 0x38): 1,
    (0x4F, 0x4F, 0x4F): 2,
    (0x53, 0x53, 0x53): 2,   # asset grey variant
    (0x82, 0x82, 0x82): 3,
    (0xB5, 0xB5, 0xB5): 4,
    (0xD9, 0xD9, 0xD9): 5,   # white

    # Blues
    (0x2A, 0x45, 0x5A): 6,   # dark water blue
    (0x63, 0x9B, 0xFF): 7,   # water blue

    # Reds
    (0x90, 0x31, 0x22): 8,   # dark red
    (0xE6, 0x4E, 0x35): 9,   # red

    # Oranges
    (0xB0, 0x4B, 0x05): 10,  # dark orange
    (0xED, 0x79, 0x29): 11,  # orange

    # Brown / yellow
    (0x60, 0x36, 0x1D): 12,  # dark brown
    (0xFD, 0xC4, 0x43): 13,  # yellow
    (0xFB, 0xCA, 0x43): 13,  # asset yellow variant

    # Greens
    (0x32, 0x8C, 0x25): 14,  # dark green
    (0x5D, 0xE3, 0x4A): 15,  # green
}


def load_map() -> dict:
    """Load the exported Tiled JSON map."""
    if not MAP_JSON.exists():
        raise FileNotFoundError(f"Map file not found: {MAP_JSON}")

    return json.loads(MAP_JSON.read_text(encoding="utf-8"))


def colour_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    """Return squared RGB distance between two colours."""
    return sum((a[i] - b[i]) ** 2 for i in range(3))


def pixel_to_palette(pixel: tuple[int, int, int, int]) -> int:
    """Convert one RGBA pixel to a fixed engine palette index."""
    red, green, blue, alpha = pixel

    if alpha < 128:
        return 0

    rgb = (red, green, blue)

    if rgb in EXACT_COLOUR_MAP:
        return EXACT_COLOUR_MAP[rgb]

    print(f"Warning: unknown colour {rgb}; mapping to black.")
    return 0

def load_tilesets(map_data: dict) -> list[dict]:
    """Load tileset metadata from the Tiled map."""
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
                "image": TILESET_DIR / image_name,
                "tiles": tileset.get("tiles", []),
            }
        )

    return sorted(tilesets, key=lambda item: item["firstgid"])


def load_tileset_images(tilesets: list[dict]) -> dict[str, Image.Image]:
    """Load all tileset PNGs referenced by the Tiled map."""
    images: dict[str, Image.Image] = {}

    for tileset in tilesets:
        image_path = tileset["image"]

        if not image_path.exists():
            raise FileNotFoundError(f"Missing tileset image: {image_path}")

        images[tileset["name"]] = Image.open(image_path).convert("RGBA")

    return images


def find_tileset(gid: int, tilesets: list[dict]) -> dict:
    """Find which tileset owns a global tile ID."""
    selected = None

    for tileset in tilesets:
        if gid >= tileset["firstgid"]:
            selected = tileset
        else:
            break

    if selected is None:
        raise ValueError(f"No tileset found for GID {gid}")

    return selected


def extract_tile(
    gid: int,
    tilesets: list[dict],
    images: dict[str, Image.Image],
) -> dict:
    """Extract one tile/sprite from its tileset image."""
    tileset = find_tileset(gid, tilesets)

    local_id = gid - tileset["firstgid"]
    tile_width = tileset["tilewidth"]
    tile_height = tileset["tileheight"]
    columns = tileset["columns"]

    image = images[tileset["name"]]

    x0 = (local_id % columns) * tile_width
    y0 = (local_id // columns) * tile_height

    if x0 + tile_width > image.width or y0 + tile_height > image.height:
        raise ValueError(
            f"GID {gid} is outside image bounds for tileset '{tileset['name']}'"
        )

    pixels: list[int] = []

    for y in range(tile_height):
        for x in range(tile_width):
            pixels.append(pixel_to_palette(image.getpixel((x0 + x, y0 + y))))

    return {
        "pixels": pixels,
        "width": tile_width,
        "height": tile_height,
    }


def collect_layer_gids(map_data: dict) -> set[int]:
    """Collect all tile GIDs used directly by tile layers."""
    gids: set[int] = set()

    for layer in map_data["layers"]:
        if layer.get("type") != "tilelayer":
            continue

        for gid in layer.get("data", []):
            if gid != EMPTY_TILE_ID:
                gids.add(gid)

    return gids


def collect_object_sprite_gids(map_data: dict) -> set[int]:
    """Collect sprite GIDs referenced by object layer properties."""
    gids: set[int] = set()

    sprite_properties = {
        "sprite_gid",
        "closed_gid",
        "opening_gid",
        "open_gid",
    }

    for layer in map_data["layers"]:
        if layer.get("type") != "objectgroup":
            continue

        for obj in layer.get("objects", []):
            for prop in obj.get("properties", []):
                property_name = prop.get("name", "").strip()

                if property_name not in sprite_properties:
                    continue

                gid = int(prop.get("value", 0))

                if gid != EMPTY_TILE_ID:
                    gids.add(gid)

    return gids


def collect_animations(map_data: dict) -> dict[int, list[int]]:
    """Collect Tiled tile animations as {base_gid: [frame_gids...]}."""
    animations: dict[int, list[int]] = {}

    for tileset in map_data["tilesets"]:
        firstgid = tileset["firstgid"]

        for tile in tileset.get("tiles", []):
            if "animation" not in tile:
                continue

            base_gid = firstgid + tile["id"]
            frame_gids = [
                firstgid + frame["tileid"] for frame in tile["animation"]
            ]

            animations[base_gid] = frame_gids

    return animations


def collect_export_gids(map_data: dict, animations: dict[int, list[int]]) -> list[int]:
    """Collect every GID that must be exported to C."""
    gids = collect_layer_gids(map_data)
    gids.update(collect_object_sprite_gids(map_data))

    # If an animated tile is used, all of its animation frames must also be exported.
    for base_gid, frame_gids in animations.items():
        if base_gid in gids:
            gids.update(frame_gids)

    return sorted(gids)


def format_pixels(tile: dict) -> str:
    """Format one sprite's pixels as readable C array rows."""
    rows: list[str] = []
    pixels = tile["pixels"]
    width = tile["width"]

    for index in range(0, len(pixels), width):
        row = pixels[index : index + width]
        rows.append("  " + ", ".join(map(str, row)) + ",")

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
        "uint16_t Game1_Tiles_ResolveAnimation(uint16_t tiled_id,\n"
        "                                      uint32_t frame_counter);\n\n"
        f"#endif // {guard}\n"
    )


def generate_source(
    tile_ids: list[int],
    tile_data: dict[int, dict],
    animations: dict[int, list[int]],
) -> str:
    parts: list[str] = [f'#include "{MAP_NAME}.h"\n\n']

    for index, gid in enumerate(tile_ids):
        tile = tile_data[gid]

        parts.append(f"static const uint8_t tile_{index}[] = {{\n")
        parts.append(format_pixels(tile))
        parts.append("\n};\n\n")

        parts.append(
            f"static const Game1_TileSprite sprite_{index} = "
            f"{{ tile_{index}, {tile['width']}, {tile['height']} }};\n\n"
        )

    parts.append(
        "typedef struct {\n"
        "  uint16_t id;\n"
        "  const Game1_TileSprite *sprite;\n"
        "} TileEntry;\n\n"
    )

    parts.append(f"static const TileEntry lookup[{MAP_NAME.upper()}_COUNT] = {{\n")

    for index, gid in enumerate(tile_ids):
        parts.append(f"  {{ {gid}, &sprite_{index} }},\n")

    parts.append("};\n\n")

    parts.append(
        "const Game1_TileSprite *Game1_Tiles_Find(uint16_t tiled_id) {\n"
        f"  for (uint16_t i = 0; i < {MAP_NAME.upper()}_COUNT; i++) {{\n"
        "    if (lookup[i].id == tiled_id) {\n"
        "      return lookup[i].sprite;\n"
        "    }\n"
        "  }\n\n"
        "  return 0;\n"
        "}\n\n"
    )

    for index, (_, frame_gids) in enumerate(animations.items()):
        frames = ", ".join(map(str, frame_gids))
        parts.append(
            f"static const uint16_t animation_{index}_frames[] = "
            f"{{ {frames} }};\n"
        )

    parts.append(
        "\ntypedef struct {\n"
        "  uint16_t id;\n"
        "  uint8_t frame_count;\n"
        "  const uint16_t *frames;\n"
        "} AnimationEntry;\n\n"
    )

    parts.append(
        f"static const AnimationEntry animations"
        f"[{MAP_NAME.upper()}_ANIMATION_COUNT] = {{\n"
    )

    for index, (base_gid, frame_gids) in enumerate(animations.items()):
        parts.append(
            f"  {{ {base_gid}, {len(frame_gids)}, animation_{index}_frames }},\n"
        )

    parts.append("};\n\n")

    parts.append(
        "uint16_t Game1_Tiles_ResolveAnimation(uint16_t tiled_id,\n"
        "                                      uint32_t frame_counter) {\n"
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
    map_data = load_map()

    tilesets = load_tilesets(map_data)
    images = load_tileset_images(tilesets)

    animations = collect_animations(map_data)
    tile_ids = collect_export_gids(map_data, animations)

    tile_data = {
        gid: extract_tile(gid, tilesets, images)
        for gid in tile_ids
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    header_path = OUTPUT_DIR / f"{MAP_NAME}.h"
    source_path = OUTPUT_DIR / f"{MAP_NAME}.c"

    header_path.write_text(
        generate_header(len(tile_ids), len(animations)),
        encoding="utf-8",
    )

    source_path.write_text(
        generate_source(tile_ids, tile_data, animations),
        encoding="utf-8",
    )

    print(f"Success! Exported {len(tile_ids)} sprites.")
    print(f"Animations exported: {len(animations)}")
    print(f"Wrote {header_path}")
    print(f"Wrote {source_path}")


if __name__ == "__main__":
    main()