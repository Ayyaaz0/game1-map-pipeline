from pathlib import Path
import csv

# --- Configuration ---
MAP_NAME = "room0"
WIDTH = 30
HEIGHT = 30
EMPTY_TILE_ID = -1
BACKGROUND_TILE_ID = 0

# --- Paths ---
INPUT_CSV = Path("assets/maps/room0.csv")
OUTPUT_DIR = Path("build")
HEADER_FILE = OUTPUT_DIR / f"{MAP_NAME}.h"
SOURCE_FILE = OUTPUT_DIR / f"{MAP_NAME}.c"


def load_and_convert_csv(path: Path) -> list[int]:
    """Read CSV, convert empty tiles, and return a flat list of tile IDs."""
    flat_data: list[int] = []

    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.reader(file)

        for row_index, row in enumerate(reader):
            cleaned_row: list[int] = []

            for value in row:
                value = value.strip()

                if not value:
                    continue

                tile_id = int(value)
                cleaned_row.append(
                    BACKGROUND_TILE_ID if tile_id == EMPTY_TILE_ID else tile_id
                )

            if not cleaned_row:
                continue

            if len(cleaned_row) != WIDTH:
                raise ValueError(
                    f"Row {row_index} has {len(cleaned_row)} tiles; expected {WIDTH}."
                )

            flat_data.extend(cleaned_row)

    expected_tiles = WIDTH * HEIGHT

    if len(flat_data) != expected_tiles:
        actual_rows = len(flat_data) // WIDTH
        raise ValueError(
            f"Map height mismatch: got {actual_rows} rows; expected {HEIGHT}."
        )

    return flat_data


def generate_header_content() -> str:
    """Generate the C header file content."""
    guard = f"{MAP_NAME.upper()}_H"
    width_macro = f"{MAP_NAME.upper()}_WIDTH"
    height_macro = f"{MAP_NAME.upper()}_HEIGHT"

    return (
        f"#ifndef {guard}\n"
        f"#define {guard}\n\n"
        f"#include <stdint.h>\n\n"
        f"#define {width_macro} {WIDTH}\n"
        f"#define {height_macro} {HEIGHT}\n\n"
        f"extern const uint16_t {MAP_NAME}_data[{width_macro} * {height_macro}];\n\n"
        f"#endif // {guard}\n"
    )


def generate_source_content(tile_data: list[int]) -> str:
    """Generate the C source file content with one map row per line."""
    width_macro = f"{MAP_NAME.upper()}_WIDTH"
    height_macro = f"{MAP_NAME.upper()}_HEIGHT"

    formatted_rows: list[str] = []

    for index in range(0, len(tile_data), WIDTH):
        row_chunk = tile_data[index:index + WIDTH]
        row_text = ", ".join(map(str, row_chunk))
        formatted_rows.append(f"    {row_text},")

    rows_block = "\n".join(formatted_rows)

    return (
        f'#include "{MAP_NAME}.h"\n\n'
        f"const uint16_t {MAP_NAME}_data[{width_macro} * {height_macro}] = {{\n"
        f"{rows_block}\n"
        f"}};\n"
    )


def main() -> None:
    try:
        print(f"--- Processing {INPUT_CSV.name} ---")

        tile_data = load_and_convert_csv(INPUT_CSV)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        HEADER_FILE.write_text(generate_header_content(), encoding="utf-8")
        SOURCE_FILE.write_text(generate_source_content(tile_data), encoding="utf-8")

        print("Success!")
        print(f"Dimensions: {WIDTH}x{HEIGHT} ({len(tile_data)} tiles)")
        print(f"Output: {OUTPUT_DIR.resolve()}")

    except FileNotFoundError:
        print(f"Error: could not find {INPUT_CSV}.")
    except ValueError as error:
        print(f"Data error: {error}")
    except Exception as error:
        print(f"Unexpected error: {error}")


if __name__ == "__main__":
    main()