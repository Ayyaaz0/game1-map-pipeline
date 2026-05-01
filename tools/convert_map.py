from pathlib import Path
import json

MAP_NAME = "room1"
LAYER_NAME = "MetaTile"

MAP_JSON = Path("assets/maps/room1.tmj")
OUTPUT_DIR = Path("build")
HEADER_FILE = OUTPUT_DIR / f"{MAP_NAME}.h"
SOURCE_FILE = OUTPUT_DIR / f"{MAP_NAME}.c"


def load_map_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Map file not found: {path}")

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def find_tile_layer(map_data: dict) -> dict:
    for layer in map_data.get("layers", []):
        if layer.get("name") == LAYER_NAME and layer.get("type") == "tilelayer":
            return layer

    raise ValueError(f"Tile layer '{LAYER_NAME}' not found.")


def load_tile_data(map_data: dict) -> tuple[list[int], int, int]:
    layer = find_tile_layer(map_data)

    width = layer["width"]
    height = layer["height"]
    tile_data = layer["data"]

    if len(tile_data) != width * height:
        raise ValueError(
            f"Layer has {len(tile_data)} tiles; expected {width * height}."
        )

    return tile_data, width, height


def generate_header_content(width: int, height: int) -> str:
    guard = f"{MAP_NAME.upper()}_H"
    width_macro = f"{MAP_NAME.upper()}_WIDTH"
    height_macro = f"{MAP_NAME.upper()}_HEIGHT"

    return (
        f"#ifndef {guard}\n"
        f"#define {guard}\n\n"
        f"#include <stdint.h>\n\n"
        f"#define {width_macro} {width}\n"
        f"#define {height_macro} {height}\n\n"
        f"extern const uint16_t {MAP_NAME}_data[{width_macro} * {height_macro}];\n\n"
        f"#endif // {guard}\n"
    )


def generate_source_content(tile_data: list[int], width: int) -> str:
    width_macro = f"{MAP_NAME.upper()}_WIDTH"
    height_macro = f"{MAP_NAME.upper()}_HEIGHT"

    rows = []

    for index in range(0, len(tile_data), width):
        row = tile_data[index:index + width]
        rows.append("    " + ", ".join(map(str, row)) + ",")

    rows_block = "\n".join(rows)

    return (
        f'#include "{MAP_NAME}.h"\n\n'
        f"const uint16_t {MAP_NAME}_data[{width_macro} * {height_macro}] = {{\n"
        f"{rows_block}\n"
        f"}};\n"
    )


def main() -> None:
    try:
        print(f"--- Processing {MAP_JSON.name} / layer '{LAYER_NAME}' ---")

        map_data = load_map_json(MAP_JSON)
        tile_data, width, height = load_tile_data(map_data)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        HEADER_FILE.write_text(generate_header_content(width, height), encoding="utf-8")
        SOURCE_FILE.write_text(generate_source_content(tile_data, width), encoding="utf-8")

        print("Success!")
        print(f"Dimensions: {width}x{height} ({len(tile_data)} tiles)")
        print(f"Output: {OUTPUT_DIR.resolve()}")

    except Exception as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()