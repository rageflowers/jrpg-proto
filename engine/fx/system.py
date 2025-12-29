# engine/fx/system.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Deque, List, Optional, Tuple
from collections import deque

import pygame

from engine.router import EventRouter
from engine.battle.battle_controller import BattleEvent
from game.debug.debug_logger import log as battle_log
from .primitives import FXPrimitives
from .camera import CameraRig
from . import universalFX


# ---------------------------------------------------------------------------
# Timed FX events
# ---------------------------------------------------------------------------


@dataclass
class FXEvent:
    """
    A timed FX event managed by FXSystem.

    kind:     string identifier (e.g. "tint_screen", "quake").
    start:    absolute time in seconds when the event begins.
    duration: length of time in seconds.
    data:     arbitrary metadata for the specific event kind.
    """
    kind: str
    start: float
    duration: float
    data: Dict[str, Any] = field(default_factory=dict)

    @property
    def end(self) -> float:
        return self.start + self.duration

    def is_active(self, t: float) -> bool:
        return self.start <= t < self.end

    def is_expired(self, t: float) -> bool:
        return t >= self.end


@dataclass
class DamageNumber:
    """World-space floating combat text (damage/heal numbers).

    This is managed by FXSystem and rendered in battle space (affected
    by camera and stage), not by the HUD.
    """
    text: str
    pos: pygame.Vector2
    kind: str = "damage"  # e.g. "damage", "heal", "dot"
    lifetime: float = 0.8
    age: float = 0.0
    velocity: pygame.Vector2 = field(
        default_factory=lambda: pygame.Vector2(0.0, -30.0)
    )

    def update(self, dt: float) -> None:
        self.age += dt
        self.pos += self.velocity * dt

    @property
    def alive(self) -> bool:
        return self.age < self.lifetime

    @property
    def color(self) -> Tuple[int, int, int]:
        """Basic palette based on kind.

        We can later extend this by element, crit flag, etc.
        """
        if self.kind == "heal":
            return (80, 255, 80)
        if self.kind == "damage":
            return (255, 80, 80)
        # Default / miscellaneous (DOT, etc.)
        return (255, 255, 255)


# ---------------------------------------------------------------------------
# FXSystem — router, camera, primitives, and overlays
# ---------------------------------------------------------------------------


