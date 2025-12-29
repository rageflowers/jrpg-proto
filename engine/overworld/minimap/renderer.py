# engine/overworld/minimap/renderer.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Iterable

import pygame

try:
    import pytmx  # type: ignore
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "pytmx is required for minimap rendering. Install pytmx or ensure it's in your environment."
    ) from e


@dataclass(frozen=True)
class MinimapPOI:
    """Pure data POI for minimap overlays (no narrative logic here)."""
    x: float
    y: float
    kind: str = "narrative"  # future-proof: narrative, shop, danger, etc.
    hidden: bool = False


@dataclass(frozen=True)
class MinimapExit:
    """Exit marker data for minimap overlays (world-space)."""
    rect: pygame.Rect


class MinimapRenderer:
    """
    Minimal, modular minimap renderer.

    Render stack (bottom -> top):
      1) parchment background (optional)
      2) terrain abstraction from TMX tiles
      3) exits (small triangles)
      4) POIs (small crosses)
      5) player dot

    Goals:
      - quiet orientation, not navigation
      - no landmarks (trees/props) baked in
      - points of interest (POIs) and exits are allowed, subtle

    Notes:
      - This renderer is deliberately "data-fed":
          * you give it TMX path + optional exits/pois
          * it does not consult narrative systems or scene specifics
    """

    def __init__(
        self,
        *,
        size_px: int = 160,
        padding_px: int = 8,
        parchment_path: Optional[str | Path] = None,
        terrain_alpha: int = 190,
        ink_alpha: int = 210,
    ) -> None:
        self.size_px = int(size_px)
        self.padding_px = int(padding_px)

        # Cache: tmx_path -> (terrain_surface, map_size_px)
        self._terrain_cache: dict[str, tuple[pygame.Surface, tuple[int, int]]] = {}

        # Optional parchment background
        self._parchment_src: Optional[pygame.Surface] = None
        self._parchment_scaled: Optional[pygame.Surface] = None
        self._parchment_path: Optional[str] = None

        self.terrain_alpha = int(terrain_alpha)
        self.ink_alpha = int(ink_alpha)

        if parchment_path is not None:
            self.set_parchment(parchment_path)

        # A reusable surface to draw onto (callers can blit this)
        self._frame = pygame.Surface((self.size_px, self.size_px), pygame.SRCALPHA)

    # -----------------------------
    # Public API
    # -----------------------------
    def set_parchment(self, parchment_path: str | Path) -> None:
        path = str(parchment_path)
        self._parchment_path = path
        self._parchment_src = pygame.image.load(path).convert_alpha()
        self._parchment_scaled = pygame.transform.smoothscale(
            self._parchment_src, (self.size_px, self.size_px)
        )

    def invalidate_cache(self) -> None:
        """Call if you edit TMX and want to force rebuild during dev."""
        self._terrain_cache.clear()

    def render(
        self,
        *,
        tmx_path: str | Path,
        player_world_px: tuple[float, float],
        exits: Optional[Iterable[MinimapExit]] = None,
        pois: Optional[Iterable[MinimapPOI]] = None,
        # if you want the minimap centered on the player, set this True
        center_on_player: bool = False,
    ) -> pygame.Surface:
        """
        Returns an RGBA surface of size (size_px, size_px).
        """
        tmx_path_s = str(tmx_path)
        terrain_surf, map_size_px = self._get_or_build_terrain(tmx_path_s)

        # Clear frame
        self._frame.fill((0, 0, 0, 0))

        # 1) Parchment background
        if self._parchment_scaled is not None:
            self._frame.blit(self._parchment_scaled, (0, 0))

        # 2) Terrain layer
        # Terrain surface is already (size_px - 2*padding)^2, blit into padded window.
        terrain_rect = terrain_surf.get_rect()
        terrain_rect.topleft = (self.padding_px, self.padding_px)
        self._frame.blit(terrain_surf, terrain_rect)

        # World->minimap transform
        map_w, map_h = map_size_px
        inner = self.size_px - 2 * self.padding_px
        sx = inner / max(1, map_w)
        sy = inner / max(1, map_h)

        # Optional: center on player by offsetting transform
        # Default: full-map view (no offset).
        off_x = 0.0
        off_y = 0.0
        if center_on_player:
            px, py = player_world_px
            # center inner area on player, clamped to map bounds
            view_w = inner / sx
            view_h = inner / sy
            min_x = 0.0
            min_y = 0.0
            max_x = max(0.0, map_w - view_w)
            max_y = max(0.0, map_h - view_h)
            off_x = _clamp(px - view_w * 0.5, min_x, max_x)
            off_y = _clamp(py - view_h * 0.5, min_y, max_y)

        def w2m(wx: float, wy: float) -> tuple[int, int]:
            mx = (wx - off_x) * sx + self.padding_px
            my = (wy - off_y) * sy + self.padding_px
            return int(mx), int(my)

        # 3) Exits
        if exits:
            for ex in exits:
                self._draw_exit_marker(ex.rect, w2m, map_size_px, off_x, off_y, sx, sy)

        # 4) POIs
        if pois:
            for p in pois:
                if p.hidden:
                    continue
                self._draw_poi_cross(p.x, p.y, w2m)

        # 5) Player dot
        self._draw_player_dot(player_world_px[0], player_world_px[1], w2m)

        return self._frame

    # -----------------------------
    # Terrain build
    # -----------------------------
    def _get_or_build_terrain(self, tmx_path: str) -> tuple[pygame.Surface, tuple[int, int]]:
        cached = self._terrain_cache.get(tmx_path)
        if cached is not None:
            return cached

        tmx = pytmx.load_pygame(tmx_path)
        map_w_px = int(tmx.width * tmx.tilewidth)
        map_h_px = int(tmx.height * tmx.tileheight)

        # Build a tiny abstraction image at "tile resolution"
        # Then scale to minimap inner size.
        tw = int(tmx.width)
        th = int(tmx.height)

        scale_src = 2
        tile_surf = pygame.Surface((tw * scale_src, th * scale_src), pygame.SRCALPHA)

        # Cache representative colors per image id (fast)
        img_color: dict[int, pygame.Color] = {}

        def color_for_img(img: pygame.Surface) -> pygame.Color:
            key = id(img)
            if key in img_color:
                return img_color[key]

            w, h = img.get_width(), img.get_height()
            c = img.get_at((w // 2, h // 2))
            if c.a == 0:
                for ox, oy in ((1, 1), (-1, 1), (1, -1), (-1, -1), (0, 0)):
                    xx = max(0, min(w - 1, w // 2 + ox))
                    yy = max(0, min(h - 1, h // 2 + oy))
                    c2 = img.get_at((xx, yy))
                    if c2.a != 0:
                        c = c2
                        break

            img_color[key] = pygame.Color(c.r, c.g, c.b, 255)
            return img_color[key]
        # Collect visible tile layers (ignore groups, images, etc.)
        layers = [
            layer for layer in tmx.layers
            if hasattr(layer, "tiles") and getattr(layer, "visible", True)
        ]
        # Draw tile colors (later layers overwrite earlier)
        tile_surf.fill((0, 0, 0, 0))
        for layer in layers:
            for x, y, img in layer.tiles():
                if img is None:
                    continue
                col = color_for_img(img)
                pygame.draw.rect(
                    tile_surf,
                    col,
                    pygame.Rect(x * scale_src, y * scale_src, scale_src, scale_src),
                )

        # Optional: if nothing was drawn (blank map), leave it transparent
        # and still scale it.
        inner = self.size_px - 2 * self.padding_px
        terrain = pygame.transform.smoothscale(tile_surf, (inner, inner)).convert_alpha()

        # Reduce alpha so parchment shows through.
        terrain.set_alpha(self.terrain_alpha)

        out = (terrain, (map_w_px, map_h_px))
        self._terrain_cache[tmx_path] = out
        print(
            f"[MINIMAP] Built terrain for {tmx_path}: "
            f"{tw}x{th} tiles → {inner}x{inner}px, "
            f"nonempty={any(tile_surf.get_at((x, y)).a > 0 for x in range(tw) for y in range(th))}"
        )

        return out

    # -----------------------------
    # Overlay drawing
    # -----------------------------
    def _draw_player_dot(self, wx: float, wy: float, w2m) -> None:
        x, y = w2m(wx, wy)
        # Player is the brightest element (still muted).
        pygame.draw.circle(self._frame, (245, 245, 245, 235), (x, y), 3)

    def _draw_poi_cross(self, wx: float, wy: float, w2m) -> None:
        x, y = w2m(wx, wy)
        c = (65, 50, 35, 220)  # ink-brown
        # small cross
        pygame.draw.line(self._frame, c, (x - 3, y), (x + 3, y), 1)
        pygame.draw.line(self._frame, c, (x, y - 3), (x, y + 3), 1)

    def _draw_exit_marker(
        self,
        rect: pygame.Rect,
        w2m,
        map_size_px: tuple[int, int],
        off_x: float,
        off_y: float,
        sx: float,
        sy: float,
    ) -> None:
        # Place marker at rect center
        cx, cy = rect.centerx, rect.centery
        x, y = w2m(float(cx), float(cy))

        # Determine direction by proximity to map bounds (world px)
        map_w, map_h = map_size_px
        # Map bounds in "view" coords if centering on player is enabled
        left = off_x
        top = off_y
        right = off_x + (self.size_px - 2 * self.padding_px) / sx
        bottom = off_y + (self.size_px - 2 * self.padding_px) / sy

        # Use rect position vs view bounds to guess outward direction
        # (This stays generic; no region knowledge.)
        margin = 24.0
        dx = 0
        dy = 0
        if cx <= left + margin:
            dx = -1
        elif cx >= right - margin:
            dx = 1
        if cy <= top + margin:
            dy = -1
        elif cy >= bottom - margin:
            dy = 1

        # Default arrow direction if ambiguous: right
        if dx == 0 and dy == 0:
            dx = 1

        # Draw a tiny triangle/chevron (sideways triangle)
        col = (95, 80, 60, 200)
        pts = _triangle_points((x, y), dx, dy, size=5)
        pygame.draw.polygon(self._frame, col, pts)


# -----------------------------
# Helpers
# -----------------------------
def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _triangle_points(center: tuple[int, int], dx: int, dy: int, *, size: int = 5) -> list[tuple[int, int]]:
    """
    Returns points for a small triangle pointing (dx,dy).
    dx,dy in {-1,0,1}. If diagonal, we bias to the dominant axis.
    """
    x, y = center
    if abs(dx) >= abs(dy):
        # horizontal
        if dx >= 0:
            return [(x + size, y), (x - size, y - size), (x - size, y + size)]
        else:
            return [(x - size, y), (x + size, y - size), (x + size, y + size)]
    else:
        # vertical
        if dy >= 0:
            return [(x, y + size), (x - size, y - size), (x + size, y - size)]
        else:
            return [(x, y - size), (x - size, y + size), (x + size, y + size)]
