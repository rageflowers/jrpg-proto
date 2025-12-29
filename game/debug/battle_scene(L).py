import os
import pygame
import random
from engine.battle.atmosphere import Atmosphere
from engine.battle.ambient_layer import AmbientLayer

# --- Background registry ---
BATTLE_BACKGROUNDS = {
    "grasslands": "grasslands.png",
    "desert": "desert.png",
    "night_forest": "night_forest.png",
    "mountain_pass": "mountain_pass.png",
    "ancient_ruins": "ancient_ruins.png",
    "default": "grasslands.png",  # fallback
}

# --- Sprite registry ---
# Map enemy names (from ENCOUNTER_TABLES) to sprite filenames
ENEMY_SPRITE_FILES = {
    "Slime": "slime.png",
    "Wolf": "wolf.png",
    "Bandit": "bandit.png",
}

# Cache so we don't reload images repeatedly
_SPRITE_CACHE = {}


def load_enemy_sprite(enemy_name, size):
    """
    Load and scale the enemy sprite for the given enemy_name.
    Returns a pygame.Surface or None if not available.
    """
    filename = ENEMY_SPRITE_FILES.get(enemy_name)
    if not filename:
        return None

    # Resolve path relative to this file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sprite_path = os.path.join(base_dir, "assets", "enemies", filename)

    # Use cache if already loaded
    cache_key = (sprite_path, size)
    if cache_key in _SPRITE_CACHE:
        return _SPRITE_CACHE[cache_key]

    if not os.path.exists(sprite_path):
        print(f"[BattleScene] Sprite not found for {enemy_name}: {sprite_path}")
        return None

    try:
        image = pygame.image.load(sprite_path).convert_alpha()
        if size is not None:
            image = pygame.transform.smoothscale(image, size)
        _SPRITE_CACHE[cache_key] = image
        return image
    except Exception as e:
        print(f"[BattleScene] Failed to load sprite '{sprite_path}': {e}")
        return None