class FXSystem:
    """
    Central FX hub (Forge XVII.7 ready).

    Responsibilities:
      - Subscribe to battle events via EventRouter.
      - Maintain a small timed FX event queue.
      - Own the cinematic camera rig (pan/zoom).
      - Own a separate quake offset for hits.
      - Provide primitive FX APIs (tint, pulses, quake, particles).
      - Composite FX layers after the battle scene is drawn.
      - Manage world-space floating combat text (damage/heal numbers).
      - Expose debug helpers used by test_battle_arena.py.

    Camera contract with BattleArena:

        fx = arena.fx_system

        # Update/draw each frame:
        fx.update(dt)
        arena.draw_scene_with_camera(fx.camera_rig, fx.get_camera_offset())
        fx.draw(screen)   # overlays

    BattleArena never mutates camera state directly; it just *reads*
    from FXSystem.
    """

    def __init__(self, router: EventRouter, viewport_size: Tuple[int, int]) -> None:
        self.router = router
        self.viewport_size = viewport_size
        battle_log("fx", f"FXSystem.__init__: router={router}")        # FX timebase
        self.time: float = 0.0

        # Transparent FX layers
        self.tint_surface = self._make_layer_surface()
        self.aura_surface = self._make_layer_surface()
        self.particle_surface = self._make_layer_surface()

        # Camera systems
        # - camera_rig: cinematic pan/zoom (skill punch-ins, sweeps, etc.)
        # - fx_camera_offset: transient shake from primitives.quake
        self.camera_rig = CameraRig()
        self.fx_camera_offset = pygame.Vector2(0, 0)

        # Low-level primitives operate on these shared surfaces/offsets
        self.primitives = FXPrimitives(
            tint_surface=self.tint_surface,
            aura_surface=self.aura_surface,
            particle_surface=self.particle_surface,
            camera_offset=self.fx_camera_offset,
        )

        # Timed FX event list
        self._events: List[FXEvent] = []

        # Debug tracking (Forge XIII.6 compatible)
        self.debug_enabled: bool = False
        self.debug_auto_print: bool = False
        self._recent_events: Deque[Dict[str, Any]] = deque(maxlen=64)

        # World-space floating combat text (damage/heal numbers)
        self.damage_numbers: List[DamageNumber] = []
        # Lazily-created font for damage numbers
        self._damage_font: Optional[pygame.font.Font] = None

        # Wire up router subscriptions
        self._register_handlers()

    # ------------------------------------------------------------------
    # Layer helpers
    # ------------------------------------------------------------------

    def _make_layer_surface(self) -> pygame.Surface:
        w, h = self.viewport_size
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        return surf

    def _clear_layers(self) -> None:
        """
        Reset all FX layers at the start of each frame.
        """
        self.tint_surface.fill((0, 0, 0, 0))
        self.aura_surface.fill((0, 0, 0, 0))
        self.particle_surface.fill((0, 0, 0, 0))

    # ------------------------------------------------------------------
    # Main loop hooks
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """
        Advance FX time and update all active events.

        Call once per frame *before* BattleArena.draw().
        """
        self.time += dt

        # Reset quake each frame; active "quake" events will modify it.
        self.fx_camera_offset.update(0.0, 0.0)

        # Clear FX layers for fresh drawing
        self._clear_layers()

        # Tick events
        t = self.time
        still_alive: List[FXEvent] = []

        for ev in self._events:
            if ev.is_expired(t):
                # Later: teardown hooks if needed
                continue

            if ev.is_active(t):
                self._update_event(ev, t)

            still_alive.append(ev)

        self._events = still_alive

        # Update floating combat text (damage/heal numbers)
        if self.damage_numbers:
            for num in self.damage_numbers:
                num.update(dt)
            self.damage_numbers = [n for n in self.damage_numbers if n.alive]

    def draw(self, screen: pygame.Surface) -> None:
        """
        Composite FX layers onto the screen.

        Call after BattleArena has drawn the scene, before HUD.
        """
        # Order: tint → aura → particles
        screen.blit(self.tint_surface, (0, 0))
        screen.blit(self.aura_surface, (0, 0))
        screen.blit(self.particle_surface, (0, 0))

        # World-space floating combat text (damage/heal numbers)
        if self.damage_numbers:
            font = self._get_damage_font()
            for num in self.damage_numbers:
                text_surf = font.render(num.text, True, num.color)
                rect = text_surf.get_rect(
                    center=(int(num.pos.x), int(num.pos.y))
                )
                screen.blit(text_surf, rect)

    def _get_damage_font(self):
        """Return the font used for floating combat text.

        Lazily creates the font on first use so we don't depend on
        font init order elsewhere.
        """
        if self._damage_font is None:
            # Default system font; tweak size later as needed.
            self._damage_font = pygame.font.Font(None, 24)
        return self._damage_font

    def get_camera_offset(self) -> pygame.Vector2:
        """
        Offset contributed by FX (quake, sweeps, etc.).

        BattleArena adds this to fx.camera_rig.offset.
        """
        return self.fx_camera_offset

    # ------------------------------------------------------------------
    # Camera helpers (cinematics & sweeps)
    # ------------------------------------------------------------------

    def camera_sweep(
        self,
        direction: Tuple[float, float],
        distance: float,
        duration: float,
        hold: float = 0.0,
    ) -> None:
        """
        Schedule a simple camera sweep in the given direction.

        direction: (dx, dy) vector, will be normalized.
        distance:  how far to move over the course of the sweep.
        duration:  how long it takes to reach the max offset.
        hold:      optional extra time to hold before returning.
        """
        dx, dy = direction
        length = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        nx, ny = dx / length, dy / length

        total_duration = duration + hold
        ev = FXEvent(
            kind="camera_sweep",
            start=self.time,
            duration=total_duration,
            data={
                "direction": (nx, ny),
                "distance": distance,
                "rise_time": duration,
                "hold": hold,
            },
        )
        self._events.append(ev)

    def play_basic_skill_cinematic(self, *args: Any, **kwargs: Any) -> None:
        """
        Forward to CameraRig.play_basic_skill_cinematic().
        """
        self.camera_rig.play_basic_skill_cinematic(*args, **kwargs)

    # ------------------------------------------------------------------
    # Event queue helpers
    # ------------------------------------------------------------------

    def _push_event(self, kind: str, duration: float, **data: Any) -> None:
        self._events.append(
            FXEvent(
                kind=kind,
                start=self.time,
                duration=duration,
                data=data,
            )
        )

    def _update_event(self, event: FXEvent, t: float) -> None:
        elapsed = t - event.start
        if event.duration <= 0.0:
            progress = 1.0
        else:
            progress = max(0.0, min(1.0, elapsed / event.duration))

        kind = event.kind
        data = event.data

        if kind == "tint_screen":
            self.primitives.tint_screen(progress, data)

        elif kind == "impact_flash":
            self.primitives.impact_flash(data.get("sprite"), progress, data)

        elif kind == "pulse_sprite":
            self.primitives.pulse_sprite(data.get("sprite"), progress, data)

        elif kind == "apply_aura":
            self.primitives.apply_aura(data.get("sprite"), progress, data)

        elif kind == "quake":
            self.primitives.quake(progress, data, self.time)

        elif kind == "burst_particles":
            self.primitives.burst_particles(progress, data)

    # ------------------------------------------------------------------
    # Public primitive APIs (schedule events)
    # ------------------------------------------------------------------

    def tint_screen(
        self,
        color: Tuple[int, int, int],
        strength: float,
        duration: float,
    ) -> None:
        self._push_event(
            kind="tint_screen",
            duration=duration,
            color=color,
            strength=strength,
        )

    def impact_flash(self, sprite: Any, duration: float = 0.10) -> None:
        self._push_event(
            kind="impact_flash",
            duration=duration,
            sprite=sprite,
        )

    def pulse_sprite(
        self,
        sprite: Any,
        color: Tuple[int, int, int],
        duration: float,
        strength: float = 1.0,
    ) -> None:
        self._push_event(
            kind="pulse_sprite",
            duration=duration,
            sprite=sprite,
            color=color,
            strength=strength,
        )

    def apply_aura(
        self,
        sprite: Any,
        color: Tuple[int, int, int],
        duration: float,
        strength: float = 1.0,
    ) -> None:
        self._push_event(
            kind="apply_aura",
            duration=duration,
            sprite=sprite,
            color=color,
            strength=strength,
        )

    def quake(self, strength: float = 5.0, duration: float = 0.20) -> None:
        """
        Schedule a shake event.

        FXPrimitives.quake() will mutate fx_camera_offset; BattleArena
        adds that to camera_rig.offset.
        """
        self._push_event(
            kind="quake",
            duration=duration,
            strength=strength,
        )

    def burst_particles(
        self,
        sprite: Any | None,
        duration: float = 0.35,
        *,
        position: Optional[pygame.Vector2] = None,
        count: int = 7,
        spread: float = 20.0,
        effect_kind: str = "white",
    ) -> None:
        """
        Spawn a small radial burst of particles.

        You can pass a sprite or a raw position (pygame.Vector2).
        """
        if position is not None:
            pos = position
        elif sprite is not None:
            pos = pygame.Vector2(
                getattr(sprite, "x", 0),
                getattr(sprite, "y", 0),
            )
        else:
            pos = None

        self._push_event(
            kind="burst_particles",
            duration=duration,
            position=pos,
            count=count,
            spread=spread,
            effect_kind=effect_kind,
        )

    # ------------------------------------------------------------------
    # Router wiring
    # ------------------------------------------------------------------

    def _register_handlers(self) -> None:
        """
        Subscribe to battle topics.

        Fired from BattleArena._apply_battle_event(...).
        """
        self.router.subscribe("battle.hit", self._on_battle_hit)
        self.router.subscribe("battle.heal", self._on_battle_heal)
        self.router.subscribe("battle.status_apply", self._on_status_apply)
        self.router.subscribe("battle.status_tick", self._on_status_tick)
        self.router.subscribe("battle.dot_tick", self._on_status_tick)
        self.router.subscribe("battle.hot_tick", self._on_status_tick)
        self.router.subscribe("battle.status_expire", self._on_status_expire)

    # ------------------------------------------------------------------
    # Debug helpers (Forge XIII.6 compatibility, now logger-based)
    # ------------------------------------------------------------------

    def _log_event(self, kind: str, **fields: Any) -> None:
        if not self.debug_enabled:
            return

        entry = {"kind": kind, "time": round(self.time, 3)}
        entry.update(fields)
        self._recent_events.append(entry)

        if self.debug_auto_print:
            battle_log("fx", f"[FX DEBUG] {entry}")

    def toggle_debug_auto_print(self) -> None:
        """
        Toggle auto-printing of FX debug entries (used by F3).

        When enabled, each FX event recorded via _log_event will also
        be sent to the unified battle logger under the 'fx' category.
        """
        self.debug_enabled = True
        self.debug_auto_print = not self.debug_auto_print
        state = "ON" if self.debug_auto_print else "OFF"
        battle_log("fx", f"FX auto_print is now {state}")

    def debug_print_recent_events(self) -> None:
        """
        Emit the recent FX events buffer via the battle logger.

        Used by test_battle_arena F3/F4 hooks. This no longer prints
        directly to stdout; instead it integrates with the structured
        battle debug channel.
        """
        battle_log("fx", "=== Recent FX Events ===")
        if not self._recent_events:
            battle_log("fx", "[none]")
        else:
            for e in self._recent_events:
                battle_log("fx", repr(e))
        battle_log("fx", "=== END FX DEBUG ===")

    # Alias for older calls (F4 in test_battle_arena.py)
    def print_recent_events(self) -> None:
        self.debug_print_recent_events()

    # ------------------------------------------------------------------
    # Small helpers: element → color
    # ------------------------------------------------------------------

    def _element_color_hint(
        self,
        element: Optional[str],
        intent: str,
    ) -> Tuple[int, int, int]:
        """
        Tiny palette helper to bias FX colors by element + intent.
        """
        e = (element or "").lower()

        if intent == "hit":
            if e == "fire":
                return (255, 140, 80)
            if e == "ice":
                return (150, 200, 255)
            if e == "lightning":
                return (255, 255, 180)
            if e == "shadow":
                return (200, 120, 255)
            if e == "holy":
                return (255, 255, 220)
            return (255, 230, 230)

        if intent == "heal":
            if e == "holy":
                return (220, 255, 220)
            if e == "nature":
                return (200, 255, 200)
            return (210, 255, 210)

        if intent == "curse":
            if e in ("poison", "acid"):
                return (170, 255, 140)
            if e in ("shadow", "void"):
                return (210, 150, 255)
            return (210, 210, 255)

        return (255, 255, 255)

    def _extract_fx_meta(self, event: BattleEvent) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract (fx_tag, element) with precedence:

        1. event.fx_tag / event.element
        2. event.skill.meta.fx_tag / .element, if present
        """
        fx_tag = getattr(event, "fx_tag", None)
        element = getattr(event, "element", None)

        skill = getattr(event, "skill", None)
        meta = getattr(skill, "meta", None) or skill

        if fx_tag is None and meta is not None:
            fx_tag = getattr(meta, "fx_tag", None)
        if element is None and meta is not None:
            element = getattr(meta, "element", None)

        return fx_tag, element

    # ------------------------------------------------------------------
    # Router handlers: battle.hit / battle.heal
    # ------------------------------------------------------------------

    def _on_battle_hit(self, topic: str, data: Dict[str, Any]) -> None:
        """
        Handle a resolved damage event in battle.

        Data payload:
          - event: BattleEvent
          - is_enemy: bool
          - arena: BattleArena
        """
        event: BattleEvent = data["event"]
        is_enemy: bool = data["is_enemy"]

        # Pull FX metadata
        fx_tag, element = self._extract_fx_meta(event)

        # Get a tiny universal recipe (intent only)
        recipe = universalFX.get_recipe(fx_tag, default="hit_light")

        # Base quake on presence of an impact_flash window
        impact_dur = float(recipe.get("impact_flash", 0.10))
        # Slightly stronger quake for "hit_light" vs "curse_pulse", etc.
        if fx_tag == "curse_pulse":
            shake_strength = 6.0
        elif fx_tag == "hit_heavy":
            shake_strength = 7.0
        else:
            shake_strength = 4.0

        # Only apply if damage + target exist
        if event.damage is not None and event.target is not None:
            target_sprite = getattr(event.target, "sprite", None)

            # Camera shake
            self.quake(strength=shake_strength, duration=impact_dur)

            # Sprite impact flash if possible
            if target_sprite is not None:
                self.impact_flash(target_sprite, duration=impact_dur)

                # Optional colored pulse if recipe says so
                if "pulse" in recipe:
                    intent = "curse" if fx_tag == "curse_pulse" else "hit"
                    color = self._element_color_hint(element, intent=intent)
                    self.pulse_sprite(
                        target_sprite,
                        color=color,
                        duration=float(recipe.get("pulse", 0.22)),
                    )

                # Floating damage number over the target
                if event.damage > 0 and hasattr(target_sprite, "rect"):
                    cx, cy = target_sprite.rect.center
                    pos = pygame.Vector2(cx, cy - 20)
                    self.damage_numbers.append(
                        DamageNumber(text=str(event.damage), pos=pos, kind="damage")
                    )

            # Camera motion hints (sweeps / lurches)
            camera_hint = recipe.get("camera")

            # For now we support two simple hints:
            #   - "sweep": horizontal shove toward the target side (for heavy hits)
            #   - "lurch": small vertical shove upward (for curses, etc.)
            if camera_hint or fx_tag in ("hit_heavy", "curse_pulse"):
                if camera_hint == "sweep" or fx_tag == "hit_heavy":
                    # Player hitting enemy (is_enemy=False) → enemies on the right → shove +x
                    # Enemy hitting player (is_enemy=True)  → party on the left       → shove -x
                    direction = (1.0, 0.0) if not is_enemy else (-1.0, 0.0)
                    self.camera_sweep(
                        direction=direction,
                        distance=32.0,
                        duration=max(0.10, impact_dur * 0.9),
                        hold=0.03,
                    )
                elif camera_hint == "lurch" or fx_tag == "curse_pulse":
                    # Quick vertical shove for curses / shadowy hits
                    self.camera_sweep(
                        direction=(0.0, -1.0),
                        distance=18.0,
                        duration=max(0.08, impact_dur * 0.7),
                        hold=0.02,
                    )

        # Log hit FX summary (if debug is enabled)
        self._log_event(
            "hit",
            fx_tag=fx_tag,
            element=element,
            amount=getattr(event, "damage", None),
            source=getattr(getattr(event, "actor", None), "name", None),
            target=getattr(getattr(event, "target", None), "name", None),
        )

    def _on_battle_heal(self, topic: str, data: Dict[str, Any]) -> None:
        """
        Handle a resolved heal event in battle.

        Data payload:
          - event: BattleEvent
          - is_enemy: bool
          - arena: BattleArena
        """
        event: BattleEvent = data["event"]

        fx_tag, element = self._extract_fx_meta(event)
        recipe = universalFX.get_recipe(fx_tag, default="heal_single")

        if event.heal is not None and event.target is not None:
            target_sprite = getattr(event.target, "sprite", None)
            if target_sprite is not None:
                color = self._element_color_hint(element, intent="heal")
                self.pulse_sprite(
                    target_sprite,
                    color=color,
                    duration=float(recipe.get("pulse", 0.30)),
                )

                # Floating heal number over the target
                if event.heal > 0 and hasattr(target_sprite, "rect"):
                    cx, cy = target_sprite.rect.center
                    pos = pygame.Vector2(cx, cy - 20)
                    self.damage_numbers.append(
                        DamageNumber(text=str(event.heal), pos=pos, kind="heal")
                    )

        self._log_event(
            "heal",
            fx_tag=fx_tag,
            element=element,
            amount=getattr(event, "heal", None),
            source=getattr(getattr(event, "actor", None), "name", None),
            target=getattr(getattr(event, "target", None), "name", None),
        )
    def _on_status_apply(self, topic: str, data: Dict[str, Any]) -> None:
        """
        Handle 'status applied' events. For now we just log a summary.
        Later we can add small auras or pulses for buffs/debuffs.
        """
        owner = data.get("owner")
        status = data.get("status")
        is_enemy = bool(data.get("is_enemy", False))

        status_name = getattr(status, "id", None) or getattr(status, "name", None)
        owner_name = getattr(owner, "name", None)

        # TODO (later): visually differentiate buffs vs debuffs here.
        self._log_event(
            "status_apply",
            status=status_name,
            owner=owner_name,
            is_enemy=is_enemy,
        )

    def _on_status_tick(self, topic: str, data: Dict[str, Any]) -> None:
        """
        Handle 'status tick' events (DOT / HOT).

        Expected payload from BattleRuntime.emit_status_tick_fx:
        - owner: combatant with the status
        - status: status object
        - amount: int
        - kind: "dot" | "hot" | "buff" | "debuff" | "unknown"
        - element: str | None (e.g. "fire", "poison", "bleed")
        - tick_kind: legacy string tag ("poison", "bleed", "regen", etc.)
        - is_enemy: bool
        - arena: BattleArena | None
        """
        owner = data.get("owner")
        status = data.get("status")
        amount = data.get("amount")
        tick_kind = data.get("tick_kind")
        is_enemy = bool(data.get("is_enemy", False))
        arena = data.get("arena")

        # semantic metadata from runtime
        status_kind = data.get("kind")       # "dot", "hot", etc.
        element = data.get("element")        # "fire", "poison", ...

        status_name = getattr(status, "id", None) or getattr(status, "name", None)
        owner_name = getattr(owner, "name", None)

        # Entry log: we received a status_tick event
        self._log_event(
            "status_tick",
            topic=topic,
            owner=owner_name,
            amount=amount,
            tick_kind=tick_kind,
            status_kind=status_kind,
            element=element,
            is_enemy=is_enemy,
            note="handler_enter",
        )

        # Nothing to do if we don't have an amount or an owner.
        if owner is None or amount is None or amount == 0:
            self._log_event(
                "status_tick",
                status=status_name,
                owner=owner_name,
                amount=amount,
                tick_kind=tick_kind,
                status_kind=status_kind,
                element=element,
                is_enemy=is_enemy,
                note="no_amount_or_owner",
            )
            return

        # Decide whether this tick feels like damage or heal.
        # Prefer semantic 'status_kind'; fall back to tick_kind/topic.
        if status_kind == "hot":
            num_kind = "heal"
        else:
            tick_kind_lower = (tick_kind or "").lower()
            if tick_kind_lower in ("regen", "hot", "heal"):
                num_kind = "heal"
            else:
                num_kind = "damage"

        # ----------------------------------------------------
        # Resolve the owner's sprite (where the number appears)
        # ----------------------------------------------------
        target_sprite = None

        # 1) Prefer the arena's mapping (stage sprite with real rect/pos)
        if arena is not None and hasattr(arena, "get_sprite_for_combatant"):
            try:
                target_sprite = arena.get_sprite_for_combatant(owner)
            except Exception as e:
                self._log_event(
                    "status_tick",
                    status=status_name,
                    owner=owner_name,
                    amount=amount,
                    tick_kind=tick_kind,
                    status_kind=status_kind,
                    element=element,
                    is_enemy=is_enemy,
                    note="sprite_lookup_error",
                    error=str(e),
                )

        # 2) Fallback to owner.sprite if arena didn't yield anything
        if target_sprite is None:
            target_sprite = getattr(owner, "sprite", None)

        # If we still don't have any sprite object, bail.
        if target_sprite is None:
            self._log_event(
                "status_tick",
                status=status_name,
                owner=owner_name,
                amount=amount,
                tick_kind=tick_kind,
                status_kind=status_kind,
                element=element,
                is_enemy=is_enemy,
                note="no_sprite",
            )
            return  # no actor anchor → no number

        # ----------------------------------------------------
        # Determine screen position from the sprite
        # ----------------------------------------------------
        cx = cy = None

        # Case 1: classic pygame-style rect
        if hasattr(target_sprite, "rect") and target_sprite.rect is not None:
            try:
                cx, cy = target_sprite.rect.center
            except Exception:
                cx = cy = None

        # Case 2: explicit vector position (e.g. sprite.pos)
        if (cx is None or cy is None) and hasattr(target_sprite, "pos"):
            try:
                # pos might be a pygame.Vector2 or a tuple
                pos_val = target_sprite.pos
                if hasattr(pos_val, "x") and hasattr(pos_val, "y"):
                    cx, cy = pos_val.x, pos_val.y
                elif isinstance(pos_val, (tuple, list)) and len(pos_val) >= 2:
                    cx, cy = pos_val[0], pos_val[1]
            except Exception:
                cx = cy = None

        # Case 3: separate x/y attributes
        if (cx is None or cy is None) and hasattr(target_sprite, "x") and hasattr(
            target_sprite, "y"
        ):
            try:
                cx, cy = target_sprite.x, target_sprite.y
            except Exception:
                cx = cy = None

        # If we *still* don't have coords, bail.
        if cx is None or cy is None:
            self._log_event(
                "status_tick",
                status=status_name,
                owner=owner_name,
                amount=amount,
                tick_kind=tick_kind,
                status_kind=status_kind,
                element=element,
                is_enemy=is_enemy,
                note="no_position",
            )
            return

        # We have a real on-screen position; spawn the number
        pos = pygame.Vector2(cx, cy - 20)
        self.damage_numbers.append(
            DamageNumber(
                text=str(amount),
                pos=pos,
                kind=num_kind,
            )
        )

        # Log the spawn for FX debug overlay
        self._log_event(
            "status_tick",
            status=status_name,
            owner=owner_name,
            amount=amount,
            tick_kind=tick_kind,
            status_kind=status_kind,
            element=element,
            is_enemy=is_enemy,
            event="spawn_number",
            number_kind=num_kind,
            pos=(cx, cy),
        )


    def _on_status_expire(self, topic: str, data: Dict[str, Any]) -> None:
        """
        Handle 'status expired' events (end of Burn, Regen, Shield, etc.).

        For now we only log a summary. Later this is a great hook for
        fade-out FX or cleanse flashes.
        """
        owner = data.get("owner")
        status = data.get("status")
        is_enemy = bool(data.get("is_enemy", False))

        status_name = getattr(status, "id", None) or getattr(status, "name", None)
        owner_name = getattr(owner, "name", None)

        self._log_event(
            "status_expire",
            status=status_name,
            owner=owner_name,
            is_enemy=is_enemy,
        )
