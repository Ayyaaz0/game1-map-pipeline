from pathlib import Path
import csv

INPUT_CSV = Path("assets/maps/room0.csv")
OUTPUT_DIR = Path("build")
MAP_NAME = "room0"


def load_csv(path):
    rows = []

    with open(path, newline="") as f:
        reader = csv.reader(f)

        for row in reader:
            cleaned_row = []
            for value in row:
                value = value.strip()

                if value == "":
                    continue

                tile_id = int(value)

                # Tiled uses -1 for empty cells in some exports.
                # Store empty cells as 0 for C/STM32.
                if tile_id == -1:
                    tile_id = 0

                cleaned_row.append(tile_id)

            if cleaned_row:
                rows.append(cleaned_row)

    return rows


def flatten(rows):
    return [tile for row in rows for tile in row]


def write_header(width, height):
    header_path = OUTPUT_DIR / f"{MAP_NAME}.h"

    header_path.write_text(f"""#ifndef ROOM0_H
#define ROOM0_H

#include <stdint.h>

#define ROOM0_WIDTH {width}
#define ROOM0_HEIGHT {height}

extern const uint16_t room0_data[ROOM0_WIDTH * ROOM0_HEIGHT];

#endif
""")


def write_source(tile_data):
    source_path = OUTPUT_DIR / f"{MAP_NAME}.c"

    lines = []
    for i in range(0, len(tile_data), 16):
        chunk = tile_data[i:i + 16]
        lines.append("    " + ", ".join(str(v) for v in chunk) + ",")

    source_path.write_text(f"""#include "room0.h"

const uint16_t room0_data[ROOM0_WIDTH * ROOM0_HEIGHT] = {{
{chr(10).join(lines)}
}};
""")


def main():
    rows = load_csv(INPUT_CSV)

    height = len(rows)
    width = len(rows[0])

    for row in rows:
        if len(row) != width:
            raise ValueError("CSV rows are not all the same width.")

    tile_data = flatten(rows)

    OUTPUT_DIR.mkdir(exist_ok=True)

    write_header(width, height)
    write_source(tile_data)

    print(f"Converted {INPUT_CSV}")
    print(f"Map size: {width} x {height}")
    print(f"Tiles: {len(tile_data)}")
    print(f"Wrote build/{MAP_NAME}.c")
    print(f"Wrote build/{MAP_NAME}.h")


if __name__ == "__main__":
    main()