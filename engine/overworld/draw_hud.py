from __future__ import annotations

import pygame


class OverworldHUD:
    """
    Draw-only HUD helper for the overworld.

    Laws:
      - No simulation authority.
      - Reads state from scene/runtime/controllers.
      - No pygame.image.load here (use scene.assets cache).
    """

    def __init__(self) -> None:
        # Cached scaled surfaces keyed by (path, (w,h))
        self._scaled_cache: dict[tuple[str, tuple[int, int]], pygame.Surface] = {}

    def _get_scaled(
        self,
        *,
        assets,
        path: str,
        size: tuple[int, int],
    ) -> pygame.Surface:
        key = (path, size)
        if key in self._scaled_cache:
            return self._scaled_cache[key]
        surf = assets.image(path)  # your OverworldAssets API
        scaled = pygame.transform.smoothscale(surf, size)
        self._scaled_cache[key] = scaled
        return scaled

    def draw(
        self,
        *,
        screen: pygame.Surface,
        scene,
    ) -> None:
        """Draw HUD elements onto final screen (call AFTER scene.draw_mode7)."""
        self._draw_encounter_eye(screen=screen, scene=scene)

        # Keep minimap behavior exactly as-is: call whichever scene method exists.
        if hasattr(scene, "draw_minimap"):
            scene.draw_minimap(screen)
        elif hasattr(scene, "draw_debug_minimap"):
            scene.draw_debug_minimap(screen)

    def _draw_encounter_eye(self, *, screen: pygame.Surface, scene) -> None:
        # If you haven't loaded encounters yet, still show closed eye.
        idx = 0

        if getattr(scene, "pending_battle", None) is not None:
            idx = 4
        else:
            idx = 0
            enc = getattr(scene, "encounters", None)

        # Read encounter meter ratio (0..1)
        enc = getattr(scene, "encounters", None)
        if enc is not None:
            ratio = float(getattr(enc, "telegraph", 0.0))
            ratio = max(0.0, min(1.0, ratio))
            idx = min(4, int(ratio * 5))

        # File names as you saved them:
        paths = [
            "hud_elements/encounter_eye_00.png",
            "hud_elements/encounter_eye_01.png",
            "hud_elements/encounter_eye_02.png",
            "hud_elements/encounter_eye_03.png",
            "hud_elements/encounter_eye_04.png",
        ]
        path = paths[idx]

        # Size + placement
        size = getattr(scene, "encounter_eye_size", (128, 128))
        margin = getattr(scene, "hud_margin", 16)

        img = self._get_scaled(assets=scene.assets, path=path, size=size)

        x = margin
        y = screen.get_height() - margin - img.get_height()
        screen.blit(img, (x, y))
