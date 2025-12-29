# overworld.py

import random
import pygame

from engine.battle.atmosphere import Atmosphere
from engine.battle.ambient_layer import AmbientLayer
from engine.core.time_manager import GameClock
from overworld.region_maps import OVERWORLD_REGIONS
from setia_sprite import Setia

# --- Core constants ---

TILE_SIZE = 32
PLAYER_SPEED = 150  # px/sec
DEBUG_OVERWORLD = False
ENCOUNTERS_ENABLED_GLOBAL = True


GRASS = 0
WATER = 1
MOUNTAIN = 2
DIRT = 3
FOREST = 4
ROCKY = 5
STONE = 6

TILE_COLORS = {
    GRASS: (34, 139, 34),
    WATER: (30, 144, 255),
    MOUNTAIN: (139, 137, 137),
    DIRT: (139, 69, 19),
    FOREST: (0, 100, 0),
    ROCKY: (160, 160, 160),
    STONE: (169, 169, 169),
}

# Movement speed modifiers per tile
TILE_SPEED_MODIFIERS = {
    GRASS: 1.0,
    DIRT: 1.0,     # road is full speed
    FOREST: 0.6,   # slower in trees
    ROCKY: 0.5,    # slower on rocky ground
    WATER: 0.0,    # shouldn't be walked on anyway (blocked)
    MOUNTAIN: 0.0, # hard wall
    STONE: 1.0,
}

# Tiles that block movement
BLOCKED_TILES = {WATER, MOUNTAIN}

# Tiles where random encounters are allowed
ENCOUNTER_TILES = {GRASS, DIRT, FOREST, ROCKY}

# Encounter tables per region
ENCOUNTER_TABLES = {
    "grasslands": [
        {"name": "Slime", "max_hp": 10, "attack": 3},
        {"name": "Wolf",  "max_hp": 16, "attack": 5},
        {"name": "Bandit","max_hp": 20, "attack": 6},
    ],
    # you can add: "desert": [...], "night_forest": [...], etc.
}

DEFAULT_REGION = "grasslands"

# Region zones in tile coordinates: ((x1, y1, x2, y2), "region_name")
# This is just a prototype partition of the example map.
REGION_ZONES = [
    ((0, 0, 7, 9), "grasslands"),      # left side
    ((8, 0, 13, 9), "night_forest"),   # middle strip
    ((14, 0, 19, 9), "desert"),        # right side
]

# --- Multi-map registry for Forge Vier ---

def load_placeholder(width, height, fill=GRASS):
    """Temporary helper until real maps are built."""
    return [[fill for _ in range(width)] for _ in range(height)]

