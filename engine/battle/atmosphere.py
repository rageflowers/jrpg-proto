import pygame


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
        int(lerp(c1[3], c2[3], t)),
    )


class Atmosphere:
    """
    Fullscreen atmospheric overlay:
    - time-of-day tint
    - region-based tint
    Can be used by overworld & battle scenes.
    """

    def __init__(self, width, height):
        self.width = width
        self.height = height
        # Alpha-capable surface for RGBA fills
        self.surface = pygame.Surface((width, height), pygame.SRCALPHA).convert_alpha()

    def get_time_tint(self, phase):
        # (R, G, B, A)
        if phase == "dawn":
            return (255, 190, 140, 40)
        elif phase == "day":
            return (255, 255, 255, 0)
        elif phase == "sunset":
            return (255, 150, 100, 70)
        elif phase == "night":
            return (40, 70, 160, 130)
        return (0, 0, 0, 0)

    def get_region_tint(self, region):
        # subtle, low-alpha biases
        if region == "desert":
            return (255, 220, 150, 25)
        if region == "night_forest":
            return (80, 200, 160, 35)
        if region == "ancient_ruins":
            return (160, 220, 180, 25)
        if region == "mountain_pass":
            return (180, 220, 255, 20)
        return (0, 0, 0, 0)

    def build_overlay(self, phase_data, region, strength=1.0):
        """
        phase_data = (phase, t) where:
          - phase is one of "dawn", "day", "sunset", "night"
          - t is a blend factor between current and next phase (0.0–1.0)
        """
        phase, t = phase_data

        # Normalize t to a safe 0–1 float
        try:
            t = float(t)
        except (TypeError, ValueError):
            t = 0.0
        # Allow looping values, then clamp
        t = t % 1.0
        t = max(0.0, min(1.0, t))

        # Define the full ordered list for blending
        timeline = ["dawn", "day", "sunset", "night", "dawn"]
        if phase not in timeline:
            # Fallback if something weird gets passed in
            phase = "day"

        current_index = timeline.index(phase)
        # Guard against index at the very end, though "dawn" repeats
        if current_index >= len(timeline) - 1:
            next_phase = timeline[0]
        else:
            next_phase = timeline[current_index + 1]

        c1 = self.get_time_tint(phase)
        c2 = self.get_time_tint(next_phase)

        # Blend time-of-day colors smoothly
        r, g, b, a = lerp_color(c1, c2, t)

        # Blend region tint on top (still additive, like before)
        rr, rg, rb, ra = self.get_region_tint(region)

        if ra > 0:
            s = ra / 255.0
            r, g, b, a = lerp_color((r, g, b, a), (rr, rg, rb, a + ra), s)

        # Apply global strength multiplier to alpha only
        a = a * strength

        # Clamp and cast all components to valid 0–255 ints
        r = int(max(0, min(255, r)))
        g = int(max(0, min(255, g)))
        b = int(max(0, min(255, b)))
        a = int(max(0, min(255, a)))

        # Clear then fill with the new tint
        self.surface.fill((0, 0, 0, 0))
        self.surface.fill((r, g, b, a))
        return self.surface
