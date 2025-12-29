# engine/overworld/aerial_actor/crow.py
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple, List

import pygame

from engine.overworld.regions.spec import AerialActorSpec
from engine.overworld.aerial_actor.api import AerialActor


# -----------------------------
# Config (author-tunable)
# -----------------------------

@dataclass(frozen=True)
class CrowConfig:
    anchor_world_x: float = 0.0
    anchor_world_y: float = 0.0

    radius_x: float = 140.0
    radius_y: float = 70.0
    angular_speed: float = 0.22

    rot_jitter_deg: float = 2.0
    alpha_center: int = 180
    alpha_amp: int = 14
    scale_center: float = 0.6
    scale_amp: float = 0.01

    anim_pattern: Tuple[int, ...] = (2, 1, 0, 2, 1)
    anim_fps: float = 6.0

    z: int = 50

# -----------------------------
# Runtime actor (Protocol: draw-only)
# -----------------------------

class CrowAerialActor(AerialActor):
    """
    Overhead crow silhouette circling an anchor point.
    Implements the AerialActor protocol: presenter calls draw(...),
    and the actor advances itself using dt.
    """

    kind: str = "crow"

    def __init__(
        self,
        *,
        frames: Sequence[pygame.Surface],
        cfg: CrowConfig,
        rng: random.Random,
    ) -> None:
        if len(frames) < 3:
            raise ValueError("CrowAerialActor expects 3+ frames.")
        self.frames = list(frames)
        self.cfg = cfg
        self.rng = rng
        self.center_world = pygame.Vector2(self.cfg.anchor_world_x, self.cfg.anchor_world_y)
        self.target_center_world = self.center_world.copy()

        self.center_blend_t = 1.0
        self.center_blend_dur = 1.0

        self.switch_timer = self.rng.uniform(4.0, 9.0)  # time until next course pick
        self.direction = self.rng.choice([-1.0, 1.0])

        # Per-course orbit characteristics (start from cfg)
        self.course_rx = self.cfg.radius_x
        self.course_ry = self.cfg.radius_y
        self.course_speed = self.cfg.angular_speed

        # Time + phases
        self.t = 0.0
        self.phase = self.rng.uniform(0.0, math.tau)
        self.rot_phase = self.rng.uniform(0.0, math.tau)
        self.alpha_phase = self.rng.uniform(0.0, math.tau)
        self.scale_phase = self.rng.uniform(0.0, math.tau)

        # Animation
        self.anim_timer = 0.0
        self.anim_i = 0

        # Exposed for optional sorting
        self.z = cfg.z
        self.pos_world = pygame.Vector2(self.cfg.anchor_world_x, self.cfg.anchor_world_y)
        self.vel_world = pygame.Vector2(0, 0)
        self.has_entered_view = False
        self.spawn_margin = 48.0  # how far offscreen it starts/ends
        self.facing_deg = 0.0
        self.facing_init = False

    def draw(
        self,
        surf: pygame.Surface,
        *,
        cam_angle: float,
        horizon_y: int,
        dt: float,
        sky_t: float = 0.0,
        view_left: float = 0.0,
        view_top: float = 0.0,
        world_w: float = 0.0,
        world_h: float = 0.0,
    ) -> None:
        self.t += float(dt)

        iw, ih = surf.get_size()
        mw = float(world_w)
        mh = float(world_h)
        margin = float(getattr(self, "spawn_margin", 48.0))

        # Need valid bounds to do smart spawns
        if mw <= 0.0 or mh <= 0.0:
            return

        # Helpers (local to draw to keep it self-contained)
        def clamp(v: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, v))

        def in_view(sx: float, sy: float) -> bool:
            return 0.0 <= sx <= float(iw) and 0.0 <= sy <= float(ih)

        def respawn() -> None:
            # Choose a spawn edge just outside the current view rect (world coords)
            side = self.rng.choice(["top", "bottom", "left", "right"])

            if side == "top":
                sx = self.rng.uniform(-margin, float(iw) + margin)
                sy = -margin
                ex = self.rng.uniform(-margin, float(iw) + margin)
                ey = float(ih) + margin
            elif side == "bottom":
                sx = self.rng.uniform(-margin, float(iw) + margin)
                sy = float(ih) + margin
                ex = self.rng.uniform(-margin, float(iw) + margin)
                ey = -margin
            elif side == "left":
                sx = -margin
                sy = self.rng.uniform(-margin, float(ih) + margin)
                ex = float(iw) + margin
                ey = self.rng.uniform(-margin, float(ih) + margin)
            else:  # right
                sx = float(iw) + margin
                sy = self.rng.uniform(-margin, float(ih) + margin)
                ex = -margin
                ey = self.rng.uniform(-margin, float(ih) + margin)

            # Convert spawn/exit points from VIEW space -> WORLD space
            wx0 = float(view_left) + sx
            wy0 = float(view_top) + sy
            wx1 = float(view_left) + ex
            wy1 = float(view_top) + ey

            # Clamp to world bounds with a little breathing room
            wx0 = clamp(wx0, 0.0, mw)
            wy0 = clamp(wy0, 0.0, mh)
            wx1 = clamp(wx1, 0.0, mw)
            wy1 = clamp(wy1, 0.0, mh)

            self.pos_world.update(wx0, wy0)

            # Velocity aimed toward exit
            dx = wx1 - wx0
            dy = wy1 - wy0
            v = pygame.Vector2(dx, dy)
            if v.length_squared() < 1e-6:
                v = pygame.Vector2(1.0, 0.0)
            v = v.normalize()

            speed = self.rng.uniform(55.0, 95.0)  # px/sec in world space (tune)
            self.vel_world = v * speed

            # Reset view gate
            self.has_entered_view = False

            # Desync phases a bit so each pass feels different
            self.rot_phase = self.rng.uniform(0.0, math.tau)
            self.alpha_phase = self.rng.uniform(0.0, math.tau)
            self.scale_phase = self.rng.uniform(0.0, math.tau)

        # If we have no velocity yet, spawn the first pass
        if self.vel_world.length_squared() < 1e-6:
            respawn()

        # Advance position (world space)
        self.pos_world += self.vel_world * float(dt)

        # Convert to internal/view space
        sx = float(self.pos_world.x) - float(view_left)
        sy = float(self.pos_world.y) - float(view_top)

        # Track whether we've entered view yet
        if not self.has_entered_view and in_view(sx, sy):
            self.has_entered_view = True

        # Once it has been seen, respawn after it leaves the view with margin
        if self.has_entered_view:
            if (sx < -margin) or (sx > float(iw) + margin) or (sy < -margin) or (sy > float(ih) + margin):
                respawn()
                # recompute sx/sy after respawn
                sx = float(self.pos_world.x) - float(view_left)
                sy = float(self.pos_world.y) - float(view_top)

        # Facing from velocity (prevents moonwalk issues entirely)
        base_angle_deg = math.degrees(math.atan2(self.vel_world.y, self.vel_world.x))
        base_angle_deg += 90.0  # your sprite-forward alignment (use your correct offset)

        if not self.facing_init:
            self.facing_deg = base_angle_deg
            self.facing_init = True
        else:
            # unwrap: choose the shortest way around the circle
            delta = (base_angle_deg - self.facing_deg + 180.0) % 360.0 - 180.0
            self.facing_deg += delta * 0.35

        # now add wobble on top (small, won't cause wrap jumps)
        wob = math.sin(self.rot_phase + self.t * 0.83)
        angle_deg = self.facing_deg + (float(self.cfg.rot_jitter_deg) * wob)

        # Alpha drift
        a = int(self.cfg.alpha_center) + int(int(self.cfg.alpha_amp) * math.sin(self.alpha_phase + self.t * 0.41))
        a = max(0, min(255, a))

        # Scale drift (smaller crow suggestion: tune cfg.scale_center)
        s = float(self.cfg.scale_center) + (float(self.cfg.scale_amp) * math.sin(self.scale_phase + self.t * 0.29))

        # Animate pattern
        self.anim_timer += float(dt)
        step = 1.0 / max(1e-6, float(self.cfg.anim_fps))
        while self.anim_timer >= step:
            self.anim_timer -= step
            self.anim_i = (self.anim_i + 1) % len(self.cfg.anim_pattern)

        frame_idx = int(self.cfg.anim_pattern[self.anim_i])
        frame_idx = max(0, min(frame_idx, len(self.frames) - 1))
        base = self.frames[frame_idx]

        # Transform + draw
        img = base

        if abs(s - 1.0) > 1e-3:
            w = max(1, int(base.get_width() * s))
            h = max(1, int(base.get_height() * s))
            img = pygame.transform.smoothscale(base, (w, h))

        if abs(angle_deg) > 1e-3:
            img = pygame.transform.rotate(img, -angle_deg)

        if a != 255:
            img = img.copy()
            img.set_alpha(a)

        surf.blit(img, img.get_rect(center=(int(sx), int(sy))))