def is_position_blocked(px, py, world_map):
    tile_x = int(px // TILE_SIZE)
    tile_y = int(py // TILE_SIZE)
    return world_map.is_blocked(tile_x, tile_y)


OVERWORLD_MAPS = {
    # ------------------------------------------------------
    # 1. Velastra Valley — Starting Zone
    # ------------------------------------------------------
    "velastra_valley": {
        "tile_grid": [
            # Simple 30x20 placeholder valley:
            # - grass open fields
            # - a water river vertical strip in the middle
            # - mountains surrounding edges
        ] or load_placeholder(30, 20),

        "region": "velastra",
        "start_pos": (15 * TILE_SIZE, 10 * TILE_SIZE),  # center of map
        "connections": {
            "east": "aurethil_road_1",
        },
    },

    # ------------------------------------------------------
    # 2. Aurethil Road I — Woodland Path
    # ------------------------------------------------------
    "aurethil_road_1": {
        "tile_grid": [
            # 40x20 placeholder:
            # Long horizontal road; grass everywhere for now
        ] or load_placeholder(40, 20),

        "region": "aurethil_road",
        "start_pos": (2 * TILE_SIZE, 10 * TILE_SIZE),  # spawn near west edge
        "connections": {
            "west": "velastra_valley",
            "east": "aurethil_city_exterior",
        },
    },

    # ------------------------------------------------------
    # 3. Aurethil City Exterior — Outer District & Main Gate
    # ------------------------------------------------------
    "aurethil_city_exterior": {
        "tile_grid": [
            # 50x30 placeholder:
            # Later will contain: big gate, trees, luminous stone
        ] or load_placeholder(50, 30),

        "region": "aurethil",
        "start_pos": (5 * TILE_SIZE, 25 * TILE_SIZE),  # lower-left district
        "connections": {
            "west": "aurethil_road_1",
            # eventually "north": "aurethil_city_inner"
        },
    },
}


# --- World map + entities ---

class WorldMap:
    def __init__(
        self,
        width: int,
        height: int,
        map_id: str = "start",
        router=None,
    ):
        self.width = width
        self.height = height
        self.map_id = map_id

        self.router = router

    def is_blocked(self, tile_x, tile_y):
        if tile_x < 0 or tile_y < 0 or tile_x >= self.width or tile_y >= self.height:
            return True
        return self.tiles[tile_y][tile_x] in BLOCKED_TILES

    def draw(self, surface, camera, screen_width, screen_height):
        start_x = camera.x // TILE_SIZE
        start_y = camera.y // TILE_SIZE

        tiles_x = screen_width // TILE_SIZE + 2
        tiles_y = screen_height // TILE_SIZE + 2

        for y in range(tiles_y):
            for x in range(tiles_x):
                map_x = start_x + x
                map_y = start_y + y

                if 0 <= map_x < self.width and 0 <= map_y < self.height:
                    tile_id = self.tiles[int(map_y)][int(map_x)]
                    color = TILE_COLORS.get(tile_id, (0, 0, 0))

                    world_px = map_x * TILE_SIZE
                    world_py = map_y * TILE_SIZE

                    screen_x = world_px - camera.x
                    screen_y = world_py - camera.y

                    pygame.draw.rect(
                        surface,
                        color,
                        (screen_x, screen_y, TILE_SIZE, TILE_SIZE),
                    )


class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 20
        self.height = 20

    @property
    def rect(self):
        return pygame.Rect(
            int(self.x - self.width / 2),
            int(self.y - self.height / 2),
            self.width,
            self.height,
        )

    def update(self, dt, world_map, keys):
        dx = 0
        dy = 0

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += 1

        if dx and dy:
            # normalize diagonal
            dx *= 0.7071
            dy *= 0.7071

        if dx == 0 and dy == 0:
            return False

        # First, compute a tentative position using base speed
        base_step = PLAYER_SPEED * dt
        temp_x = self.x + dx * base_step
        temp_y = self.y + dy * base_step

        # Look at the tile under the *feet* at that tentative position
        probe_x = temp_x
        probe_y = temp_y + self.height / 2 - 4

        tile_x = int(probe_x // TILE_SIZE)
        tile_y = int(probe_y // TILE_SIZE)

        # Default modifier is 1.0 if tile is out-of-bounds or unknown
        speed_modifier = 1.0
        if 0 <= tile_x < world_map.width and 0 <= tile_y < world_map.height:
            tile_id = world_map.tiles[tile_y][tile_x]
            speed_modifier = TILE_SPEED_MODIFIERS.get(tile_id, 1.0)

        # Now compute the final step with the terrain modifier
        step = PLAYER_SPEED * speed_modifier * dt
        new_x = self.x + dx * step
        new_y = self.y + dy * step

        # Recompute probe for collision
        probe_x = new_x
        probe_y = new_y + self.height / 2 - 4

        if not is_position_blocked(probe_x, probe_y, world_map):
            self.x = new_x
            self.y = new_y
            return True

        return False  # blocked / no move

    def draw(self, surface, camera):
        screen_rect = self.rect.move(-camera.x, -camera.y)
        pygame.draw.rect(surface, (255, 255, 0), screen_rect)


class Camera:
    def __init__(self, world_map, target, screen_width, screen_height):
        self.world_map = world_map
        self.target = target
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = 0
        self.y = 0

    def update(self):
        target_x = self.target.x - self.screen_width // 2
        target_y = self.target.y - self.screen_height // 2

        max_x = self.world_map.width * TILE_SIZE - self.screen_width
        max_y = self.world_map.height * TILE_SIZE - self.screen_height

        if max_x < 0:
            max_x = 0
        if max_y < 0:
            max_y = 0

        self.x = max(0, min(target_x, max_x))
        self.y = max(0, min(target_y, max_y))


# --- WorldMapScene: ties it all together ---

class WorldMapScene:
    """
    Overworld scene for JRPG-Proto.

    Exposes:
      - handle_event(event)
      - update(dt)
      - draw(surface)
      - pending_battle: dict when encounter triggers, else None
      - region: current region string (for battle backgrounds, encounter tables)
    """

    def __init__(self, screen_width, screen_height, map_id="velastra_valley", router=None):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.map_id = map_id

        self.router = router

        # Load map data from registry in region_maps.py
        data = OVERWORLD_REGIONS[map_id]
        tile_grid = data["tile_grid"]
        self.region = data["region"]

        # Build world map
        self.world_map = WorldMap(tile_grid)

        # Convert start_tile -> pixel coordinates
        start_tx, start_ty = data.get(
            "start_tile",
            (self.world_map.width // 2, self.world_map.height // 2)
        )
        start_x = start_tx * TILE_SIZE
        start_y = start_ty * TILE_SIZE

        SPRITE_FOLDER = "assets/sprites"

        # Logical player (position, collisions, encounters, etc.)
        self.player = Player(start_x, start_y)

        # Visual sprite that follows the player
        self.setia = Setia(SPRITE_FOLDER, start_pos=(start_x, start_y))

        # Sprite group for drawing (add Setia, not the logical Player)
        self.all_sprites = pygame.sprite.Group()
        self.all_sprites.add(self.setia)

        # Camera tracks the logical player's position
        self.camera = Camera(self.world_map, self.player, screen_width, screen_height)

        self._keys = None

        # Systems
        self.clock = GameClock(cycle_length=20)          # fast for testing
        self.atmosphere = Atmosphere(screen_width, screen_height)
        self.ambient = AmbientLayer(screen_width, screen_height)

        # Encounters
        self.encounter_rate = 0.003
        self.pending_battle = None
        global ENCOUNTERS_ENABLED_GLOBAL
        self.encounters_enabled = ENCOUNTERS_ENABLED_GLOBAL

        # Map transitions
        self.request_map_change = None

        # Region: initialized from starting position
        self.update_region_for_player()

    # --- Region helpers ---

    def get_region_for_tile(self, tile_x, tile_y):
        for (x1, y1, x2, y2), region_name in REGION_ZONES:
            if x1 <= tile_x <= x2 and y1 <= tile_y <= y2:
                return region_name
        return DEFAULT_REGION

    def update_region_for_player(self):
        tile_x = int(self.player.x // TILE_SIZE)
        tile_y = int(self.player.y // TILE_SIZE)
        self.region = self.get_region_for_tile(tile_x, tile_y)

    # --- Encounter handling ---

    def check_for_encounter(self):
        # Only trigger when not already queued
        if self.pending_battle is not None:
            return
        
        if not getattr(self, "encounters_enabled", True):
            return

        # Check tile under player
        tile_x = int(self.player.x // TILE_SIZE)
        tile_y = int(self.player.y // TILE_SIZE)

        if tile_x < 0 or tile_y < 0 or tile_x >= self.world_map.width or tile_y >= self.world_map.height:
            return

        tile_id = self.world_map.tiles[tile_y][tile_x]
        if tile_id not in ENCOUNTER_TILES:
            return

        # Use region-specific encounter table if available
        table = ENCOUNTER_TABLES.get(self.region) or ENCOUNTER_TABLES.get(DEFAULT_REGION)
        if not table:
            return

        # Simple flat chance per movement step
        if random.random() < self.encounter_rate:
            encounter = random.choice(table)
            print("!! ENCOUNTER:", encounter["name"], "appears !!")
            self.pending_battle = encounter

    # --- Scene API ---

    def handle_event(self, event):
        # Debug hotkeys, menus, etc.
        if event.type == pygame.KEYDOWN:
            # Toggle encounters on/off with 'E'
            if event.key == pygame.K_e:
                self.encounters_enabled = not self.encounters_enabled
                global ENCOUNTERS_ENABLED_GLOBAL
                ENCOUNTERS_ENABLED_GLOBAL = self.encounters_enabled
                state = "ON" if self.encounters_enabled else "OFF"
                print(f"[DEBUG] Encounters toggled {state}")

    def update(self, dt):
        """
        Per-frame update for the overworld:

        - Advance in-world time
        - Handle player movement and camera
        - Update ambient particles
        - Handle random encounters
        - Detect map edge transitions
        """
        # --- Time progression ---
        self.clock.update(dt)

        # --- Player movement (logical) ---
        keys = pygame.key.get_pressed()

        # Remember where the player was last frame
        prev_x, prev_y = self.player.x, self.player.y

        # Move the logical player (handles collisions + terrain speed)
        moved = self.player.update(dt, self.world_map, keys)

        # Compute movement delta
        dx = self.player.x - prev_x
        dy = self.player.y - prev_y

        # Update Setia's facing based on movement direction
        if moved:
            if abs(dx) > abs(dy):
                if dx > 0:
                    self.setia.face_right()
                else:
                    self.setia.face_left()
            else:
                if dy > 0:
                    self.setia.face_down()
                else:
                    self.setia.face_up()

        # --- Camera follow (uses logical player coords) ---
        self.camera.update()

        # --- Position Setia in SCREEN space (player - camera) ---
        screen_cx = self.player.x - self.camera.x
        screen_cy = self.player.y - self.camera.y
        self.setia.rect.center = (int(screen_cx), int(screen_cy))

        # --- Animate Setia (and any other sprites) ---
        self.all_sprites.update(dt)

        # --- Ambient / particles ---
        self.ambient.update(dt)

        phase, _ = self.clock.get_phase()
        if random.random() < 0.03:
            if phase in ("day", "dawn"):
                self.ambient.spawn(1, (255, 255, 180), speed=10, drift=10, lifetime=3)
            elif phase == "sunset":
                self.ambient.spawn(1, (255, 140, 80), speed=8, drift=15, lifetime=3)
            elif phase == "night":
                self.ambient.spawn(1, (100, 220, 255), speed=5, drift=20, lifetime=4)

        if moved:
            # Region + encounters
            self.update_region_for_player()
            self.check_for_encounter()

            # --- Map edge detection / map-change request ---
            tile_x = int(self.player.x // TILE_SIZE)
            tile_y = int(self.player.y // TILE_SIZE)

            connections = OVERWORLD_REGIONS.get(self.map_id, {}).get("connections", {})

            if DEBUG_OVERWORLD:
                print(
                    f"[DEBUG] map={self.map_id} tile=({tile_x},{tile_y}) "
                    f"connections={connections}"
                )

            if self.request_map_change is None:
                # West edge
                if tile_x <= 0 and "west" in connections:
                    target = connections["west"]
                    if DEBUG_OVERWORLD:
                        print(f"[DEBUG] Edge WEST reached in {self.map_id} -> {target}")
                    self.request_map_change = target

                # East edge
                elif tile_x >= self.world_map.width - 1 and "east" in connections:
                    target = connections["east"]
                    if DEBUG_OVERWORLD:
                        print(f"[DEBUG] Edge EAST reached in {self.map_id} -> {target}")
                    self.request_map_change = target

                # North edge
                elif tile_y <= 0 and "north" in connections:
                    target = connections["north"]
                    if DEBUG_OVERWORLD:
                        print(f"[DEBUG] Edge NORTH reached in {self.map_id} -> {target}")
                    self.request_map_change = target

                # South edge
                elif tile_y >= self.world_map.height - 1 and "south" in connections:
                    target = connections["south"]
                    if DEBUG_OVERWORLD:
                        print(f"[DEBUG] Edge SOUTH reached in {self.map_id} -> {target}")
                    self.request_map_change = target

    def draw(self, surface):
        # map + player
        self.world_map.draw(surface, self.camera, self.screen_width, self.screen_height)
        self.all_sprites.draw(surface)

        # atmosphere overlay (time-of-day + region)
        phase_data = self.clock.get_phase()
        overlay = self.atmosphere.build_overlay(phase_data, self.region)
        surface.blit(overlay, (0, 0))

        # ambient particles on top
        self.ambient.draw(surface)
