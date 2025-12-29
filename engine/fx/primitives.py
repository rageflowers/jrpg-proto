# engine/fx/primitives.py

from __future__ import annotations

from typing import Any, Dict, Tuple
import math

import pygame


class FXPrimitives:
    """
    Low-level drawing helpers for FXSystem.

    - Draws into the provided layer surfaces.
    - Adjusts camera_offset for quake-like effects.
    - Stateless except for the surfaces and shared camera_offset vector.
    """

    def __init__(
        self,
        tint_surface: pygame.Surface,
        aura_surface: pygame.Surface,
        particle_surface: pygame.Surface,
        camera_offset: pygame.math.Vector2,
    ) -> None:
        self.tint_surface = tint_surface
        self.aura_surface = aura_surface
        self.particle_surface = particle_surface
        self.camera_offset = camera_offset

    # --------------------------------------------------------------
    # Impact flash: white flash over sprite
    # --------------------------------------------------------------

    def impact_flash(
        self,
        sprite: Any,
        progress: float,
        data: Dict[str, Any],
    ) -> None:
        """
        Draw a brief white flash over the sprite.

        - progress: 0 → 1 over the event duration.
        """
        if sprite is None:
            return

        img = getattr(sprite, "current_frame", None)
        if img is None:
            img = getattr(sprite, "image", None)
        if img is None:
            return

        # Fade out over time
        alpha = int(255 * max(0.0, 1.0 - progress))
        if alpha <= 0:
            return

        flash_img = img.copy()
        # Add white with alpha
        flash_img.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_ADD)

        self.particle_surface.blit(
            flash_img,
            (int(sprite.x), int(sprite.y)),
        )

    # --------------------------------------------------------------
    # Pulse sprite: colored glow overlay
    # --------------------------------------------------------------

    def pulse_sprite(
        self,
        sprite: Any,
        progress: float,
        data: Dict[str, Any],
    ) -> None:
        """
        Draw a soft, colored overlay pulse on the sprite.
        """
        if sprite is None:
            return

        color: Tuple[int, int, int] = data.get("color", (255, 255, 255))

        img = getattr(sprite, "current_frame", None)
        if img is None:
            img = getattr(sprite, "image", None)
        if img is None:
            return

        alpha = int(180 * max(0.0, 1.0 - progress))
        if alpha <= 0:
            return

        overlay = pygame.Surface(img.get_size(), pygame.SRCALPHA)
        overlay.fill((*color, alpha))

        self.aura_surface.blit(
            overlay,
            (int(sprite.x), int(sprite.y)),
            special_flags=pygame.BLEND_RGBA_ADD,
        )

    # --------------------------------------------------------------
    # Aura: radial glow around sprite
    # --------------------------------------------------------------

    def apply_aura(
        self,
        sprite: Any,
        progress: float,
        data: Dict[str, Any],
    ) -> None:
        """
        Draw a soft radial aura around the sprite.
        """
        if sprite is None:
            return

        color: Tuple[int, int, int] = data.get("color", (255, 255, 255))

        base_img = getattr(sprite, "image", None)
        if base_img is None:
            base_img = getattr(sprite, "current_frame", None)
        if base_img is None:
            return

        # Radius shrinks slightly over time, alpha fades
        radius = int(40 * (1.0 - 0.3 * progress))
        radius = max(radius, 10)
        alpha = int(120 * max(0.0, 1.0 - progress))
        if alpha <= 0:
            return

        aura = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            aura,
            (*color, alpha),
            (radius, radius),
            radius,
        )

        center_x = int(sprite.x + base_img.get_width() / 2)
        center_y = int(sprite.y + base_img.get_height() / 2)

        self.aura_surface.blit(
            aura,
            (center_x - radius, center_y - radius),
            special_flags=pygame.BLEND_RGBA_ADD,
        )

    # --------------------------------------------------------------
    # Tint screen: full-screen overlay
    # --------------------------------------------------------------

    def tint_screen(
        self,
        progress: float,
        data: Dict[str, Any],
    ) -> None:
        """
        Apply a color overlay over the entire battlefield.
        """
        color: Tuple[int, int, int] = data.get("color", (255, 255, 255))
        strength: float = float(data.get("strength", 1.0))

        alpha = int(180 * strength * max(0.0, 1.0 - progress))
        if alpha <= 0:
            return

        w, h = self.tint_surface.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((*color, alpha))

        self.tint_surface.blit(
            overlay,
            (0, 0),
            special_flags=pygame.BLEND_RGBA_ADD,
        )

    # --------------------------------------------------------------
    # Quake: camera shake
    # --------------------------------------------------------------

    def quake(
        self,
        progress: float,
        data: Dict[str, Any],
        global_time: float,
    ) -> None:
        """
        Simple screen shake using sinusoidal offsets.
        """
        strength: float = float(data.get("strength", 5.0))
        amp = strength * max(0.0, 1.0 - progress)

        if amp <= 0.0:
            # Let FXSystem reset to base elsewhere if desired.
            return
        
        # Simple multi-axis shake
        self.camera_offset.x = math.sin(global_time * 40.0) * amp
        self.camera_offset.y = math.cos(global_time * 35.0) * amp

    # --------------------------------------------------------------
    # Burst particles: tiny expanding dots
    # --------------------------------------------------------------

    def burst_particles(
        self,
        progress: float,
        data: Dict[str, Any],
    ) -> None:
        """
        Simple radial burst of small particles.
        """
        pos = data.get("position")
        if pos is None:
            return

        count = int(data.get("count", 4))
        spread = float(data.get("spread", 20.0))
        effect_kind = data.get("effect_kind", "white")

        colors = {
            "white": (255, 255, 255),
            "shadow": (160, 130, 220),
            "holy": (255, 248, 215),
            "wind": (195, 245, 235),
        }
        color = colors.get(effect_kind, (255, 255, 255))

        alpha = int(180 * max(0.0, 1.0 - progress))
        if alpha <= 0:
            return

        for i in range(max(count, 1)):
            angle = (i / max(count, 1)) * (2.0 * math.pi)
            dist = spread * progress * 1.5
            px = int(pos.x + math.cos(angle) * dist)
            py = int(pos.y + math.sin(angle) * dist)

            pygame.draw.circle(
                self.particle_surface,
                (*color, alpha),
                (px, py),
                3,
            )
