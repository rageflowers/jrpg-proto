import pygame

class BattleSprite:
    """Simple looping idle animation sprite for battle actors."""

    def __init__(self, frame_paths, x, y, scale=1.0, facing="right", idle_enabled=True):
        self.x = x
        self.y = y
        self.scale = scale
        self.facing = facing  # "left" or "right"

        self.animations = {
            "idle": self._load_frames(frame_paths),
        }
        self.current_anim = "idle"
        self.frame_index = 0
        self.frame_timer = 0.0
        self.frame_duration = 0.14  # seconds per frame

        # New: can this sprite play its idle animation?
        self.idle_enabled = idle_enabled

        # New: flash timer (seconds remaining)
        self.flash_timer = 0.0
        # Dissolve factor
        self.dissolve_factor = 1.0  # 1 = fully visible, 0 = gone

    def _load_frames(self, paths):
        frames = []
        for path in paths:
            img = pygame.image.load(path).convert_alpha()
            w, h = img.get_size()
            img = pygame.transform.smoothscale(
                img, (int(w * self.scale), int(h * self.scale))
            )
            frames.append(img)
        if not frames:
            print("WARNING: no frames loaded for BattleSprite")
        return frames

    def set_animation(self, name):
        if name == self.current_anim:
            return
        if name in self.animations:
            self.current_anim = name
            self.frame_index = 0
            self.frame_timer = 0.0

    def trigger_flash(self, duration: float = 0.15):
        """Cause this sprite to flash bright for a short duration."""
        self.flash_timer = duration

    def set_dissolve_factor(self, t: float):
        # clamp between 0 and 1
        self.dissolve_factor = max(0.0, min(1.0, t))
    
    
    def update(self, dt):
        # Animate idle only if allowed
        if self.idle_enabled:
            frames = self.animations[self.current_anim]
            if len(frames) > 1:
                self.frame_timer += dt
                if self.frame_timer >= self.frame_duration:
                    self.frame_timer -= self.frame_duration
                    self.frame_index = (self.frame_index + 1) % len(frames)

        # Tick down flash timer
        if self.flash_timer > 0.0:
            self.flash_timer = max(0.0, self.flash_timer - dt)

    def draw(self, surface):
        """
        Draws the current animation frame with:
        - facing flip
        - hit flash (invert colors)
        - dissolve fade-out (alpha)
        """

        # ---------------------------------------------------------
        # 1. Get current frame
        # ---------------------------------------------------------
        frames = self.animations.get(self.current_anim, [])
        if not frames:
            return

        base = frames[self.frame_index]

        # Facing flip
        frame_to_draw = base
        if self.facing == "left":
            frame_to_draw = pygame.transform.flip(base, True, False)

        rect = frame_to_draw.get_rect()
        rect.midbottom = (int(self.x), int(self.y))

        # ---------------------------------------------------------
        # 2. Dissolve fade-out
        # ---------------------------------------------------------
        dissolve = max(0.0, min(1.0, self.dissolve_factor))

        # Completely invisible → skip
        if dissolve <= 0.0:
            return

        # Work from a copy
        img = frame_to_draw.copy()

        # ---------------------------------------------------------
        # 3. Flash inversion (per-pixel)
        # ---------------------------------------------------------
        if self.flash_timer > 0.0:
            w, h = img.get_size()
            for ix in range(w):
                for iy in range(h):
                    r, g, b, a = img.get_at((ix, iy))
                    if a == 0:
                        continue  # don't invert fully transparent pixels
                    img.set_at((ix, iy), (255 - r, 255 - g, 255 - b, a))

        # ---------------------------------------------------------
        # 4. Apply dissolve alpha
        # ---------------------------------------------------------
        if dissolve < 1.0:
            img.set_alpha(int(255 * dissolve))

        # ---------------------------------------------------------
        # 5. Draw final image
        # ---------------------------------------------------------
        surface.blit(img, rect)
