# ======================================================================
# FORGE XVII — BATTLEARENA: THE WIRING LAYER (SCENE + ROUTER)
#
# BattleArena is a *composition root* for battle.
# It wires systems together, forwards intent, and draws the scene.
#
# CORE LAW (XVII.25, binding):
#   UIFlow decides what happens.
#   BattleUI draws what it looks like.
#   BattleArena wires who talks to whom.
#   BattleController stays thin (legacy bridge / rules facade).
#
# BattleArena OWNS:
#   - Scene lifecycle: enter/update/draw/reset
#   - References to: BattleRuntime, BattleController, BattleUI, UIFlow, FXSystem
#   - World presentation: Stage/Actors, background/atmosphere/ambient, choreography hooks
#   - Input *routing* only (not intent rules):
#       - delegate menu/tactical/target-move to UIFlow
#       - delegate confirm/cancel (temporarily) to Arena helpers
#       - forward emitted BattleCommand to Runtime.ActionMapper
#
# BattleArena MUST NOT:
#   - Decide menu rules, selection rules, or targeting movement rules
#   - Build or interpret UI intent (belongs in UIFlow)
#   - Mutate battle truth (HP/MP/status/CTB), choose winners/losers, or run AI
#   - Re-introduce legacy cursor helpers (targeting is unified)
#   - Confirm/cancel are handled by UIFlow (targeting lifecycle). Arena only forwards commands.
# QUICK SMELL TEST:
#   If a change requires "if menu_layer..." or "if targeting..." logic here,
#   it belongs in UIFlow.
#
# If something feels like it belongs in two places, it belongs in UIFlow.
# ======================================================================

import os
import random
import pygame

from engine.battle.atmosphere import Atmosphere
from engine.battle.ambient_layer import AmbientLayer
from engine.battle.sprites import BattleSprite
from engine.battle.combatants import PlayerCombatant, EnemyCombatant
from engine.battle.skills.registry import initialize_defaults, get_for_user
from engine.router import EventRouter

from engine.stage.stage import Stage
from engine.stage.actor import StageActor
from engine.stage.choreo import Timeline
from engine.actors.character_sheet import new_default_party
from engine.actors.enemy_sheet import spawn_enemy_from_template

from engine.battle.battle_controller import BattleController, ChoreoRequest
from engine.battle.battle_ui import BattleUI
from engine.battle.ui_flow import UIFlow
from engine.battle.party_layout import compute_party_layout
from engine.battle.enemy_layout import compute_enemy_slots

from engine.battle.action_phases import ActionPhase
from engine.battle.battle_runtime import BattleRuntime
from engine.battle.battle_command import BattleCommand
from game.debug.debug_logger import log as battle_log
# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
BATTLE_SPRITE_SCALE = 0.2

BATTLE_BACKGROUNDS = {
    "grasslands": "grasslands.png",
    "desert": "desert.png",
    "night_forest": "night_forest.png",
    "mountain_pass": "mountain_pass.png",
    "ancient_ruins": "ancient_ruins.png",
    "default": "grasslands.png",
}

GROUND_PLANE_FRACTION = {
    "grasslands": 0.67,
    "desert": 0.82,
    "obelisk": 0.84,
    "default": 0.80,
}

