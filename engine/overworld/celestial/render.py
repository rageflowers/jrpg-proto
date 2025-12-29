# engine/overworld/celestial/render.py
from __future__ import annotations

from typing import Dict, Tuple
import pygame

from engine.overworld.celestial.spec import CelestialObjectSpec


# -------------------------------------------------
# Celestial render cache
# -------------------------------------------------
# We cache small translucent surfaces so nothing is created per-frame.
# Keys are integers only (fast, stable).
_DiscKey = Tuple[int, int]              # (radius_px, alpha)
_HaloKey = Tuple[int, int, int]         # (radius_px, halo_strength, alpha)
_GlareKey = Tuple[int, int]             # (radius_px, alpha)
_FlareKey = Tuple[int, int]             # (radius_px, alpha)

_disc_cache: Dict[_DiscKey, pygame.Surface] = {}
_halo_cache: Dict[_HaloKey, pygame.Surface] = {}
_glare_cache: Dict[_GlareKey, pygame.Surface] = {}
_flare_cache: Dict[_FlareKey, pygame.Surface] = {}
_SpriteKey = Tuple[str, int, int]  # (sprite_path, diameter_px, alpha)
_sprite_cache: Dict[_SpriteKey, pygame.Surface] = {}

def _clamp_u8(x: int) -> int:
    return 0 if x < 0 else 255 if x > 255 else x


def _get_disc_surface(*, radius_px: int, alpha: int) -> pygame.Surface:
    r = max(1, int(radius_px))
    a = _clamp_u8(int(alpha))
    key = (r, a)
    surf = _disc_cache.get(key)
    if surf is not None:
        return surf

    s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    # warm sun disc color (matches your current vibe)
    pygame.draw.circle(s, (255, 250, 235, a), (r, r), r)

    _disc_cache[key] = s
    return s


