# engine/overworld/presenters/mode7_presenter.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Callable
import math
import pygame

from engine.overworld.mode7_renderer_px import Mode7Camera, draw_mode7_floor_video_pixelarray
from engine.overworld.weather.spec import SkyGradientSpec, HazeBandSpec
from engine.overworld.celestial.spec import CelestialProfile, CelestialObjectSpec
from engine.overworld.celestial.starfield import get_starfield
from engine.overworld.celestial.render import draw_celestial_object

_sky_gradient_cache: dict[tuple[int, int, tuple[int, int, int], tuple[int, int, int]], pygame.Surface] = {}

# -----------------------------
# Sky state (runtime) — presenter-owned
# -----------------------------

@dataclass
class SkyLayer:
    surf: pygame.Surface
    speed_px_s: float = 0.0      # how fast it drifts (pixels/sec)
    yaw_factor: float = 0.0      # how much it responds to turning
    y: int = 0                   # vertical placement
    alpha: int = 255             # optional transparency

@dataclass
class SkyState:
    t: float
    layers: list[SkyLayer]

    # new (optional)
    gradient: Optional[SkyGradientSpec] = None
    haze: tuple[HazeBandSpec, ...] = ()

# -----------------------------
# Landmark projection (matches floorcaster math)
# -----------------------------

def project_landmark(
    wx: float,
    wy: float,
    cam: Mode7Camera,
    screen_w: int,
    screen_h: int,
) -> tuple[int, int, float] | None:
    """
    Project world point (wx, wy) onto the Mode-7 floor in a way that matches
    draw_mode7_floor_video_pixelarray's exact math.

    Returns (screen_x, base_y, depth_z) where base_y is the scanline where
    the feet touch the ground.
    """
    # Convert to "texture-space" offsets (because floor uses cam.scale)
    lx = (wx - cam.x) / cam.scale
    ly = (wy - cam.y) / cam.scale

    sin_a = math.sin(cam.angle)
    cos_a = math.cos(cam.angle)

    # Invert the floor's rotation: [x,y] = R(-a) * [px,py]
    ux = lx * cos_a + ly * sin_a
    uy = -lx * sin_a + ly * cos_a

    # Floor uses:
    #   y = t + focal
    #   z = t + alt
    # => y = z - alt + focal
    # And also: [x,y] = z * [ux,uy]
    # So: z*uy = z - alt + focal  =>  z = (focal - alt) / (uy - 1)
    denom = (uy - 1.0)
    if abs(denom) < 1e-6:
        return None

    z = (cam.focal_len - cam.alt) / denom
    if z <= 0:
        return None

    x = z * ux

    # t = z - alt, and j = horizon + t
    base_y = int(cam.horizon + (z - cam.alt))

    # Floor uses x = (half_w - i) + vanish  =>  i = half_w + vanish - x
    half_w = screen_w * 0.5
    sx = int(half_w + cam.vanish_shift - x)

    if sx < -screen_w or sx > screen_w * 2:
        return None

    if base_y < 0 or base_y >= screen_h:
        return None

    return sx, base_y, z


# -----------------------------
# Presenter
# -----------------------------

