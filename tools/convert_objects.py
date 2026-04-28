from pathlib import Path
import json

MAP_NAME = "room0"
LAYER_NAME = "Entities"

MAP_JSON = Path("assets/maps/room0.tmj")
OUTPUT_DIR = Path("build")

HEADER_FILE = OUTPUT_DIR / f"{MAP_NAME}_entities.h"
SOURCE_FILE = OUTPUT_DIR / f"{MAP_NAME}_entities.c"


def load_map_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Map file not found: {path}")

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def find_object_layer(map_data: dict) -> dict:
    for layer in map_data.get("layers", []):
        if layer.get("name") == LAYER_NAME and layer.get("type") == "objectgroup":
            return layer

    raise ValueError(f"Object layer '{LAYER_NAME}' not found.")


def get_property(obj: dict, name: str, default=0):
    for prop in obj.get("properties", []):
        if prop.get("name", "").strip() == name:
            return prop.get("value", default)

    return default


def map_entity_type(type_name: str) -> str:
    type_name = type_name.strip()

    if type_name == "door":
        return "ENTITY_DOOR"

    if type_name == "key":
        return "ENTITY_KEY"

    if type_name == "spawn":
        return "ENTITY_SPAWN"

    return "ENTITY_UNKNOWN"


def parse_objects(layer: dict) -> list[dict]:
    entities: list[dict] = []

    for obj in layer.get("objects", []):
        entity_type = str(get_property(obj, "type", "")).strip()

        if not entity_type:
            continue

        entities.append(
            {
                "type": entity_type,
                "x": int(obj.get("x", 0)),
                "y": int(obj.get("y", 0)),
                "w": int(obj.get("width", 0)),
                "h": int(obj.get("height", 0)),
                "key_id": int(get_property(obj, "key_id", 0)),
                "locked": int(bool(get_property(obj, "locked", False))),
                "sprite_gid": int(get_property(obj, "sprite_gid", 0)),
                "closed_gid": int(get_property(obj, "closed_gid", 0)),
                "opening_gid": int(get_property(obj, "opening_gid", 0)),
                "open_gid": int(get_property(obj, "open_gid", 0)),
            }
        )

    return entities


def generate_header(entity_count: int) -> str:
    guard = f"{MAP_NAME.upper()}_ENTITIES_H"

    return (
        f"#ifndef {guard}\n"
        f"#define {guard}\n\n"
        f"#include <stdint.h>\n\n"
        f"#define {MAP_NAME.upper()}_ENTITY_COUNT {entity_count}\n\n"
        "typedef enum {\n"
        "  ENTITY_UNKNOWN,\n"
        "  ENTITY_SPAWN,\n"
        "  ENTITY_KEY,\n"
        "  ENTITY_DOOR\n"
        "} Game1_EntityType;\n\n"
        "typedef struct {\n"
        "  Game1_EntityType type;\n"
        "  int16_t x;\n"
        "  int16_t y;\n"
        "  uint8_t w;\n"
        "  uint8_t h;\n"
        "  uint8_t key_id;\n"
        "  uint8_t locked;\n"
        "  uint16_t sprite_gid;\n"
        "  uint16_t closed_gid;\n"
        "  uint16_t opening_gid;\n"
        "  uint16_t open_gid;\n"
        "} Game1_Entity;\n\n"
        f"extern const Game1_Entity {MAP_NAME}_entities[];\n"
        f"extern const uint16_t {MAP_NAME}_entity_count;\n\n"
        f"#endif // {guard}\n"
    )


def generate_source(entities: list[dict]) -> str:
    lines: list[str] = [f'#include "{MAP_NAME}_entities.h"\n\n']

    lines.append(f"const Game1_Entity {MAP_NAME}_entities[] = {{\n")

    for entity in entities:
        lines.append(
            "  { "
            f"{map_entity_type(entity['type'])}, "
            f"{entity['x']}, "
            f"{entity['y']}, "
            f"{entity['w']}, "
            f"{entity['h']}, "
            f"{entity['key_id']}, "
            f"{entity['locked']}, "
            f"{entity['sprite_gid']}, "
            f"{entity['closed_gid']}, "
            f"{entity['opening_gid']}, "
            f"{entity['open_gid']} "
            "},\n"
        )

    lines.append("};\n\n")
    lines.append(f"const uint16_t {MAP_NAME}_entity_count = {len(entities)};\n")

    return "".join(lines)


def main() -> None:
    try:
        map_data = load_map_json(MAP_JSON)
        object_layer = find_object_layer(map_data)
        entities = parse_objects(object_layer)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        HEADER_FILE.write_text(generate_header(len(entities)), encoding="utf-8")
        SOURCE_FILE.write_text(generate_source(entities), encoding="utf-8")

        print(f"Success! Exported {len(entities)} entities.")
        print(f"Wrote {HEADER_FILE}")
        print(f"Wrote {SOURCE_FILE}")

    except Exception as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()