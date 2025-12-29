# engine/overworld/regions/silhouettes.py
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, Optional, Set, Tuple

import pygame


def _angle_wrap_pi(a: float) -> float:
    """Wrap angle to [-pi, +pi]."""
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def angle_delta(a: float, b: float) -> float:
    """Smallest absolute angular difference between angles a and b (radians)."""
    return abs(_angle_wrap_pi(a - b))


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    """Classic smoothstep in [0..1] for x between edge0 and edge1."""
    if edge0 == edge1:
        return 1.0 if x >= edge1 else 0.0
    t = (x - edge0) / (edge1 - edge0)
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    return t * t * (3.0 - 2.0 * t)


@dataclass
class SilhouetteBand:
    """
    One horizon-anchored silhouette band.

    Runtime behavior:
    - Strongest near facing_angle
    - Fades out as camera deviates away from facing_angle
    - Slight yaw parallax via yaw_factor (purely camera-angle-driven, not time drift)
    """
    image: pygame.Surface

    # Where should it be strongest? (radians)
    facing_angle: float

    # Grouping/filtering (lets author multiple "tiers" of silhouettes)
    tier: int = 1

    # Fade behavior (radians). inner = fully visible, outer = fully gone
    fade_inner: float = math.radians(15)
    fade_outer: float = math.radians(140)

    # Optional yaw parallax (NOT time drift). Usually very small.
    yaw_factor: float = 0.18

    # Vertical offset relative to (horizon_y - image_height)
    y_offset: int = 0

    # Alpha envelope
    alpha_max: int = 255
    alpha_min: int = 0

    # Allow band to dip below horizon by N pixels (0 = clamp fully above horizon)
    horizon_overlap: int = 0


class SilhouetteSystem:
    """
    Draw-only system: owns bands and draws them, but does not simulate/tick.
    Intended to be owned by RegionRuntime and passed to a presenter.
    """
    def __init__(self) -> None:
        self.bands: list[SilhouetteBand] = []

        # Cache for alpha-modulated surfaces to avoid per-frame .copy() cost
        # Key: (id(surface), alpha) -> Surface
        self._alpha_cache: Dict[Tuple[int, int], pygame.Surface] = {}

    def add(self, band: SilhouetteBand) -> None:
        self.bands.append(band)

    def clear_cache(self) -> None:
        """If you hot-swap band images at runtime, call this to avoid stale cached entries."""
        self._alpha_cache.clear()

    def _get_alpha_surface(self, surf: pygame.Surface, alpha: int) -> pygame.Surface:
        if alpha >= 255:
            return surf
        if alpha <= 0:
            # Caller should have culled already; return surf to keep type stable.
            return surf

        key = (id(surf), alpha)
        cached = self._alpha_cache.get(key)
        if cached is not None:
            return cached

        tmp = surf.copy()
        tmp.set_alpha(alpha)
        self._alpha_cache[key] = tmp
        return tmp

    def draw(
        self,
        dst: pygame.Surface,
        *,
        horizon_y: int,
        cam_angle: float,
        include_tiers: Optional[Set[int]] = None,
    ) -> None:
        """
        Draw all bands horizon-anchored and yaw-gated. Does not clear dst.
        """
        w, h = dst.get_size()

        for band in self.bands:
            if include_tiers is not None and band.tier not in include_tiers:
                continue

            surf = band.image
            tw, th = surf.get_size()
            if tw <= 0 or th <= 0:
                continue

            # Signed delta for horizontal parallax
            d = _angle_wrap_pi(cam_angle - band.facing_angle)

            # Fade uses absolute angular distance (prevents a hard cut at wrap seam)
            fade_d = abs(d)
            t = smoothstep(band.fade_inner, band.fade_outer, fade_d)
            a = int(band.alpha_max * (1.0 - t))

            if a <= band.alpha_min:
                continue
            if a > 255:
                a = 255

            # Horizon anchoring
            y = (horizon_y - th) + int(band.y_offset)

            # Clamp to not dip under the horizon unless allowed
            if band.horizon_overlap <= 0:
                y = min(y, horizon_y - th)
            else:
                y = min(y, horizon_y + band.horizon_overlap - th)

            # Small yaw parallax: pixels to shift per radian
            px_per_rad = band.yaw_factor * w
            x = int((w // 2) - (tw // 2) - (d * px_per_rad))

            blit_surf = self._get_alpha_surface(surf, a)
            dst.blit(blit_surf, (x, y))