class Mode7Presenter:
    """
    Pure rendering. No collisions, no exits, no flag mutation.
    Owns sky animation + landmark projection/draw order.
    """

    def __init__(
        self,
        *,
        internal_surface: pygame.Surface,
        camera: Mode7Camera,
        ground_texture: pygame.Surface,
        region_rt,  # RegionRuntime (duck-typed to avoid import cycles)
        get_wind_t,
        get_celestial_angle: Callable[[str], float],
        get_landmarks,
        fog_strength: int = 160,
    ) -> None:
        self.internal_surface = internal_surface
        self.camera = camera
        self.ground_texture = ground_texture

        # Runtime bundle (authoritative mutable region state)
        self.region_rt = region_rt

        # callable hooks so presenter doesn't own gameplay state
        self._get_wind_t = get_wind_t
        self.get_celestial_angle = get_celestial_angle
        self._get_landmarks = get_landmarks

        self.fog_strength = fog_strength

    # ---------- SKY ----------
    def _draw_sky_gradient(self, surf: pygame.Surface) -> None:
        """
        Draw a smooth vertical sky gradient (cached).
        This replaces the per-frame line drawing that can create streak/banding artifacts.
        """
        grad = getattr(self.region_rt.sky, "gradient", None)
        if grad is None:
            # fallback to your default solid color
            surf.fill((120, 185, 255))
            return

        w, h = surf.get_size()

        # Expect gradient as ((r,g,b),(r,g,b)) or object with top/bottom
        if isinstance(grad, tuple) and len(grad) == 2:
            top = tuple(grad[0])
            bot = tuple(grad[1])
        else:
            top = tuple(getattr(grad, "top", (120, 185, 255)))
            bot = tuple(getattr(grad, "bottom", (120, 185, 255)))

        key = (w, h, top, bot)
        cached = _sky_gradient_cache.get(key)
        if cached is None:
            gsurf = pygame.Surface((w, h)).convert()

            # Fill via PixelArray for smoothness + speed (one-time cost)
            px = pygame.PixelArray(gsurf)
            try:
                tr, tg, tb = top
                br, bg, bb = bot
                if h <= 1:
                    color = gsurf.map_rgb((tr, tg, tb))
                    px[:, 0] = color
                else:
                    for y in range(h):
                        t = y / (h - 1)
                        r = int(tr + (br - tr) * t)
                        g = int(tg + (bg - tg) * t)
                        b = int(tb + (bb - tb) * t)
                        px[:, y] = gsurf.map_rgb((r, g, b))
            finally:
                del px

            cached = gsurf
            _sky_gradient_cache[key] = cached

        surf.blit(cached, (0, 0))

    def _draw_haze_bands(self, surf: pygame.Surface, *, horizon_y: int) -> None:
        haze = getattr(self.region_rt.sky, "haze", ()) or ()
        if not haze:
            return

        iw, ih = surf.get_size()

        def _clamp_u8(x: int) -> int:
            return 0 if x < 0 else 255 if x > 255 else x

        # Slightly sky-tinted haze (less chalky than pure white)
        R, G, B = 200, 220, 235

        for band in haze:
            band_h = max(1, int(getattr(band, "height_px", 0) or 0))
            if band_h <= 0:
                continue

            y_off = int(getattr(band, "y_from_horizon", 0) or 0)

            # Convention:
            #   +y_from_horizon => ABOVE horizon
            #   -y_from_horizon => legacy/explicit (can still place above if negative)
            if y_off >= 0:
                y0 = horizon_y - y_off
            else:
                y0 = horizon_y + y_off

            # Skip if completely off-screen
            if y0 >= ih or (y0 + band_h) <= 0:
                continue

            a_top = _clamp_u8(int(getattr(band, "alpha_top", 0) or 0))
            a_bot = _clamp_u8(int(getattr(band, "alpha_bottom", 0) or 0))

            # Build a 1px-wide vertical alpha ramp, then scale to full width.
            col = pygame.Surface((1, band_h), pygame.SRCALPHA)

            # Faster than set_at() in a Python loop
            px = pygame.PixelArray(col)
            try:
                for yy in range(band_h):
                    t = 0.0 if band_h == 1 else (yy / (band_h - 1))
                    a = _clamp_u8(int(a_top + (a_bot - a_top) * t))
                    px[0, yy] = col.map_rgb((R, G, B, a))
            finally:
                del px

            haze_surf = pygame.transform.smoothscale(col, (iw, band_h))
            surf.blit(haze_surf, (0, y0))

    def _get_celestial_object(self, kind: str):
        celestial = self.region_rt.celestial
        if celestial is None:
            return None
        for obj in celestial.objects:
            if obj.kind == kind:
                return obj
        return None

    def _project_celestial_x(self, *, angle_rad: float, screen_w: int) -> int:
        """
        Map a sky-dome angle to screen X using camera yaw.
        Returns an X in [0, screen_w].
        """
        rel_angle = float(angle_rad) - float(self.camera.angle)
        rel_angle = (rel_angle + math.pi) % (2 * math.pi) - math.pi
        return int((rel_angle / math.pi) * (screen_w * 0.5) + (screen_w * 0.5))

    def _resolve_celestial_angle(self, obj: CelestialObjectSpec) -> float:
        """
        Resolve an object's sky angle in radians.
        Presenter owns this because it references runtime hooks (e.g., get_celestial_angle).
        Phase 4 supports only:
        - angle_mode="world"  (hook-driven, current behavior)
        - angle_mode="fixed"  (spec-driven)
        """
        if obj.angle_mode == "fixed":
            if obj.fixed_angle_rad is None:
                # Fail soft: treat missing fixed angle as 0.0 rather than crash during iteration.
                return 0.0
            return float(obj.fixed_angle_rad)

        # Default: "world" (current sun behavior)
        return float(self.get_celestial_angle(obj.kind))

    def draw_sky(self, internal: pygame.Surface, dt: float) -> None:
        iw, ih = internal.get_size()
        internal.fill((120, 185, 255))

        self._draw_sky_gradient(internal)

        horizon_y = int(self.camera.horizon)
        HORIZON_OVERLAP = 20

        # -------------------------------------------------
        # Stars (celestial sky-field) — after sky fill, before everything else
        # -------------------------------------------------
        stars_spec = self._get_celestial_object("stars")
        if stars_spec is not None and stars_spec.alpha > 0:
            sky_h = max(1, horizon_y)
            stars = get_starfield(width=iw, height=sky_h, alpha=stars_spec.alpha)

            yaw = float(self.camera.angle)
            drift = int((yaw * 12.0) % iw)

            internal.blit(stars, (-drift, 0))
            internal.blit(stars, (-drift + iw, 0))

        # -------------------------------------------------
        # Haze (weather)
        # -------------------------------------------------
        self._draw_haze_bands(internal, horizon_y=horizon_y)

        # -------------------------------------------------
        # Celestial objects (non-stars) — draw by layer
        # -------------------------------------------------
        def _draw_celestials_for_layer(layer_name: str) -> None:
            if self.region_rt.celestial is None:
                return

            # Phase parity: keep the same Y placement for all objects for now
            sky_y = int(horizon_y * 0.15)

            for obj in self.region_rt.celestial.objects:
                if obj.kind == "stars":
                    continue
                if obj.alpha <= 0:
                    continue
                if obj.draw_layer != layer_name:
                    continue

                angle = self._resolve_celestial_angle(obj)
                x = self._project_celestial_x(angle_rad=angle, screen_w=iw)

                draw_celestial_object(
                    surface=internal,
                    spec=obj,
                    x=x,
                    y=sky_y,
                    sprite=None,                 # presenter can supply later when sprites are introduced
                    enable_flares=(obj.kind == "sun"),  # sun-only for now
                )

        # Draw behind-cloud celestials before clouds so clouds can occlude them
        _draw_celestials_for_layer("behind_clouds")

        # -------------------------------------------------
        # Clip sky above horizon: birds + clouds live here
        # -------------------------------------------------
        old_clip = internal.get_clip()
        internal.set_clip(pygame.Rect(0, 0, iw, horizon_y + HORIZON_OVERLAP))
        try:
            if self.region_rt.aerial_actor is not None:
                # Actor owns its own runtime state + visuals
                self.region_rt.aerial_actor.draw(
                    internal,
                    dt=dt,
                    horizon_y=horizon_y,
                    cam_angle=float(self.camera.angle),
                    sky_t=float(self.region_rt.sky.t),
                )

            # Clouds / sky layers
            for layer in self.region_rt.sky.layers:
                surf = layer.surf
                tw, th = surf.get_size()
                if tw <= 0 or th <= 0:
                    continue

                x_time = self.region_rt.sky.t * layer.speed_px_s
                x_yaw = self.camera.angle * layer.yaw_factor
                x0 = -int((x_time + x_yaw) % tw)

                base_y = horizon_y - th
                breath = math.sin(self.region_rt.sky.t * 0.15 + layer.y * 0.01) * 1.5
                y = base_y + int(layer.y + breath)
                y = min(y, horizon_y + HORIZON_OVERLAP - th)

                x = x0
                while x < iw:
                    internal.blit(surf, (x, y))
                    x += tw
        finally:
            internal.set_clip(old_clip)

        # Draw in-front celestials after clouds so they sit above them
        _draw_celestials_for_layer("in_front_of_clouds")

