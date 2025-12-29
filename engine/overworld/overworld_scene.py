# engine/overworld/overworld_scene.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import math
import pygame

from engine.overworld.assets import OverworldAssets
from engine.overworld.mode7_renderer_px import Mode7Camera
from engine.overworld.camera.controller import CameraController
from engine.overworld.camera.sequence import CameraSequence, CameraSequenceContext
from engine.overworld.tiled_loader import (
    bake_tmx_ground_surface,
    load_world_rects,
    load_landmark_defs,
    WorldRects,
    LandmarkDef,
)
from engine.overworld.presenters.overhead_presenter import OverheadPresenter
from engine.overworld.presenters.mode7_presenter import Mode7Presenter
from engine.overworld.regions.registry import get_region
from engine.overworld.regions.builder import build_region_runtime
from engine.overworld.encounters.registry import get_encounter_profile
from engine.overworld.encounters.controller import EncounterController, BattleRequest
from engine.overworld.draw_hud import OverworldHUD
from engine.overworld.narrative.registry import get_on_enter_sequence
from engine.overworld.minimap.renderer import MinimapRenderer, MinimapExit
from pathlib import Path

@dataclass
class OverworldConfig:
    region_id: str = "velastra_highlands"
    tmx_path: Optional[str] = None  # optional override for quick testing

    window_size: tuple[int, int] = (1024, 768)
    internal_size: tuple[int, int] = (512, 384)

    # TMX object layers
    collision_layer_name: str = "Collision"
    exits_layer_name: str = "Exits"
    landmarks_layer_name: str = "Landmarks"

    allow_strafe: bool = True
    spawn_px: tuple[int, int] = (600, 340)

    # Determinism (optional)
    seed: Optional[int] = None

@dataclass
class Landmark:
    image: pygame.Surface
    pos: pygame.Vector2  # world pixel coords (same space as TMX bake)

    # TMX authoring
    scale_mul: float = 1.0
    sway: bool = False
    base_offset_px: int = 0  # optional: raise/lower feet on ground

    # Safety / artistic bounds
    min_scale: float = 0.05     # below this: skip drawing
    max_scale: float = 8.0      # above this: clamp
    max_size_px: int = 1024     # cap on smoothscale width/height (each axis)

