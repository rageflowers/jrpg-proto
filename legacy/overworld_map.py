# overworld_map.py

TILE_SIZE = 32

MAP_WIDTH_TILES = 32   # 1024 px
MAP_HEIGHT_TILES = 24  # 768 px

# ---- Tile IDs ----
OCEAN    = 0
PLAINS   = 1
FOREST   = 2
MOUNTAIN = 3
CHASM    = 4
DESERT   = 5
RUINS    = 6
RIVER    = 7
ROAD     = 8
CITY     = 9   # tiny city marker (can be drawn as a special tile/icon)


def generate_overworld_map():
    """
    Build a 32x24 tile grid that roughly matches your hand-drawn continent:
    - Mountains + forest belt in the north (Velastra & Aurethil)
    - Plains in the middle
    - East–west chasm starting from the east, 2/3 across
    - Western land bridge to the south
    - Desert + desolate plateau in the south
    - Old Dias Ruins in center-south
    - Vael'aras ruins in far south-east
    """
    # Start with everything as PLAINS
    grid = [[PLAINS for _ in range(MAP_WIDTH_TILES)]
            for _ in range(MAP_HEIGHT_TILES)]

    # --- OCEAN RIM (optional, just to frame the map) ---
    for y in range(MAP_HEIGHT_TILES):
        for x in range(MAP_WIDTH_TILES):
            if x == 0 or x == MAP_WIDTH_TILES - 1 or y == 0 or y == MAP_HEIGHT_TILES - 1:
                grid[y][x] = OCEAN

    # --- NORTHERN MOUNTAINS (row 1-3 roughly) ---
    for y in range(1, 4):
        for x in range(2, MAP_WIDTH_TILES - 2):
            grid[y][x] = MOUNTAIN

    # Extra-tall mountains in the northeast for Velastra
    for y in range(1, 5):
        for x in range(MAP_WIDTH_TILES - 8, MAP_WIDTH_TILES - 2):
            grid[y][x] = MOUNTAIN

    # --- NORTHERN FOREST BELT (below mountains, rows 4-6) ---
    for y in range(4, 7):
        for x in range(2, MAP_WIDTH_TILES - 2):
            if grid[y][x] != OCEAN:
                grid[y][x] = FOREST

    # --- RIVER (from NE mountains down & west) ---
    # Start near Velastra mountains and snake southwest-ish
    river_path = [
        (MAP_WIDTH_TILES - 6, 3),
        (MAP_WIDTH_TILES - 7, 4),
        (MAP_WIDTH_TILES - 8, 5),
        (MAP_WIDTH_TILES - 9, 6),
        (MAP_WIDTH_TILES - 10, 7),
        (MAP_WIDTH_TILES - 11, 8),
        (MAP_WIDTH_TILES - 12, 9),
    ]
    for (rx, ry) in river_path:
        if 0 <= rx < MAP_WIDTH_TILES and 0 <= ry < MAP_HEIGHT_TILES:
            grid[ry][rx] = RIVER

    # --- CITIES (tiny markers) ---
    # Aurethil: northwest forest, near coast & cliffs
    aurethil_x, aurethil_y = 5, 5
    grid[aurethil_y][aurethil_x] = CITY

    # Velastra: northeast forest, near high mountains and river source
    velastra_x, velastra_y = MAP_WIDTH_TILES - 6, 4
    grid[velastra_y][velastra_x] = CITY

    # --- ROAD: Velastra -> along river -> split to Aurethil ---
    # Simple approximation along forest & plains
    # From Velastra down and left toward the river path, then westish.
    road_coords = [
        (velastra_x, velastra_y + 1),
        (velastra_x - 1, velastra_y + 2),
        (velastra_x - 2, velastra_y + 3),
        (velastra_x - 3, velastra_y + 4),
        (velastra_x - 4, velastra_y + 5),
        (velastra_x - 5, velastra_y + 5),  # getting closer to Aurethil
        (velastra_x - 6, velastra_y + 5),
        (aurethil_x + 1, aurethil_y + 1),
        (aurethil_x, aurethil_y + 1),
    ]
    for (tx, ty) in road_coords:
        if 0 <= tx < MAP_WIDTH_TILES and 0 <= ty < MAP_HEIGHT_TILES:
            # Don't overwrite ocean/chasm, but overwrite forest/plains/desert
            if grid[ty][tx] not in (OCEAN, CHASM):
                grid[ty][tx] = ROAD

    # --- CENTRAL PLAINS (middle rows 7-10) ---
    for y in range(7, 11):
        for x in range(2, MAP_WIDTH_TILES - 2):
            if grid[y][x] not in (OCEAN, RIVER, ROAD):
                grid[y][x] = PLAINS

    # --- GREAT CHASM (east–west, 2/3 across) ---
    chasm_y = 11
    for x in range(8, MAP_WIDTH_TILES - 2):  # starts roughly under east, stops before west edge
        grid[chasm_y][x] = CHASM

    # --- DESERT & PLATEAU SOUTH OF THE CHASM ---
    # rows 12-16 desert, 17-20 more desolate plateau
    for y in range(12, 17):
        for x in range(2, MAP_WIDTH_TILES - 2):
            if grid[y][x] != OCEAN:
                grid[y][x] = DESERT

    for y in range(17, 21):
        for x in range(2, MAP_WIDTH_TILES - 2):
            if grid[y][x] != OCEAN:
                # could still be DESERT, but visually maybe a different palette in tileset
                grid[y][x] = DESERT

    # --- OLD DIAS RUINS (center-south, just below chasm) ---
    dias_x, dias_y = MAP_WIDTH_TILES // 2, 14
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            gx = dias_x + dx
            gy = dias_y + dy
            if 0 <= gx < MAP_WIDTH_TILES and 0 <= gy < MAP_HEIGHT_TILES:
                grid[gy][gx] = RUINS

    # --- VAEL'ARAS RUINS (far south-east) ---
    base_x, base_y = MAP_WIDTH_TILES - 7, MAP_HEIGHT_TILES - 6
    for dy in range(0, 3):
        for dx in range(0, 4):
            gx = base_x + dx
            gy = base_y + dy
            if 0 <= gx < MAP_WIDTH_TILES and 0 <= gy < MAP_HEIGHT_TILES:
                grid[gy][gx] = RUINS

    return grid


TILEMAP = generate_overworld_map()