class BattleScene:
    """
    Prototype battle screen.
    1 = Attack, 2 = Run.

    Visual:
    - Distinct background
    - Enemy sprite if available, else placeholder block
    - UI panel at bottom
    """

    def __init__(self, screen_width, screen_height, encounter, region="grasslands", phase="day"):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.region = region
        self.phase = phase
        # Simple player stub
        self.player_max_hp = 30
        self.player_hp = 30
        self.player_attack = 8

        # Enemy data from overworld
        self.enemy_name = encounter["name"]
        self.enemy_max_hp = encounter["max_hp"]
        self.enemy_hp = encounter["max_hp"]
        self.enemy_attack = encounter["attack"]

        self.message = f"A wild {self.enemy_name} appears!"

        self.done = False          # when True, caller should exit battle
        self.result = None         # "victory", "escape", "defeat"

        # Fonts
        self.font_main = pygame.font.SysFont(None, 28)
        self.font_small = pygame.font.SysFont(None, 22)

        # Layout: top = arena, bottom = UI
        self.bg_rect = pygame.Rect(0, 0, self.screen_width, int(self.screen_height * 0.6))
        self.ui_rect = pygame.Rect(
            0,
            int(self.screen_height * 0.6),
            self.screen_width,
            int(self.screen_height * 0.4),
        )
        # Atmosphere just for the arena area (not UI)
        self.atmosphere = Atmosphere(self.bg_rect.width, self.bg_rect.height)
        self.ambient = AmbientLayer(self.bg_rect.width, self.bg_rect.height)
        self.background = self.load_background(self.region)

        # Enemy placement
        self.enemy_rect = pygame.Rect(0, 0, 80, 80)
        self.enemy_rect.centerx = self.screen_width // 2
        self.enemy_rect.centery = self.bg_rect.centery - 20

        # Try to load a sprite for this enemy
        self.enemy_sprite = load_enemy_sprite(self.enemy_name, self.enemy_rect.size)
        self.enemy_color = (200, 80, 80)  # used if no sprite
        

    # --- Input handling ---

    def load_background(self, region):
        filename = BATTLE_BACKGROUNDS.get(region, BATTLE_BACKGROUNDS["default"])
        bg_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets",
            "backgrounds",
            filename,
        )

        if not os.path.exists(bg_path):
            print(f"[BattleScene] Missing background for region '{region}' at {bg_path}")
            return None

        try:
            image = pygame.image.load(bg_path).convert()
            # Scale to match the bg_rect height while filling width
            image = pygame.transform.smoothscale(
                image,
                (self.bg_rect.width, self.bg_rect.height),
            )
            return image
        except Exception as e:
            print(f"[BattleScene] Failed to load background '{bg_path}': {e}")
            return None

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_1:
                self.player_attack_action()
            elif event.key == pygame.K_2:
                self.run_attempt()

    # --- Battle actions ---

    def player_attack_action(self):
        if self.done:
            return

        # Player hits enemy
        self.enemy_hp -= self.player_attack
        if self.enemy_hp <= 0:
            self.enemy_hp = 0
            self.message = f"You defeated the {self.enemy_name}!"
            self.result = "victory"
            self.done = True
            return

        # Enemy counterattacks
        self.player_hp -= self.enemy_attack
        if self.player_hp <= 0:
            self.player_hp = 0
            self.message = f"You were defeated by the {self.enemy_name}..."
            self.result = "defeat"
            self.done = True
        else:
            self.message = f"You hit the {self.enemy_name}! It strikes back!"

    def run_attempt(self):
        if self.done:
            return
        self.message = f"You fled from the {self.enemy_name}."
        self.result = "escape"
        self.done = True

    # --- Update/draw ---

    def update(self, dt):
        if self.done:
            return

        # ambient particles follow frozen phase snapshot
        self.ambient.update(dt)

        # get a stable phase name
        if isinstance(self.phase, tuple):
            phase_name, _ = self.phase
        else:
            phase_name = self.phase

        if random.random() < 0.04:  # a bit higher than overworld; arena is smaller
            if phase_name in ("day", "dawn"):
                # soft dust/pollen
                self.ambient.spawn(1, (255, 255, 180), speed=8, drift=10, lifetime=2.5)
            elif phase_name == "sunset":
                self.ambient.spawn(1, (255, 160, 120), speed=6, drift=12, lifetime=2.0)
            elif phase_name == "night":
                # slightly region-flavored
                if self.region == "night_forest":
                    self.ambient.spawn(1, (120, 255, 200), speed=3, drift=15, lifetime=3.0)
                else:
                    self.ambient.spawn(1, (150, 200, 255), speed=3, drift=10, lifetime=3.0)

        # ...your existing input/command + enemy AI + win/lose logic...

    def draw(self, surface):
        # --- Background ---
        if self.background:
            surface.blit(self.background, self.bg_rect)
        else:
            pygame.draw.rect(surface, (10, 10, 30), self.bg_rect)
        
        overlay = self.atmosphere.build_overlay(self.phase, self.region, strength=1.6)
        surface.blit(overlay, self.bg_rect.topleft)
        # --- Enemy sprite / placeholder ---

        if self.enemy_sprite:
            enemy_pos = self.enemy_sprite.get_rect(center=self.enemy_rect.center)
            surface.blit(self.enemy_sprite, enemy_pos)
        else:
            # Placeholder block with outline
            pygame.draw.rect(
                surface,
                (80, 20, 20),
                self.enemy_rect.inflate(10, 10),
                border_radius=10,
            )
            pygame.draw.rect(
                surface,
                self.enemy_color,
                self.enemy_rect,
                border_radius=8,
            )

        # Enemy name (above sprite)
        name_surf = self.font_small.render(self.enemy_name, True, (255, 230, 230))
        name_rect = name_surf.get_rect(
            midbottom=(self.enemy_rect.centerx, self.bg_rect.top + 24)
        )
        surface.blit(name_surf, name_rect)

        # --- Ambient particles in arena ---
        self.ambient.draw(surface, offset=self.bg_rect.topleft)
        
        # --- Enemy sprite/block ---
        if self.enemy_sprite:
            surface.blit(self.enemy_sprite, self.enemy_rect)
        else:
            pygame.draw.rect(surface, self.enemy_color, self.enemy_rect)
        
        # --- UI panel ---
        pygame.draw.rect(surface, (20, 20, 20), self.ui_rect)

        # Message line
        msg_surf = self.font_main.render(self.message, True, (240, 240, 240))
        msg_rect = msg_surf.get_rect(
            topleft=(self.ui_rect.left + 16, self.ui_rect.top + 10)
        )
        surface.blit(msg_surf, msg_rect)

        # Player HP
        p_text = f"Hero HP: {self.player_hp}/{self.player_max_hp}"
        p_surf = self.font_small.render(p_text, True, (180, 220, 255))
        surface.blit(p_surf, (self.ui_rect.left + 16, self.ui_rect.top + 48))

        # Enemy HP
        e_text = f"{self.enemy_name}: {self.enemy_hp}/{self.enemy_max_hp}"
        e_surf = self.font_small.render(e_text, True, (255, 180, 180))
        surface.blit(e_surf, (self.ui_rect.left + 16, self.ui_rect.top + 72))

        # Commands
        c1 = self.font_small.render("1) Attack", True, (220, 220, 220))
        c2 = self.font_small.render("2) Run", True, (220, 220, 220))
        surface.blit(c1, (self.ui_rect.left + 16, self.ui_rect.bottom - 56))
        surface.blit(c2, (self.ui_rect.left + 160, self.ui_rect.bottom - 56))
        
        # --- Atmospheric overlay only on arena ---
        # phase may be a string or (phase, t); both work with your current Atmosphere
        phase_data = self.phase if isinstance(self.phase, tuple) else (self.phase, 0.0)
        overlay = self.atmosphere.build_overlay(phase_data, self.region, strength=1.6)
        surface.blit(overlay, self.bg_rect.topleft)