class OverworldScene:
    def __init__(self, cfg: OverworldConfig) -> None:
        # -----------------------------
        # Config + Region
        # -----------------------------
        self.cfg = cfg
        self.debug_draw = False

        self.region = get_region(cfg.region_id)

        tmx_path = cfg.tmx_path or self.region.tmx_path
        self.tmx_path = tmx_path  # keep current TMX path for minimap + transitions

        # -----------------------------
        # Exits (region-authored intent)
        # -----------------------------
        self.exit_map = {ex.id: ex for ex in self.region.exits}
        self.flags: set[str] = set()  # minimal world-state bag for gating

        # -----------------------------
        # Encounters (controller is region-scoped)
        # -----------------------------
        self.encounters: EncounterController | None = None
        self.pending_battle: BattleRequest | None = None
        self.debug_encounters: bool = True

        # -----------------------------
        # Assets (persist across transitions)
        # -----------------------------
        self.assets = OverworldAssets(root_dir="assets")

        # -----------------------------
        # Load collision + exits (TMX truth)
        # -----------------------------
        self.world: WorldRects = load_world_rects(
            tmx_path,
            collision_layer_name=cfg.collision_layer_name,
            exits_layer_name=cfg.exits_layer_name,
            debug_layers=False,
        )
        self.map_w, self.map_h = self.world.map_size_px
        self.last_trigger: str = ""

        # -----------------------------
        # Bake visuals (TMX tile layers -> surface)
        # -----------------------------
        self.ground_texture = bake_tmx_ground_surface(
            tmx_path,
            exclude_layers=[cfg.collision_layer_name, cfg.exits_layer_name],
        ).convert()

        # -----------------------------
        # Internal render surface
        # -----------------------------
        iw, ih = cfg.internal_size
        self.internal_surface = pygame.Surface((iw, ih)).convert()

        self.hud = OverworldHUD()
        self.encounter_eye_size = (128, 128)
        self.hud_margin = 16

        # -----------------------------
        # Minimap (parchment + TMX abstraction)
        # -----------------------------
        minimap_dir = Path(__file__).resolve().parent / "minimap"
        self.minimap = MinimapRenderer(
            size_px=160,
            padding_px=12,
            parchment_path=minimap_dir / "parchment.png",
        )

        # -----------------------------
        # Camera
        # -----------------------------
        self.camera = Mode7Camera()
        self.camera.x = float(cfg.spawn_px[0])
        self.camera.y = float(cfg.spawn_px[1])
        self.camera.angle = 0.0
        # Your existing code relies on camera.horizon/focal_len defaults from Mode7Camera.
        self.camera_ctl = CameraController(camera=self.camera)
        self.camera_ctl.set_follow_target(x=self.camera.x, y=self.camera.y)
        self._cam_seq: CameraSequence | None = None

        # -----------------------------
        # Player
        # -----------------------------
        self.player = pygame.Rect(cfg.spawn_px[0], cfg.spawn_px[1], 24, 24)
        self.pos = pygame.Vector2(self.player.x, self.player.y)

        # -----------------------------
        # Motion params
        # -----------------------------
        self.speed = 250.0
        self.wind_t = 0.0
        self.sun_angle = 0.0

        # -----------------------------
        # Region Runtime (resolved + mutable)
        # -----------------------------
        internal_w = self.internal_surface.get_width()
        self.region_rt = build_region_runtime(
            self.region,
            assets=self.assets,  # <-- NOTE: self.assets, not a local
            internal_w=internal_w,
            horizon_y=int(self.camera.horizon),
            seed=getattr(cfg, "seed", None),
        )
        print("[AERIAL]", self.region_rt.aerial_actor)
        self._rebuild_encounters_for_region()

        # -----------------------------
        # Landmarks (TMX-authored overlays)
        # -----------------------------
        self.landmarks = self._load_landmarks_from_tmx(tmx_path)

        # -----------------------------
        # Presenter wiring (draw-only)
        # -----------------------------
        self.presenter = self._build_presenter()
        
        # Clamp/sync once at boot
        self._clamp_player_to_map()
        self.camera_ctl.set_follow_target(x=self.pos.x, y=self.pos.y)
        self.camera_ctl.release(blend_s=0.0)
        self.camera_ctl.update(0.0)

        self._on_region_enter()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_presenter(self):
        ptype = getattr(self.region, "presenter_type", "mode7")

        if ptype == "overhead":
            return OverheadPresenter(
                internal_surface=self.internal_surface,
                camera=self.camera,  # still single authoritative camera pose
                ground_texture=self.ground_texture,
                get_player_rect=lambda: self.player,
                get_landmarks=lambda: self.landmarks,
                get_aerial_actor=lambda: self.region_rt.aerial_actor,
            )

        # default: mode7
        return Mode7Presenter(
            internal_surface=self.internal_surface,
            camera=self.camera,
            ground_texture=self.ground_texture,
            region_rt=self.region_rt,
            get_wind_t=lambda: self.wind_t,
            get_celestial_angle=lambda kind: self.sun_angle if kind == "sun" else 0.0,
            get_landmarks=lambda: self.landmarks,
            fog_strength=160,
        )

    def _load_landmarks_from_tmx(self, tmx_path: str) -> list[Landmark]:
        defs: list[LandmarkDef] = load_landmark_defs(
            tmx_path,
            landmarks_layer_name=self.cfg.landmarks_layer_name,
            strict=False,
        )

        img_cache: dict[str, pygame.Surface] = {}
        out: list[Landmark] = []

        for d in defs:
            # LandmarkDef.image_path is expected to be a file path string.
            img = img_cache.get(d.image_path)
            if img is None:
                # Keep consistent with your existing landmark pipeline:
                img = pygame.image.load(d.image_path).convert_alpha()
                img_cache[d.image_path] = img

            out.append(
                Landmark(
                    image=img,
                    pos=pygame.Vector2(d.pos.x, d.pos.y),
                    scale_mul=float(getattr(d, "scale", 1.0)),
                    sway=bool(getattr(d, "sway", False)),
                    base_offset_px=int(getattr(d, "base_offset_px", 0)),
                    min_scale=float(getattr(d, "min_scale", 0.05)),
                    max_scale=float(getattr(d, "max_scale", 8.0)),
                    max_size_px=int(getattr(d, "max_size_px", 1024)),
                )
            )
        return out

    # ------------------------------------------------------------------
    # Exit detection + transitions
    # ------------------------------------------------------------------

    def _check_exit(self) -> Optional[str]:
        for name, rect in self.world.exits.items():
            if self.player.colliderect(rect):
                if self.last_trigger != name:
                    self.last_trigger = name
                    return name
                return None
        self.last_trigger = ""
        return None

    def _try_use_exit(self, exit_id: str) -> None:
        ex = self.exit_map.get(exit_id)
        if ex is None:
            print(f"[EXITS] TMX exit {exit_id!r} has no matching ExitSpec in region {self.region.id!r}")
            return

        # Flag gating (truth checked against current flags bag)
        if getattr(ex, "requires_flag", None) and ex.requires_flag not in self.flags:
            print(f"[EXITS] Exit {exit_id!r} blocked (missing flag {ex.requires_flag!r})")
            return

        self._transition_to_region(ex.to_region_id, to_spawn=getattr(ex, "to_spawn", None))

    def _transition_to_region(self, region_id: str, *, to_spawn: str | None = None) -> None:
        print(f"[EXITS] Transition: {self.region.id!r} -> {region_id!r} (spawn={to_spawn!r})")

        # 1) swap region spec
        self.region = get_region(region_id)
        tmx_path = self.region.tmx_path
        self.tmx_path = tmx_path

        # 2) refresh exits mapping
        self.exit_map = {ex.id: ex for ex in self.region.exits}

        # 3) reload world truth + visuals from TMX
        self.world = load_world_rects(
            tmx_path,
            collision_layer_name=self.cfg.collision_layer_name,
            exits_layer_name=self.cfg.exits_layer_name,
            debug_layers=False,
        )
        self.map_w, self.map_h = self.world.map_size_px
        self.last_trigger = ""

        self.ground_texture = bake_tmx_ground_surface(
            tmx_path,
            exclude_layers=[self.cfg.collision_layer_name, self.cfg.exits_layer_name],
        ).convert()

        self.landmarks = self._load_landmarks_from_tmx(tmx_path)

        # 4) rebuild region runtime (sky/celestial/aerial/silhouettes)
        internal_w = self.internal_surface.get_width()
        self.region_rt = build_region_runtime(
            self.region,
            assets=self.assets,
            internal_w=internal_w,
            horizon_y=int(self.camera.horizon),
            seed=getattr(self.cfg, "seed", None),
        )
        self._rebuild_encounters_for_region()
        print("[AERIAL]", self.region_rt.aerial_actor)

        # 5) re-anchor player spawn (named spawns are TMX-authored truth)
        spawn_px = self.cfg.spawn_px
        spawn_angle = None

        if to_spawn:
            spawn = self.world.spawns.get(to_spawn)
            if spawn:
                spawn_px = spawn.rect.center
                spawn_angle = spawn.angle
                print(f"[EXITS] spawn {to_spawn!r} resolved to {spawn_px}, angle={spawn_angle}")
            else:
                print(f"[EXITS] spawn {to_spawn!r} not found; using cfg.spawn_px")

        self.player.x, self.player.y = spawn_px
        if spawn_angle is not None:
            self.camera_ctl.snap_angle(spawn_angle)

        # 6) clamp + sync camera
        self._clamp_player_to_map()

        # Always set follow target to the new spawn
        self.camera_ctl.set_follow_target(x=float(self.pos.x), y=float(self.pos.y))

        # Snap camera to follow baseline first (so takeover seeds correctly)
        self.camera_ctl.release(blend_s=0.0)
        self.camera_ctl.update(0.0)

        # If the region wants script authority by default, borrow it now
        if self.region.default_camera_mode == "script":
            self.camera_ctl.takeover()
        
        # 7) rebuild presenter so it points at the new runtime + ground texture
        self.presenter = self._build_presenter()
        
        self._on_region_enter()

    def _on_region_enter(self) -> None:
        seq = get_on_enter_sequence(
            region_id=self.region.id,
            x=float(self.pos.x),
            y=float(self.pos.y),
            angle=float(self.camera.angle),
            flags=self.flags,
        )
        self._cam_seq = seq

    # ------------------------------------------------------------------
    # Movement + collisions
    # ------------------------------------------------------------------

    def _resolve_collisions(self, dx: float, dy: float) -> None:
        # Axis-separated collision resolution
        self.player.x += int(dx)
        for wall in self.world.collision_rects:
            if self.player.colliderect(wall):
                if dx > 0:
                    self.player.right = wall.left
                elif dx < 0:
                    self.player.left = wall.right

        self.player.y += int(dy)
        for wall in self.world.collision_rects:
            if self.player.colliderect(wall):
                if dy > 0:
                    self.player.bottom = wall.top
                elif dy < 0:
                    self.player.top = wall.bottom

        self.pos.x = float(self.player.x)
        self.pos.y = float(self.player.y)

        self._clamp_player_to_map()

    def _clamp_player_to_map(self) -> None:
        # Keep player within map bounds
        self.player.x = max(0, min(self.player.x, self.map_w - self.player.w))
        self.player.y = max(0, min(self.player.y, self.map_h - self.player.h))
        self.pos.x = float(self.player.x)
        self.pos.y = float(self.player.y)

    def _rebuild_encounters_for_region(self) -> None:
        """Rebuild encounter controller when region changes."""
        self.encounters = None
        self.pending_battle = None
        enc_ref = getattr(self.region, "encounters", None)
        if enc_ref is None:
            return

        pid = getattr(enc_ref, "profile_id", None)
        if not isinstance(pid, str) or not pid.strip():
            print(f"[ENCOUNTER] Invalid EncounterProfileRef.profile_id on region {self.region.id!r}: {pid!r}")
            return

        profile = get_encounter_profile(pid)
        if profile is None:
            print(f"[ENCOUNTER] Encounter profile_id not found: {pid!r} (region={self.region.id!r})")
            return

        # NOTE: for now we’ll assume RegionRuntime exposes rng as self.region_rt.rng
        self.encounters = EncounterController(profile=profile, rng=self.region_rt.rng)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        # -----------------------------
        # Region runtime ticking (always)
        # -----------------------------
        self.region_rt.update(dt)

        # -----------------------------
        # Ambient clocks (still scene-owned for now)
        # -----------------------------
        self.wind_t += dt
        self.sun_angle += dt * 0.05
        keys = pygame.key.get_pressed()

        # -----------------------------
        # Camera intent (always safe)
        # If you want a hard freeze of camera turning during pending battle, gate this.
        # -----------------------------
        turn_dir = float(int(keys[pygame.K_e]) - int(keys[pygame.K_q]))  # +1 right, -1 left
        if self.pending_battle is None and getattr(self.region, "presenter_type", "mode7") == "mode7":
            self.camera_ctl.add_turn_intent(dt=dt, turn_dir=turn_dir)

        # -----------------------------
        # Gameplay updates (freeze when battle is pending)
        # -----------------------------
        if self.pending_battle is None:
            move_f = int(keys[pygame.K_w] or keys[pygame.K_UP]) - int(keys[pygame.K_s] or keys[pygame.K_DOWN])
            if self.cfg.allow_strafe:
                move_s = int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(keys[pygame.K_a] or keys[pygame.K_LEFT])
            else:
                move_s = 0

            ptype = getattr(self.region, "presenter_type", "mode7")

            if ptype == "overhead":
                # World-axis controls: W = up (y-), S = down (y+), A = left (x-), D = right (x+)
                forward = pygame.Vector2(0, -1)
                right = pygame.Vector2(1, 0)
            else:
                # Mode7: camera-relative FPS-style controls
                a = self.camera.angle
                sin_a = math.sin(a)
                cos_a = math.cos(a)

                forward = pygame.Vector2(sin_a, -cos_a)
                right = pygame.Vector2(cos_a, sin_a)

                # Keep your established Mode7 feel
                forward = -forward
                right = -right

            v = forward * move_f + right * move_s
            if v.length_squared() > 0:
                v = v.normalize()

            dx = v.x * self.speed * dt
            dy = v.y * self.speed * dt

            # movement magnitude for encounter meter
            moved_px = (dx * dx + dy * dy) ** 0.5

            self._resolve_collisions(dx, dy)

            # Encounters update only when we actually moved AND no battle is pending
            req = None
            if (
                self.pending_battle is None
                and self.encounters is not None
                and moved_px > 0.0
            ):
                req = self.encounters.update(
                    region_id=self.region.id,
                    moved_px=moved_px,
                    flags=self.flags,
                    debug=self.debug_encounters,
                )
            if req is not None:
                self.pending_battle = req
                if hasattr(self.encounters, "threat"):
                    self.encounters.threat = 1.0
                print("[ENCOUNTER] PENDING BATTLE:", req)
                # Don't return: we still want camera/sequence to tick and land smoothly.

            # Exit check happens ONCE, after movement/collision resolution.
            if self.pending_battle is None:
                exit_id = self._check_exit()
                if exit_id:
                    self._try_use_exit(exit_id)

        # -----------------------------
        # Camera follow target + sequences (always)
        # -----------------------------
        self.camera_ctl.set_follow_target(x=float(self.pos.x), y=float(self.pos.y))

        if self._cam_seq is not None and not self._cam_seq.done:
            self._cam_seq.update(
                CameraSequenceContext(camera_ctl=self.camera_ctl, flags=self.flags),
                dt,
            )

        # Apply final camera pose for this frame
        self.camera_ctl.update(dt)

    def clear_pending_battle(self) -> None:
        self.pending_battle = None
        # optional: also reset encounter meter if you want post-battle grace
        if self.encounters is not None:
            self.encounters.reset()

    def draw(self, screen: pygame.Surface, dt: float) -> None:
        self.presenter.draw(screen, dt)

        if not self.debug_draw:
            return

        # Debug overlay (minimal)
        font = pygame.font.SysFont("consolas", 16)
        y = 10
        screen.blit(font.render(f"REGION: {self.region.id}", True, (0, 255, 0)), (10, y))
        y += 18
        screen.blit(font.render(f"EXITS: {list(self.world.exits.keys())}", True, (0, 255, 0)), (10, y))
        y += 18
        screen.blit(font.render(f"LAST EXIT: {self.last_trigger}", True, (255, 255, 0)), (10, y))

    def draw_hud(self, screen: pygame.Surface) -> None:
        self.hud.draw(screen=screen, scene=self)

        # Minimap (quiet overlay, parchment-backed)
        mm = self.minimap.render(
            tmx_path=self.tmx_path,
            player_world_px=(float(self.pos.x), float(self.pos.y)),
            exits=[MinimapExit(rect=r) for r in self.world.exits.values()],
            pois=None,
            center_on_player=False,
        )

        margin = 16
        x = screen.get_width() - mm.get_width() - margin
        y = margin
        screen.blit(mm, (x, y))

    def toggle_debug(self) -> None:
        self.debug_draw = not self.debug_draw
