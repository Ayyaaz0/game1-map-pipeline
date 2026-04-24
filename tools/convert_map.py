from pathlib import Path
import csv

INPUT_CSV = Path("assets/maps/room0.csv")
OUTPUT_DIR = Path("build")

MAP_NAME = "room0"
C_ARRAY_NAME = "room0_data"
WIDTH = 30
HEIGHT = 30


def load_csv(path):
    rows = []

    with open(path, newline="") as file:
        reader = csv.reader(file)

        for row in reader:
            cleaned_row = []

            for value in row:
                value = value.strip()

                if value == "":
                    continue

                tile_id = int(value)

                # Tiled empty cell.
                # Store as 0 so it can mean "empty / black tile" in C.
                if tile_id == -1:
                    tile_id = 0

                cleaned_row.append(tile_id)

            if cleaned_row:
                rows.append(cleaned_row)

    return rows


def flatten(rows):
    return [tile for row in rows for tile in row]


def validate_map(rows):
    if len(rows) != HEIGHT:
        raise ValueError(f"Expected {HEIGHT} rows, got {len(rows)} rows.")

    for row_index, row in enumerate(rows):
        if len(row) != WIDTH:
            raise ValueError(
                f"Row {row_index} has {len(row)} tiles, expected {WIDTH}."
            )


def write_header():
    header_path = OUTPUT_DIR / f"{MAP_NAME}.h"

    include_guard = f"{MAP_NAME.upper()}_H"

    header_path.write_text(
        f"""#ifndef {include_guard}
#define {include_guard}

#include <stdint.h>

#define ROOM0_WIDTH {WIDTH}
#define ROOM0_HEIGHT {HEIGHT}

extern const uint16_t {C_ARRAY_NAME}[ROOM0_WIDTH * ROOM0_HEIGHT];

#endif
"""
    )


def write_source(tile_data):
    source_path = OUTPUT_DIR / f"{MAP_NAME}.c"

    lines = []
    # Use WIDTH (30) to determine how many tiles go on one line
    for i in range(0, len(tile_data), WIDTH):
        chunk = tile_data[i : i + WIDTH]
        # Join the numbers with a comma and space
        line_content = ", ".join(str(value) for value in chunk)
        lines.append(f"    {line_content},")

    source_path.write_text(
        f"""#include "{MAP_NAME}.h"

const uint16_t {C_ARRAY_NAME}[ROOM0_WIDTH * ROOM0_HEIGHT] = {{
{chr(10).join(lines)}
}};
"""
    )


def main():
    rows = load_csv(INPUT_CSV)
    validate_map(rows)

    tile_data = flatten(rows)

    expected_tiles = WIDTH * HEIGHT
    actual_tiles = len(tile_data)

    if actual_tiles != expected_tiles:
        raise ValueError(
            f"Expected {expected_tiles} tiles, got {actual_tiles} tiles."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    write_header()
    write_source(tile_data)

    print(f"Converted {INPUT_CSV}")
    print(f"Map size: {WIDTH} x {HEIGHT}")
    print(f"Tiles written: {actual_tiles}")
    print(f"Wrote {OUTPUT_DIR / (MAP_NAME + '.c')}")
    print(f"Wrote {OUTPUT_DIR / (MAP_NAME + '.h')}")


if __name__ == "__main__":
    main()