# -----------------------------
# Builder hook (spec -> runtime)
# -----------------------------

def _f(p: Mapping[str, Any], key: str, default: float) -> float:
    try:
        return float(p.get(key, default))
    except Exception:
        return float(default)


def _i(p: Mapping[str, Any], key: str, default: int) -> int:
    try:
        return int(p.get(key, default))
    except Exception:
        return int(default)


def build_crow(
    spec: AerialActorSpec,
    *,
    assets,
    internal_w: int,
    horizon_y: int,
    rng: Optional[random.Random] = None,
) -> AerialActor:
    """
    Factory hook: translate declarative AerialActorSpec -> CrowAerialActor runtime.

    Expected spec.params:
      frames: ["sprites/overworld/crow_00.png", ...]  (3+)
      optional tuning keys matching CrowConfig fields
    """
    if spec.params is None:
        raise ValueError("Crow AerialActorSpec requires params")

    p: Mapping[str, Any] = spec.params
    r = rng or random.Random()

    frame_paths = p.get("frames")
    if not isinstance(frame_paths, list) or len(frame_paths) < 3:
        raise ValueError("crow params['frames'] must be a list of 3+ image paths")

    # Use canonical assets cache/loader
    frames: List[pygame.Surface] = [assets.image(str(path)) for path in frame_paths]

    # Parse anim pattern (list/tuple -> tuple[int,...])
    ap = p.get("anim_pattern", (2, 1, 0, 2, 1))
    if isinstance(ap, (list, tuple)) and len(ap) > 0:
        anim_pattern = tuple(int(x) for x in ap)
    else:
        anim_pattern = (2, 1, 0, 2, 1)

    cfg = CrowConfig(
        anchor_world_x=_f(p, "anchor_world_x", 0.0),
        anchor_world_y=_f(p, "anchor_world_y", 0.0),

        radius_x=_f(p, "radius_x", 140.0),
        radius_y=_f(p, "radius_y", 80.0),
        angular_speed=_f(p, "angular_speed", 0.22),

        rot_jitter_deg=_f(p, "rot_jitter_deg", 2.0),
        alpha_center=_i(p, "alpha_center", 180),
        alpha_amp=_i(p, "alpha_amp", 14),

        scale_center=_f(p, "scale_center", 0.75),
        scale_amp=_f(p, "scale_amp", 0.02),

        anim_pattern=anim_pattern,
        anim_fps=_f(p, "anim_fps", 6.0),

        z=_i(p, "z", 50),
    )

    return CrowAerialActor(frames=frames, cfg=cfg, rng=r)
