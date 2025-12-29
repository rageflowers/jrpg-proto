"""
Map registry and layout data for the overworld.

Tile IDs must match overworld.py:
    0 = GRASS
    1 = WATER
    2 = MOUNTAIN
"""

# Local tile IDs (must stay in sync with overworld.py)
GRASS = 0
WATER = 1
MOUNTAIN = 2
DIRT = 3
FOREST = 4
ROCKY = 5
STONE = 6


def load_placeholder(width, height, fill=GRASS):
    """Temporary helper until real maps are built."""
    return [[fill for _ in range(width)] for _ in range(height)]


def make_velastra_valley():
    """
    30x20 Velastra test layout:

      - Mostly grass with some rocky flavor
      - WEST edge (x == 0) is ALL GRASS and easy to reach
      - This is deliberately simple just to guarantee transitions
    """
    width, height = 30, 20
    grid = [[GRASS for _ in range(width)] for _ in range(height)]

    # A little rocky flavor in the middle
    mid_y = height // 2
    for x in range(10, 20):
        grid[mid_y - 1][x] = ROCKY
        grid[mid_y + 1][x] = ROCKY

    # East side “feel” of cliffs (still blocking)
    for y in range(2, height - 2):
        grid[y][width - 3] = MOUNTAIN
        grid[y][width - 2] = MOUNTAIN
        grid[y][width - 1] = MOUNTAIN

    # WEST edge: all GRASS, guaranteed walkable
    for y in range(height):
        grid[y][0] = GRASS

    return grid


def make_aurethil_road_1():
    """
    40x20 forested merchant road:

      - Mountains tapering off on the EAST side (back toward Velastra)
      - Dense forest north/south of the road
      - Dirt road running east<->west
      - River on the SOUTH side of the road, starting from the eastern mountains
        and slowly peeling away as we go west toward the plains.
    """
    width, height = 40, 20
    grid = [[GRASS for _ in range(width)] for _ in range(height)]

    mid_y = height // 2

    # --- Eastern mountains (Velastra side) ---
    for y in range(2, height - 2):
        for x in range(width - 5, width):
            grid[y][x] = MOUNTAIN

    # --- Forest bands north/south of the road ---
    # (Using MOUNTAIN as blocking until we add a FOREST tile ID)
    forest_top_start = 2
    forest_top_end = mid_y - 2
    forest_bot_start = mid_y + 3
    forest_bot_end = height - 2

    for y in range(forest_top_start, forest_top_end):
        for x in range(2, width - 5):
            grid[y][x] = MOUNTAIN  # placeholder "thick forest"

    for y in range(forest_bot_start, forest_bot_end):
        for x in range(2, width - 5):
            grid[y][x] = MOUNTAIN  # placeholder "thick forest"

    # --- Dirt road through the middle ---
    road_y = mid_y
    for x in range(2, width - 2):
        grid[road_y][x] = DIRT
        if 0 <= road_y + 1 < height:
            grid[road_y + 1][x] = DIRT

    # --- River south of the road ---
    # Starts near the eastern mountains, close to the road,
    # then drifts further south as we approach the western plains.
    river_base_y = road_y + 3
    for x in range(6, width - 6):
        if x < width // 3:
            ry = river_base_y       # closer to the road (east side)
        elif x < 2 * width // 3:
            ry = river_base_y + 1   # a bit further south
        else:
            ry = river_base_y + 2   # peels further away to the south-west

        if 0 <= ry < height:
            grid[ry][x] = WATER
            if ry + 1 < height:
                grid[ry + 1][x] = WATER  # thicker river band

    return grid

def make_aurethil_city_exterior():
    """
    50x30 map:

      - Open grass plains
      - Subtle, somewhat broken dirt path coming in from the EAST
        that becomes more defined near the city gate
      - City wall near the top with a central gate
      - A small continuation of the river at the far south that
        has drifted away from the road.
    """
    width, height = 50, 30
    grid = [[GRASS for _ in range(width)] for _ in range(height)]

    wall_y = 6

    # --- City wall across map ---
    for x in range(width):
        grid[wall_y][x] = MOUNTAIN

    # Gate opening
    gate_x_center = width // 2
    gate_half_width = 2
    for x in range(gate_x_center - gate_half_width,
                   gate_x_center + gate_half_width + 1):
        grid[wall_y][x] = GRASS

    # --- Fading road from east plains to gate ---
    # East side: faint, patchy dirt
    road_y = height - 6
    for x in range(width - 1, gate_x_center - 6, -1):
        if (x % 3) == 0:
            grid[road_y][x] = DIRT

    # Mid section: more regular
    for x in range(gate_x_center - 6, gate_x_center + 1):
        grid[road_y][x] = DIRT
        if road_y - 1 >= 0:
            grid[road_y - 1][x] = DIRT

    # Column up to the gate
    for y in range(road_y - 1, wall_y + 1, -1):
        grid[y][gate_x_center] = DIRT
        if gate_x_center - 1 >= 0:
            grid[y][gate_x_center - 1] = DIRT

    # --- River continuation at far south, drifting away ---
    river_y = height - 2
    for x in range(5, 20):
        grid[river_y][x] = WATER
        if river_y - 1 >= 0:
            grid[river_y - 1][x] = WATER

    return grid

def make_aurethil_city_gate():
    """
    50x30 Aurethil City - Gate District:

      - Stone courtyard inside the wall
      - Inner buildings on the north side
      - Road from the south gate up into the city
    """
    width, height = 50, 30
    grid = [[GRASS for _ in range(width)] for _ in range(height)]

    # Convert most of the central area to STONE courtyard
    for y in range(10, height - 2):
        for x in range(5, width - 5):
            grid[y][x] = STONE

    # Inner city wall at the top of the courtyard
    wall_y = 9
    for x in range(5, width - 5):
        grid[wall_y][x] = MOUNTAIN

    # Gaps in that inner wall for streets further into the city (later maps)
    center_x = width // 2
    for x in range(center_x - 2, center_x + 3):
        grid[wall_y][x] = STONE

    # Road from south edge up into courtyard
    road_x = center_x
    for y in range(height - 1, 10, -1):
        grid[y][road_x] = DIRT
        if road_x - 1 >= 0:
            grid[y][road_x - 1] = DIRT

    # A few stone buildings along the north side of the courtyard
    for x in range(8, 15):
        grid[11][x] = STONE
    for x in range(width - 16, width - 9):
        grid[11][x] = STONE

    return grid



OVERWORLD_REGIONS = {
    "velastra_valley": {
        "tile_grid": make_velastra_valley(),
        "region": "velastra",
        "start_tile": (22, 10),
        "connections": {
            "west": "aurethil_road_1",   # <-- important
        },
    },

    "aurethil_road_1": {
        "tile_grid": make_aurethil_road_1(),
        "region": "aurethil_road",
        "start_tile": (35, 10),
        "connections": {
            "east": "velastra_valley",
            "west": "aurethil_city_exterior",
        },
    },

    "aurethil_city_exterior": {
        "tile_grid": make_aurethil_city_exterior(),
        "region": "aurethil",
        "start_tile": (40, 25),
        "connections": {
            "east": "aurethil_road_1",
            "north": "aurethil_city_gate",
        },
    },

    "aurethil_city_gate": {
        "tile_grid": make_aurethil_city_gate(),
        "region": "aurethil",
        "start_tile": (25, 25),  # roughly center of lower courtyard
        "connections": {
            "south": "aurethil_city_exterior",
            # later: "north": "aurethil_market", etc.
        },
    },

}