# ---------- FULL PIPELINE ----------
# Render order is intentional. This function is the single, authoritative draw orchestration for Mode7Presenter.
#
# Layer contract:
#   1) Sky + clouds (includes celestials and aerial actor)
#   2) FAR_DEEP silhouettes (tier 3) rendered *behind* the ground plane
#   3) Ground plane (Mode7 floor)
#   4) Foreground silhouettes (tiers 0/1/2) rendered *in front of* the ground plane
#   5) Landmarks (camera-projected sprites), depth-sorted far -> near
#   6) Final upscale internal buffer -> screen
#
# NOTE: Tier semantics are region-authored. The presenter only enforces which tiers render in which pass.
# - tier 3: FAR_DEEP (background horizon forms that must sit behind the floor)
# - tiers 0/1/2: near/mid/far silhouettes rendered after the floor

    def draw(self, screen: pygame.Surface, dt: float) -> None:
        internal = self.internal_surface
        sw, sh = screen.get_size()
        iw, ih = internal.get_size()

        # Clear the frame buffer every frame to avoid persistence artifacts from partial draws.
        internal.fill((0, 0, 0))

        # 1) SKY PASS
        # Owns: gradient/haze, clouds, celestials (behind/in front of clouds), aerial actor.
        self.draw_sky(internal, dt)

        # 2) BACKGROUND SILHOUETTES (FAR_DEEP)
        # These are horizon bands that must sit behind the ground plane.
        self.region_rt.silhouettes.draw(
            internal,
            horizon_y=int(self.camera.horizon),
            cam_angle=float(self.camera.angle),
            include_tiers={3},
        )

        # 3) GROUND PLANE (MODE7 FLOOR)
        draw_mode7_floor_video_pixelarray(
            internal,
            self.ground_texture,
            self.camera,
            step=2,
            wrap=False,
            fog_strength=self.fog_strength,
        )

        # 4) FOREGROUND SILHOUETTES (NEAR/MID/FAR)
        # These sit on top of the floor and help sell depth/horizon layering.
        self.region_rt.silhouettes.draw(
            internal,
            horizon_y=int(self.camera.horizon),
            cam_angle=float(self.camera.angle),
            include_tiers={0, 1, 2},
        )

        # 5) LANDMARKS (DEPTH-SORTED SPRITES)
        # Landmarks are camera-projected and depth-sorted far -> near for correct overlap.
        to_draw: list[tuple[float, int, int, object]] = []
        for lm in self._get_landmarks():
            proj = project_landmark(lm.pos.x, lm.pos.y, self.camera, iw, ih)
            if proj is None:
                continue
            sx, base_y, depth = proj
            to_draw.append((depth, sx, base_y, lm))

        # Sort far -> near (smaller depth first)
        to_draw.sort(key=lambda t: t[0])

        wind_t = float(self._get_wind_t())

        for depth, sx, base_y, lm in to_draw:
            # Scale based on distance (depth) and landmark-specific multiplier.
            base_scale = (depth / self.camera.focal_len) * lm.scale_mul

            # Clamp scale to authored bounds.
            if base_scale < lm.min_scale:
                continue
            if base_scale > lm.max_scale:
                base_scale = lm.max_scale

            img = lm.image
            spr_w = max(1, int(img.get_width() * base_scale))
            spr_h = max(1, int(img.get_height() * base_scale))

            # Optional subtle sway (wind-driven). We only sway the canopy for trees.
            dx = 0
            if lm.sway:
                phase = (wind_t * 0.6) + (lm.pos.x * 0.01) + (lm.pos.y * 0.007)
                dx = int(math.sin(phase) * 2)

            # Hard cap: keep any single landmark from becoming a giant surface allocation.
            max_px = lm.max_size_px
            if spr_w > max_px or spr_h > max_px:
                k = min(max_px / spr_w, max_px / spr_h)
                spr_w = max(1, int(spr_w * k))
                spr_h = max(1, int(spr_h * k))

            spr = pygame.transform.smoothscale(img, (spr_w, spr_h))

            # Anchor the sprite by its "base" (feet/root) so it sits on the projected ground properly.
            x0 = sx - spr_w // 2
            y0 = (base_y - spr_h) + lm.base_offset_px

            if not lm.sway:
                internal.blit(spr, (x0, y0))
                continue

            # Canopy-only sway:
            # - bottom stays rigid (trunk)
            # - top shifts by dx (leaves/canopy)
            CANOPY_RATIO = 0.45
            cut_y = int(spr_h * CANOPY_RATIO)
            cut_y = max(1, min(spr_h - 1, cut_y))

            bottom_rect = pygame.Rect(0, cut_y, spr_w, spr_h - cut_y)
            internal.blit(spr.subsurface(bottom_rect), (x0, y0 + cut_y))

            top_rect = pygame.Rect(0, 0, spr_w, cut_y)
            internal.blit(spr.subsurface(top_rect), (x0 + dx, y0))

        # 6) PRESENTATION: UPSCALE INTERNAL BUFFER -> SCREEN
        # Internal surface is low-res for speed/texture; upscale once at the end.
        screen.blit(pygame.transform.scale(internal, (sw, sh)), (0, 0))