class BattleArena:
    """
    BattleArena — Wiring Layer

    Receives raw events, delegates input intent to UIFlow,
    forwards BattleCommand to Runtime, and invokes BattleUI for rendering.

    BattleArena should not contain UI logic or selection rules.
    """

    def __init__(
        self,
        width: int,
        height: int,
        setia_frames,
        nyra_frames,
        kaira_frames,
        enemy_frames,
        fonts=None,
        region: str = "grasslands",
        phase: str = "day",
        router: EventRouter | None = None,
        party_instances=None,
        party_keys=None,
        enemy_party_id: str | None = None,
        seed: int | None = None,
        enemies=None,
    ):
        # ==================================================================
        # 1) Scene + Stage wiring
        # ==================================================================
        self.width = width
        self.height = height
        self.screen_width = width
        self.screen_height = height

        self.region = region if region in BATTLE_BACKGROUNDS else "default"
        self.phase = phase
        self.router = router
        # --------------------------------------------------
        # Arena lifecycle / debug latches (explicit, not getattr-spaghetti)
        # --------------------------------------------------
        self._dbg_printed_outcome: bool = False
        self._dbg_mapper_file: bool = False  # if you ever re-enable mapper file debug
        self.battle_outcome = None
        self.party_instances = party_instances  # external character sheet injection
        self.stage = Stage(width=self.width, height=self.height)

        # Ground plane for feet
        ground_frac = GROUND_PLANE_FRACTION.get(self.region, GROUND_PLANE_FRACTION["default"])
        self.ground_y = int(self.height * ground_frac)

        # Background + UI panel rects
        self.bg_rect = pygame.Rect(0, 0, self.screen_width, self.screen_height)
        self.ui_rect = pygame.Rect(
            0,
            int(self.screen_height * 0.65),
            self.screen_width,
            int(self.screen_height * 0.35),
        )

        # UIFlow owns UI logic (menu/tactical/targeting). Arena only wires.
        self.ui_flow = UIFlow()
        self._ui_menu_actor_id = None

        # Atmosphere / ambient / background
        self.atmosphere = Atmosphere(self.bg_rect.width, self.bg_rect.height)
        self.ambient = AmbientLayer(self.bg_rect.width, self.bg_rect.height)
        self.background = self.load_background(self.region)

        # Fonts
        if fonts is None:
            self.font_small = pygame.font.SysFont("consolas", 18)
            self.font_med = pygame.font.SysFont("consolas", 24)
            self.font_large = pygame.font.SysFont("consolas", 32)
        else:
            self.font_small, self.font_med, self.font_large = fonts

        # ==================================================================
        # 2) Party construction (data-driven; supports 1–4)
        # ==================================================================
        # Character sheet integration (stats & levels)
        if self.party_instances is not None:
            party_instances = self.party_instances
        else:
            party_instances = new_default_party(level=1)

        # Party keys default to classic trio
        if party_keys is None:
            party_keys = ["setia", "nyra", "kaira"]
        self.party_keys = party_keys

        # Temporary tuning so heroes don't obliterate everything (revisit later)
        OFFENSE_SCALE = 0.65

        def resolve_frames(key):
            if key == "setia":
                return setia_frames
            if key == "nyra":
                return nyra_frames
            if key == "kaira":
                return kaira_frames
            raise ValueError(f"Unknown party key: {key}")

        def _build_player_combatant(ci, frames, *, scale_factor=1.0):
            return PlayerCombatant(
                ci.name,
                ci.stats.max_hp,
                BattleSprite(
                    frames,
                    x=0,
                    y=0,
                    scale=BATTLE_SPRITE_SCALE * scale_factor,
                    facing="right",
                    idle_enabled=True,
                ),
                max_mp=ci.stats.max_mp,
                level=ci.level,
                stats={
                    "atk": int(ci.stats.atk * OFFENSE_SCALE),
                    "mag": int(ci.stats.mag * OFFENSE_SCALE),
                    "defense": ci.stats.defense,
                    "mres": ci.stats.mres,
                    "spd": ci.stats.spd,
                },
            )

        self.party = []
        for i, key in enumerate(self.party_keys[:4]):
            ci = party_instances[key]
            frames = resolve_frames(key)
            actor = _build_player_combatant(
                ci,
                frames,
                scale_factor=1.0,
            )
            self.party.append(actor)

        # ------------------------------------------------------------------
        # Optional legacy named access (TEMP shim; must not drive logic)
        # ------------------------------------------------------------------
        self.setia = next((a for a in self.party if a.name == "Setia"), None)
        self.nyra = next((a for a in self.party if a.name == "Nyra"), None)
        self.kaira = next((a for a in self.party if a.name == "Kaira"), None)

        # Add party actors to Stage (data-driven, no hardcoding)
        for a in self.party:
            self.stage.add_actor(StageActor(a.name, a.sprite, layer=20))

        # ==================================================================
        # 3) Enemies (provided by builder/harness; BattleArena does not invent content)
        # ==================================================================
        self.enemies = list(enemies or [])

        def _enemy_frames_for(template_id: str) -> list[str]:
            # Battle presentation owns sprite paths, not the harness.
            sprite_dir = os.path.join("assets", "sprites", "merchant_trail")
            return [
                os.path.join(sprite_dir, f"{template_id}__idle_00.png"),
                os.path.join(sprite_dir, f"{template_id}__idle_01.png"),
                os.path.join(sprite_dir, f"{template_id}__attack_00.png"),
            ]

        if not self.enemies:
            # enemy_party_id now means "species/pool id" (Step B)
            # For now, we treat it as a single template id (e.g. "trail_wolf").
            if enemy_party_id:
                from engine.actors.enemy_sheet import ENEMY_TEMPLATES
                templates = ENEMY_TEMPLATES

                if enemy_party_id not in templates:
                    raise KeyError(f"Unknown enemy_party_id/template_id: {enemy_party_id!r}")

                tpl = templates[enemy_party_id]

                rng = random.Random(seed)
                max_n = max(1, min(6, int(getattr(tpl, "max_number", 6))))
                pack_size = rng.randint(1, max_n)

                frames = _enemy_frames_for(enemy_party_id)

                for i in range(pack_size):
                    enemy_sprite = BattleSprite(
                        frames,
                        x=0,
                        y=0,
                        scale=BATTLE_SPRITE_SCALE,
                        facing="left",
                        idle_enabled=False,
                    )
                    name_suffix = chr(ord("A") + i)

                    enemy = spawn_enemy_from_template(
                        tpl,
                        sprite=enemy_sprite,
                        name_suffix=name_suffix,
                    )
                    self.enemies.append(enemy)

        # Stage registration
        for i, e in enumerate(self.enemies):
            self.stage.add_actor(StageActor(f"Enemy_{i}", e.sprite, layer=20))

        self._layout_party(flip=False)
        self._layout_enemies()

        # ==================================================================
        # 4) Ensure combatants have stable ids (CTBTimeline / Unified targeting)
        # ==================================================================
        all_combatants = list(self.party) + list(self.enemies)
        for idx, c in enumerate(all_combatants):
            if not hasattr(c, "id"):
                name = getattr(c, "name", None) or getattr(c, "label", None)
                if name is None:
                    name = f"combatant_{idx}"
                c.id = str(name)

        # ==================================================================
        # 5) Battle rules + runtime wiring
        # ==================================================================
        initialize_defaults()
        self.controller = BattleController(
            party=self.party,
            enemies=self.enemies,
            get_skills_for=get_for_user,
        )

        self.message = f"{self.party[self.controller.active_index].name} steps forward."

        self.runtime = BattleRuntime(self.party, self.enemies, router)
        self.runtime.arena = self

        # ==================================================================
        # 6) Visual subsystems (UI + FX)
        # ==================================================================
        self.timeline = Timeline()
        self.ui = BattleUI(
            ui_rect=self.ui_rect,
            font_small=self.font_small,
            font_med=self.font_med,
            font_large=self.font_large,
        )

        from engine.fx.system import FXSystem
        self.fx_system = FXSystem(router, viewport_size=(self.width, self.height))

    # ==================================================================
    # Region & background
    # ==================================================================
    def load_background(self, region: str):
        filename = BATTLE_BACKGROUNDS.get(region, BATTLE_BACKGROUNDS["default"])
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(base_dir))
        bg_path = os.path.join(project_root, "assets", "backgrounds", filename)

        if not os.path.exists(bg_path):
            battle_log("runtime", f"[BattleArena] Missing background for region '{region}' at {bg_path}")
            return None

        try:
            image = pygame.image.load(bg_path).convert()
            iw, ih = image.get_size()
            tw, th = self.bg_rect.size
            scale = max(tw / iw, th / ih)
            image = pygame.transform.smoothscale(image, (int(iw * scale), int(ih * scale)))
            return image
        except Exception as e:
            battle_log("runtime", f"[BattleArena] Failed to load background '{bg_path}': {e}")
            return None

    # ------------------------------------------------------------
    # Sprite lookup for FXSystem / camera
    # ------------------------------------------------------------
    def get_sprite_for_combatant(self, combatant):
        """
        Return the BattleSprite associated with a combatant, or None.

        This lets FXSystem (and other world-FX layers) find a world-space
        anchor point to spawn damage/heal numbers, auras, etc.
        """
        # Adjust attribute names depending on how your BattleSprite stores
        # its link back to the combatant (owner, combatant, model, etc.).
        for sprite in getattr(self, "party_sprites", []):
            owner = getattr(sprite, "owner", None) or getattr(
                sprite, "combatant", None
            )
            if owner is combatant:
                return sprite

        for sprite in getattr(self, "enemy_sprites", []):
            owner = getattr(sprite, "owner", None) or getattr(
                sprite, "combatant", None
            )
            if owner is combatant:
                return sprite

        return None

    def handle_event(self, event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        mapper = self.runtime.action_mapper
        if mapper.phase != ActionPhase.PLAYER_COMMAND:
            return

        actor_id = mapper.current_actor_id
        if not actor_id:
            return

        actor = self.runtime.session.get_combatant(actor_id)

        controller = self.controller
        skills = controller.skills if controller is not None else []

        handled, chosen_idx, cmd = self.ui_flow.handle_key(
            event.key,
            arena=self,
            controller=controller,
            actor=actor,
            skills=skills,
            flee_allowed=True,
        )

        if not handled:
            return

        if cmd is not None:
            mapper.on_player_command(cmd)
            return

        if chosen_idx is not None:
            skill_def = skills[chosen_idx]
            self.ui_flow.enter_targeting(
                self.runtime.session.party,
                self.runtime.session.enemies,
                controller=controller,
                actor=actor,
                skill_def=skill_def,
            )

    # ==================================================================
    # Turn handlers
    # ==================================================================
    def _apply_battle_event(self, event, is_enemy: bool):
        """
        Apply a resolved battle event to the view layer and notify the Runtime
        so it can emit FX / semantic events.
        """
        # Update the on-screen battle message
        self.message = event.message

        runtime = getattr(self, "runtime", None)
        if runtime is not None:
            runtime.emit_effects_for_event(
                event,
                is_enemy=is_enemy,
                arena=self,
            )

        # Choreography hook (dash, spell, etc.)
        if isinstance(event.choreo, ChoreoRequest):
            if event.choreo.kind == "melee" and event.actor is not None:
                from engine.battle.choreo_patterns import queue_melee_dash

                idx = event.choreo.primary_target_index or 0
                queue_melee_dash(
                    timeline=self.timeline,
                    stage=self.stage,
                    actor_id=event.actor.name,
                    enemy_index=idx,
                )
            # More kinds ("spell", "cinematic") can be added later.

    # ==================================================================
    # Reset battle
    # ==================================================================
    def _reset_battle(self):
        self.controller.reset_battle()
        self._layout_enemies()

        actor = self.party[self.controller.active_index]
        self.ui_flow.begin_actor_menu(arena=self, actor=actor)

        self.message = f"{actor.name} steps forward."

    # ==================================================================
    # Update loop
    # ==================================================================
    def update(self, dt: float) -> None:
        # --------------------------------------------------
        # Stage + ambient
        # --------------------------------------------------
        self.stage.update(dt)
        self.ambient.update(dt)

        # --------------------------------------------------
        # Battle runtime tick (only if initialized)
        # --------------------------------------------------
        runtime = getattr(self, "runtime", None)
        if runtime is not None and self.controller is not None:
            runtime.update(dt, self.controller)
        if runtime is None:
            return

        mapper = runtime.action_mapper

        # --------------------------------------------------
        # UIFlow menu entry hook: fire once per actor turn
        # --------------------------------------------------
        if mapper.phase == ActionPhase.PLAYER_COMMAND and mapper.current_actor_id:
            if self._ui_menu_actor_id != mapper.current_actor_id:
                self._ui_menu_actor_id = mapper.current_actor_id
                actor = self.runtime.session.get_combatant(mapper.current_actor_id)
                self.ui_flow.begin_actor_menu(arena=self, actor=actor)
        else:
            self._ui_menu_actor_id = None

        # --------------------------------------------------
        # DEBUG: Battle Outcome (one-shot)
        # --------------------------------------------------
        if mapper.phase == ActionPhase.BATTLE_END and not self._dbg_printed_outcome:
            self._dbg_printed_outcome = True
            outcome = getattr(self.runtime, "battle_outcome", None)
            print("=== BATTLE OUTCOME ===")
            print(outcome)
            if outcome is not None:
                print("result:", getattr(outcome, "result", None))
                print("script_flags:", getattr(outcome, "script_flags", None))
            print("======================")
            g = self.runtime.gains
            print("consumed totals:", g.consumed_totals())

        # --------------------------------------------------
        # Region particles
        # --------------------------------------------------
        if random.random() < 0.04:
            phase = self.phase
            if phase in ("day", "dawn"):
                self.ambient.spawn(1, (255, 255, 180), speed=8, drift=10, lifetime=2.5)
            elif phase == "sunset":
                self.ambient.spawn(1, (255, 160, 120), speed=6, drift=12, lifetime=2.0)
            elif phase == "night":
                if self.region == "night_forest":
                    self.ambient.spawn(1, (120, 255, 200), speed=3, drift=15, lifetime=3.0)
                else:
                    self.ambient.spawn(1, (150, 200, 255), speed=3, drift=10, lifetime=3.0)

        # --------------------------------------------------
        # Choreography timeline (dash, etc.)
        # --------------------------------------------------
        self.timeline.update(dt)

        # --------------------------------------------------
        # Enemy dissolve fade-outs
        # --------------------------------------------------
        for enemy in self.enemies:
            if not enemy.alive and enemy.dissolve_time > 0.0:
                enemy.dissolve_time = max(0.0, enemy.dissolve_time - dt)
                t = enemy.dissolve_time / enemy.dissolve_duration  # 1 → 0
                spr = enemy.sprite
                if spr is not None and hasattr(spr, "set_dissolve_factor"):
                    spr.set_dissolve_factor(t)

    # ==================================================================
    # Target cursor helpers (visual)
    # ==================================================================
    def _get_cursor_target_combatant(self):
        # Unified targeting: UIFlow owns hover truth.
        hover_id = getattr(self.ui_flow.state, "hover_id", None)
        if not hover_id:
            return None
        try:
            return self.runtime.session.get_combatant(hover_id)
        except Exception:
            return None

    def _draw_target_cursor(self, scene: pygame.Surface) -> None:
        """
        Draw a small floating triangle above the currently selected
        combatant's sprite (ally or enemy).
        """
        target = self._get_cursor_target_combatant()
        if target is None:
            return

        sprite = getattr(target, "sprite", None)
        if sprite is None:
            return

        # Base position: we assume sprite.x, sprite.y are around the feet / center.
        # We'll place the cursor a bit above the sprite's y position.
        x = int(getattr(sprite, "x", 0))
        y = int(getattr(sprite, "y", 0))

        # Vertical offset so the triangle floats above the head/body.
        # Tweak this if it feels too high/low.
        offset_y = 60

        top = (x, y - offset_y)
        left = (x - 12, y - offset_y + 18)
        right = (x + 12, y - offset_y + 18)

        # Bright, readable triangle. You can change the color later if you like.
        color = (255, 255, 0)  # yellow
        pygame.draw.polygon(scene, color, [top, left, right])

    # ==================================================================
    # Draw with post-process camera pan/zoom
    # ==================================================================
    def draw(self, surface: pygame.Surface):
        # 1) Draw the whole scene to an offscreen surface
        scene = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

        # Stage (background + actors)
        self.stage.background = self.background
        self.stage.draw(scene)

        # Atmosphere overlay
        overlay = self.atmosphere.build_overlay(
            (self.phase, 0.0), self.region, strength=1.0
        )
        scene.blit(overlay, self.bg_rect.topleft)

        # Ambient particles
        self.ambient.draw(scene, offset=self.bg_rect.topleft)

        # After drawing characters, draw the targeting cursor on top
        if self.ui_flow.state.mode == "targeting":
            self._draw_target_cursor(scene)

        # --------------------------------------------------------------
        # Camera pan/zoom: read from FXSystem if present
        # --------------------------------------------------------------
        zoom = 1.0
        total_off = pygame.Vector2(0, 0)

        fx_system = getattr(self, "fx_system", None)
        if fx_system is not None:
            camera_rig = getattr(fx_system, "camera_rig", None)
            if camera_rig is not None:
                zoom = getattr(camera_rig, "zoom", 1.0)

                # camera_rig.offset may already be a Vector2; normalize it
                offset = getattr(camera_rig, "offset", pygame.Vector2(0, 0))
                if not isinstance(offset, pygame.math.Vector2):
                    offset = pygame.Vector2(offset)

                quake = (
                    fx_system.get_camera_offset()
                    if hasattr(fx_system, "get_camera_offset")
                    else pygame.Vector2(0, 0)
                )
                total_off = offset + quake

        if abs(zoom - 1.0) < 1e-3 and total_off.length_squared() < 1e-2:
            # No special camera; blit directly
            surface.blit(scene, (0, 0))
        else:
            w, h = scene.get_size()
            new_w = int(w * zoom)
            new_h = int(h * zoom)
            zoomed = pygame.transform.smoothscale(scene, (new_w, new_h))

            # Center zoomed image, then apply camera offset
            dest_x = (w - new_w) // 2 + int(total_off.x)
            dest_y = (h - new_h) // 2 + int(total_off.y)
            surface.blit(zoomed, (dest_x, dest_y))

        # 3) UI on top (not affected by camera zoom/pan)
        self.ui.draw(surface, self)

    # ==================================================================
    # Sprite positioning
    # ==================================================================
    def _layout_party(self, *, flip: bool = False) -> None:
        layout = compute_party_layout(
            bg_width=self.bg_rect.width,
            ground_y=self.ground_y,
            flip=flip,
        )
        slots = layout.slots

        # Slot mapping (your doctrine)
        # 0: Setia (front)
        # 1: Nyra (bottom/middle)
        # 2: Kaira (back)
        # 3: Guest (top)
        desired_slot_by_key = {
            "setia": 0,
            "nyra": 1,
            "kaira": 2,
            "guest": 3,  # optional catch-all
        }

        party_combatants = getattr(self, "party", None) or []

        def combatant_key(c) -> str:
            # Try the common places a key might live
            for attr in ("key", "id", "name"):
                v = getattr(c, attr, None)
                if isinstance(v, str) and v:
                    return v.lower()

            tpl = getattr(c, "template", None)
            for attr in ("key", "id", "name"):
                v = getattr(tpl, attr, None)
                if isinstance(v, str) and v:
                    return v.lower()

            return ""

        # Place each combatant into the correct slot based on key
        for c in party_combatants:
            k = combatant_key(c)
            if not k:
                continue

            # If it isn't one of the big three, treat it as guest slot 3
            slot_idx = desired_slot_by_key.get(k, 3)
            if slot_idx >= len(slots):
                continue

            spr = getattr(c, "sprite", None)
            if spr is None:
                continue

            x, y = slots[slot_idx]
            spr.x = x
            spr.y = y

            if hasattr(spr, "facing"):
                spr.facing = layout.facing

    def _layout_enemies(self):
        slots = compute_enemy_slots(
            count=len(self.enemies),
            bg_width=self.bg_rect.width,
            ground_y=self.ground_y,
            height=self.height,
        )
        for enemy, (x, y) in zip(self.enemies, slots):
            if enemy.sprite:
                enemy.sprite.x = x
                enemy.sprite.y = y