def _get_halo_surface(*, radius_px: int, halo_strength: int, alpha: int) -> pygame.Surface:
    """
    Soft outer glow / halo.
    halo_strength behaves like a "range" control (0 = none).
    """
    r = max(1, int(radius_px))
    hs = max(0, int(halo_strength))
    a0 = _clamp_u8(int(alpha))

    key = (r, hs, a0)
    surf = _halo_cache.get(key)
    if surf is not None:
        return surf

    if hs <= 0 or a0 <= 0:
        # Return a tiny transparent surface so caller can blit safely
        s = pygame.Surface((1, 1), pygame.SRCALPHA)
        _halo_cache[key] = s
        return s

    # Keep this “like today” while still spec-driven.
    # Larger halo_strength yields a bigger, slightly brighter halo.
    pad = 26
    extra = min(64, hs // 8)
    outer = r + pad + extra

    s = pygame.Surface((outer * 2, outer * 2), pygame.SRCALPHA)
    glow_color = (255, 235, 190)

    # Radial falloff in coarse rings (cheap; cached)
    # Preserve the current stepped look (r..r+26 in steps of 4) but allow scaling.
    ring_span = max(12, min(80, pad + extra))
    step = 4

    for rr in range(r + ring_span, r, -step):
        t = 1.0 - (rr - r) / max(1, ring_span)
        # Base halo is subtle; overall alpha respects spec.alpha
        aa = int((22 * t) * (a0 / 255.0))
        if aa <= 0:
            continue
        pygame.draw.circle(s, (*glow_color, _clamp_u8(aa)), (outer, outer), rr)

    _halo_cache[key] = s
    return s


def _get_glare_surface(*, radius_px: int, alpha: int) -> pygame.Surface:
    """
    Big soft glare bloom centered on the sun.
    """
    r = max(1, int(radius_px))
    a0 = _clamp_u8(int(alpha))
    key = (r, a0)
    surf = _glare_cache.get(key)
    if surf is not None:
        return surf

    glare_r = r * 6
    s = pygame.Surface((glare_r * 2, glare_r * 2), pygame.SRCALPHA)

    # Matches current “(255,255,255,18)” but scaled by alpha.
    aa = int(18 * (a0 / 255.0))
    if aa > 0:
        pygame.draw.circle(s, (255, 255, 255, _clamp_u8(aa)), (glare_r, glare_r), glare_r)

    _glare_cache[key] = s
    return s


def _get_flare_surface(*, screen_w: int, screen_h: int, sun_x: int, sun_y: int, radius_px: int, alpha: int) -> pygame.Surface:
    """
    Lens flare nodes along the line from sun -> center.
    This is *screen-sized* and therefore NOT cached by screen dims here.
    We keep it optional: caller decides if/when to use it.

    Note: We’re not caching this yet because it depends on sun position.
    In Phase 1, you can disable flares entirely to keep parity + performance.
    """
    flare = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    a0 = _clamp_u8(int(alpha))
    if a0 <= 0:
        return flare

    cx, cy = screen_w * 0.5, screen_h * 0.55
    dx, dy = (cx - sun_x), (cy - sun_y)

    r = max(1, int(radius_px))
    nodes = [
        (0.20, int(r * 0.55), 22),
        (0.45, int(r * 0.35), 18),
        (0.70, int(r * 0.25), 14),
        (0.92, int(r * 0.18), 10),
    ]
    for t, rr, aa in nodes:
        fx = int(sun_x + dx * t)
        fy = int(sun_y + dy * t)
        aa2 = int(aa * (a0 / 255.0))
        if aa2 <= 0:
            continue
        pygame.draw.circle(flare, (255, 255, 255, _clamp_u8(aa2)), (fx, fy), max(2, rr))

    return flare

def _get_scaled_sprite(
    *,
    sprite: pygame.Surface,
    sprite_path: str,
    diameter_px: int,
    alpha: int,
) -> pygame.Surface:
    """
    Return a cached, scaled, alpha-applied sprite for celestial rendering.

    IMPORTANT:
    - Renderer does NOT load sprites.
    - 'sprite' is an already-loaded pygame.Surface supplied by the presenter.
    - 'sprite_path' is used ONLY as a stable cache key identity.
    """
    d = max(1, int(diameter_px))
    a = _clamp_u8(int(alpha))
    key = (sprite_path, d, a)

    cached = _sprite_cache.get(key)
    if cached is not None:
        return cached

    # Scale to requested diameter (celestial objects are defined by radius_px)
    scaled = pygame.transform.smoothscale(sprite, (d, d)).convert_alpha()

    # Apply alpha without mutating the shared asset surface
    if a < 255:
        scaled.set_alpha(a)

    _sprite_cache[key] = scaled
    return scaled

def draw_celestial_object(
    *,
    surface: pygame.Surface,
    spec: CelestialObjectSpec,
    x: int,
    y: int,
    sprite: pygame.Surface | None = None,
    enable_flares: bool = True,
) -> None:
    """
    Draw a celestial object at screen-space (x, y).

    - No projection.
    - No yaw logic.
    - No time logic.
    - Uses cached surfaces for disc/halo/glare.
    - Optional sprite support:
        * spec.sprite_path indicates intent
        * presenter supplies 'sprite' (already loaded Surface)
        * renderer caches scaled+alpha variants
    """
    if spec.alpha <= 0:
        return

    # -----------------------------------------
    # Sprite path (optional) — presenter supplies the surface
    # -----------------------------------------
    if spec.sprite_path and sprite is not None:
        diameter = max(1, int(spec.radius_px) * 2)

        # Cache scaled+alpha sprite variants keyed by (sprite_path, diameter, alpha)
        # NOTE: requires _get_scaled_sprite() + _sprite_cache in this module.
        spr = _get_scaled_sprite(
            sprite=sprite,
            sprite_path=spec.sprite_path,
            diameter_px=diameter,
            alpha=spec.alpha,
        )

        sw, sh = spr.get_size()
        surface.blit(spr, (x - sw // 2, y - sh // 2))

        # Optional: allow halo overlay even for sprites (good for moon glow / comet head)
        if spec.halo_strength > 0:
            halo = _get_halo_surface(
                radius_px=spec.radius_px,
                halo_strength=spec.halo_strength,
                alpha=spec.alpha,
            )
            hw, hh = halo.get_size()
            if hw > 1 and hh > 1:
                surface.blit(halo, (x - hw // 2, y - hh // 2))

        return

    # -----------------------------------------
    # Disc/Halo/Glare fallback (sun/moon style)
    # -----------------------------------------
    kind = spec.kind

    # For Phase 1, treat sun+moon as disc/halo/glare.
    # (Other kinds become meaningful later without touching the presenter.)
    if kind in ("sun", "moon"):
        # Halo behind disc
        if spec.halo_strength > 0:
            halo = _get_halo_surface(
                radius_px=spec.radius_px,
                halo_strength=spec.halo_strength,
                alpha=spec.alpha,
            )
            hw, hh = halo.get_size()
            if hw > 1 and hh > 1:
                surface.blit(halo, (x - hw // 2, y - hh // 2))

        # Disc
        disc = _get_disc_surface(radius_px=spec.radius_px, alpha=spec.alpha)
        dw, dh = disc.get_size()
        surface.blit(disc, (x - dw // 2, y - dh // 2))

        # Glare over everything (subtle bloom)
        glare = _get_glare_surface(radius_px=spec.radius_px, alpha=spec.alpha)
        gw, gh = glare.get_size()
        if gw > 1 and gh > 1:
            surface.blit(glare, (x - gw // 2, y - gh // 2))

        # Optional flares (screen-sized; can disable for perf/parity)
        if enable_flares:
            sw, sh = surface.get_size()
            flare = _get_flare_surface(
                screen_w=sw,
                screen_h=sh,
                sun_x=x,
                sun_y=y,
                radius_px=spec.radius_px,
                alpha=spec.alpha,
            )
            surface.blit(flare, (0, 0))

        return

    # -----------------------------------------
    # Other kinds: no-op for now (Phase 1 focus)
    # -----------------------------------------
    return


