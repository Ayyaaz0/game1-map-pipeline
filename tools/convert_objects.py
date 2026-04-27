from pathlib import Path
import json

# --- CONFIG ---
MAP_NAME = "room0"
LAYER_NAME = "Entities"

MAP_JSON = Path("assets/maps/room0.tmj")
OUTPUT_DIR = Path("build")

HEADER_FILE = OUTPUT_DIR / f"{MAP_NAME}_entities.h"
SOURCE_FILE = OUTPUT_DIR / f"{MAP_NAME}_entities.c"


def load_map_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def find_object_layer(map_data: dict) -> dict:
    for layer in map_data.get("layers", []):
        if layer.get("name") == LAYER_NAME and layer.get("type") == "objectgroup":
            return layer
    raise ValueError(f"Layer '{LAYER_NAME}' not found")


def get_property(obj: dict, name: str, default=0):
    for prop in obj.get("properties", []):
        if prop["name"].strip() == name:
            return prop["value"]
    return default


def parse_objects(layer: dict):
    parsed = []

    for obj in layer.get("objects", []):
        obj_type = get_property(obj, "type", "")

        parsed.append({
            "type": obj_type,
            "x": int(obj["x"]),
            "y": int(obj["y"]),
            "w": int(obj["width"]),
            "h": int(obj["height"]),
            "key_id": int(get_property(obj, "key_id", 0)),
            "locked": int(get_property(obj, "locked", False)),
        })

    return parsed


def generate_header():
    guard = f"{MAP_NAME.upper()}_ENTITIES_H"

    return f"""#ifndef {guard}
#define {guard}

#include <stdint.h>

typedef enum {{
  ENTITY_SPAWN,
  ENTITY_KEY,
  ENTITY_DOOR
}} Game1_EntityType;

typedef struct {{
  Game1_EntityType type;
  int16_t x;
  int16_t y;
  uint8_t w;
  uint8_t h;
  uint8_t key_id;
  uint8_t locked;
}} Game1_Entity;

extern const Game1_Entity {MAP_NAME}_entities[];
extern const uint16_t {MAP_NAME}_entity_count;

#endif
"""


def map_type(type_str: str) -> str:
    if type_str == "door":
        return "ENTITY_DOOR"
    if type_str == "key":
        return "ENTITY_KEY"
    if type_str == "spawn":
        return "ENTITY_SPAWN"
    return "ENTITY_SPAWN"


def generate_source(objects):
    lines = []

    lines.append(f'#include "{MAP_NAME}_entities.h"\n\n')

    lines.append(f"const Game1_Entity {MAP_NAME}_entities[] = {{\n")

    for obj in objects:
        enum_type = map_type(obj["type"])

        lines.append(
            f"  {{ {enum_type}, {obj['x']}, {obj['y']}, {obj['w']}, {obj['h']}, {obj['key_id']}, {obj['locked']} }},\n"
        )

    lines.append("};\n\n")

    lines.append(f"const uint16_t {MAP_NAME}_entity_count = {len(objects)};\n")

    return "".join(lines)


def main():
    data = load_map_json(MAP_JSON)
    layer = find_object_layer(data)
    objects = parse_objects(layer)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    HEADER_FILE.write_text(generate_header(), encoding="utf-8")
    SOURCE_FILE.write_text(generate_source(objects), encoding="utf-8")

    print(f"Exported {len(objects)} objects")


if __name__ == "__main__":
    main()