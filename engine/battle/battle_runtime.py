# engine/battle/battle_runtime.py

from __future__ import annotations

from typing import Iterable, Any, Optional, Dict, List
from engine.battle.session import BattleSession
from engine.battle.ctb_timeline import CTBTimeline, ReadyBatch
from engine.battle.action_mapper import choose_basic_enemy_action, ActionMapper
from engine.battle.input_handler import BattleInputHandler
from game.debug.debug_logger import BattleDebug  # XVII.8 – battle logger
from .action_resolver import ActionResolver, ActionResult, TargetResult
from game.debug.debug_logger import log as battle_log
from engine.battle.status.effects import get_status_fx_meta
from engine.battle.action_phases import ActionPhase
from engine.meta.battle_outcome import BattleOutcome
from engine.battle.battle_gains import BattleGains

# Forge XVII.13 – Resolver authority scaffolding
USE_ACTION_RESOLVER_FOR_PLAYERS: bool = False
USE_ACTION_RESOLVER_FOR_ENEMIES: bool = False
SESSION_AUTH_PLAYER_SKILLS: set[str] = {
    "setia_attack_1",  # Setia's basic Attack
    "setia_wind_strike_1"
}

class BattleRuntime:
    """
    BattleRuntime

    Responsibilities (XVII.26+):
    - Resolve BattleCommand → ActionResult
    - Delegate mechanical resolution (SkillResolver, etc.)
    - Hand results to ActionMapper for phase/CTB control

    Non-responsibilities:
    - Does NOT own turn flow
    - Does NOT mutate HP/MP directly (Session is the mutation gate)
    - Does NOT manage UI state
    """

    def __init__(
        self,
        party: Iterable[Any],
        enemies: Iterable[Any],
        router: Any,
        flags: Optional[Any] = None,
    ) -> None:
        
        # Make concrete lists so we can safely reuse them
        self.party = list(party)
        self.enemies = list(enemies)

        # Ensure every combatant has an .id for CTB + Session
        all_objs = self.party + self.enemies
        for idx, obj in enumerate(all_objs):
            if not hasattr(obj, "id") or getattr(obj, "id") is None:
                name = getattr(obj, "name", None) or getattr(obj, "label", None)
                if not name:
                    name = f"combatant_{idx}"
                obj.id = str(name)

        # Core battle model
        self.session = BattleSession(self.party, self.enemies, flags=flags)
        self.router = router
        self.gains = BattleGains()
        self.session.gains = self.gains
        # Battle-local equipment snapshot (NO ledger mutation)
        # actor_id -> weapon_id (or other equip ids later)
        self.equipment: dict[str, str] = {}

        self.debug = BattleDebug()
        from engine.items.bootstrap import initialize_items
        initialize_items()

        # Stable turn-order lists (based on party/enemy order)
        self.player_order_ids: list[str] = []
        for idx, obj in enumerate(self.party):
            cid = getattr(obj, "id", None)
            if cid is None:
                cid = f"party_{idx}"
                obj.id = cid
            self.player_order_ids.append(cid)

        self.enemy_order_ids: list[str] = []
        for idx, obj in enumerate(self.enemies):
            cid = getattr(obj, "id", None)
            if cid is None:
                cid = f"enemy_{idx}"
                obj.id = cid
            self.enemy_order_ids.append(cid)

        # Rotation cursors
        self._last_side: str | None = None
        self._last_player_idx: int = -1
        self._last_enemy_idx: int = -1

        # New CTB + action architecture
        self.timeline = CTBTimeline(self.session)
        self.resolver = ActionResolver(self.session)
        self.input_handler = BattleInputHandler(self.session)
        self.input = self.input_handler
        # XVII.11 – phase-based nervous system
        self.action_mapper = ActionMapper(self)

    def is_session_authoritative_for_player_skill(self, skill_id: str) -> bool:
        return skill_id in SESSION_AUTH_PLAYER_SKILLS
    # ------------------------------------------------------
    # XVII.13 – Resolution scaffolding (mirror only)
    # ------------------------------------------------------
    def _format_action_result_pairs(self, action_result: ActionResult) -> list[tuple[str, int]]:
        """
        Helper for compact debug logging:
            [('Shade A', -42), ('Setia', 0)]
        """
        pairs: list[tuple[str, int]] = []
        for t in action_result.targets:
            pairs.append((t.target_id, t.hp_delta))
        return pairs

    def capture_player_resolution(
        self,
        *,
        actor: Any,
        skill_def: Any | None,
        targets: list[Any],
        skill_result: Any,
    ) -> Any | None:
        """
        Build an ActionResult from the existing SkillResolver result.

        Does NOT apply deltas to Session here.
        Instead, buffers the ActionResult for ActionMapper.POST_RESOLVE to apply.
        """
        if not hasattr(self, "resolver") or self.resolver is None:
            return None

        try:
            action_result = self.resolver.build_from_skill_resolution(
                actor=actor,
                skill_def=skill_def,
                targets=targets,
                skill_result=skill_result,
                command_type="skill",
            )
        except Exception as exc:
            if getattr(self, "debug", None) is not None:
                self.debug.runtime(f"[RESOLVER] player mirror failed: {exc!r}")
            return None
        # XVII.?? – Immediate-bucket status events (retaliation, on-hit procs)
        extra_events = getattr(skill_result, "status_events", None)
        if extra_events:
            from engine.battle.status.status_event_resolver import resolve_status_events

            extra_ar = resolve_status_events(
                events=extra_events,
                session=self.session,
                source="status_immediate",
            )

            # Merge into the same mutation package (do NOT apply here)
            action_result.targets.extend(extra_ar.targets)

        # Optional: compact debug summary (keep or delete later)
        try:
            pairs = self._format_action_result_pairs(action_result)
            if getattr(self, "debug", None) is not None:
                name = getattr(actor, "name", getattr(actor, "id", "<?>"))
                self.debug.runtime(f"[RESOLVER] player {name} -> {pairs}")
        except Exception:
            # Debug should never break the battle flow
            pass

        # Hand off to ActionMapper; POST_RESOLVE will apply it
        if getattr(self, "action_mapper", None) is not None:
            self.action_mapper.pending_action_result = action_result

        return action_result
    
    def capture_enemy_resolution(
        self,
        *,
        enemy: Any,
        skill_def: Any | None,
        targets: list[Any],
        skill_result: Any,
    ) -> None:
        """
        Same mirror as capture_player_resolution, but we log via the
        enemy_ai channel so it shows up under [BATTLE ENEMY_AI].
        """
        if not hasattr(self, "resolver") or self.resolver is None:
            return

        try:
            action_result = self.resolver.build_from_skill_resolution(
                actor=enemy,
                skill_def=skill_def,
                targets=targets,
                skill_result=skill_result,
                command_type="skill",
            )
        except Exception as exc:
            if hasattr(self, "debug") and self.debug is not None:
                self.debug.enemy_ai(f"[RESOLVER] enemy mirror failed: {exc!r}")
            return

        pairs = self._format_action_result_pairs(action_result)
        if hasattr(self, "debug") and self.debug is not None:
            name = getattr(enemy, "name", getattr(enemy, "id", "<?>"))
            self.debug.enemy_ai(f"[RESOLVER] enemy {name} -> {pairs}")

    def resolve_player_command(self, command):
        """
        Resolve a player BattleCommand into an ActionResult.

        Authority notes (XVII.26+):
        - ActionMapper owns phase/CTB; this method only resolves payload -> result.
        - Session mutation still happens in POST_RESOLVE.
        """
        arena = getattr(self, "arena", None)
        controller = getattr(arena, "controller", None) if arena is not None else None

        ctype = getattr(command, "command_type", None)

        # Local import avoids cycles and keeps runtime light.
        from engine.battle.command_handlers import (
            resolve_defend,
            resolve_flee,
            resolve_item,
            resolve_equip_weapon,
            resolve_skill,
        )

        if ctype == "defend":
            return resolve_defend(command)

        if ctype == "flee":
            return resolve_flee(command, session=self.session)

        if ctype == "item":
            return resolve_item(command, session=self.session, runtime=self)

        if ctype == "equip_weapon":
            return resolve_equip_weapon(command)

        if ctype == "skill":
            return resolve_skill(command, runtime=self, controller=controller, arena=arena)

        return None


    def _emit_player_message(self, arena, actor, meta, msg: str) -> None:
        """Transitional UI feedback hook (safe no-op if not available)."""
        if arena is None or not hasattr(arena, "_apply_battle_event"):
            return
        try:
            from engine.battle.battle_controller import BattleEvent  # local to avoid cycles
            evt = BattleEvent(actor, None, meta, None, None, msg, None)
            arena._apply_battle_event(evt, is_enemy=False)
        except Exception:
            return

    # ------------------------------------------------------
    # Forge XVII.13 – ActionResolver authority helper
    # ------------------------------------------------------
    def apply_action_result(self, result: Any) -> None:
        """
        Thin pass-through helper so callers can ask the runtime
        to apply a mechanical ActionResult to the Session.

        In Forge XVII.13 this is not used in the main flow yet;
        it's here so future forges can flip usage on per-skill
        or per-side toggles.
        """
        if result is None:
            return
        session = getattr(self, "session", None)
        if session is None:
            return

        # Defensive import / call to avoid cycles
        try:
            session.apply_action_result(result)
        except Exception as e:
            if hasattr(self, "debug") and self.debug is not None:
                self.debug.runtime(
                    f"[RESOLVER] error applying ActionResult via Session: {e}"
                )

    def apply_action_result_meta(self, result) -> None:
        """
        Apply non-Session battle-local mutations that should occur at the same deterministic
        POST_RESOLVE beat as Session truth application.

        IMPORTANT: This must NOT touch the ledger.
        """
        try:
            if getattr(result, "command_type", None) == "equip_weapon":
                actor_id = getattr(result, "actor_id", None)
                weapon_id = getattr(result, "item_id", None)
                if actor_id and weapon_id:
                    self.equipment[str(actor_id)] = str(weapon_id)
        except Exception:
            pass

    # ------------------------------------------------------
    # KO helper
    # ------------------------------------------------------

    def _is_cid_ko(self, cid: str) -> bool:
        """
        Runtime-facing KO helper.

        Given a combatant ID, return True if this actor is considered KO'd
        according to the BattleSession's definition. If the session doesn't
        expose an _is_ko() helper, fall back to a basic flag check.
        """
        try:
            combatant = self.session.get_combatant(cid)
        except KeyError:
            # If we can't even find them, treat them as unusable/KO.
            return True

        # Preferred: delegate to the session's KO definition if available.
        if hasattr(self.session, "_is_ko"):
            try:
                return bool(self.session._is_ko(combatant))  # type: ignore[attr-defined]
            except Exception:
                # If something goes wrong, fall back to local check.
                pass

        # Fallback: try simple flag access on the combatant.
        flag = getattr(combatant, "is_ko", None)
        if callable(flag):
            return bool(flag())
        if flag is not None:
            return bool(flag)

        # Last resort: if there's a _is_ko attribute directly.
        flag2 = getattr(combatant, "_is_ko", None)
        if callable(flag2):
            return bool(flag2())
        if flag2 is not None:
            return bool(flag2)

        # If we truly can't tell, assume they are NOT KO'd.
        return False
    # ------------------------------------------------------
    # CTB gauge bridge for HUD (XVII.10)
    # ------------------------------------------------------
    def get_ctb_ratio_for(self, actor: Any) -> float:
        cid = getattr(actor, "id", None)
        if cid is None:
            return 0.0

        if not hasattr(self, "timeline") or self.timeline is None:
            return 0.0

        getter = getattr(self.timeline, "get_gauge_ratio", None)
        if getter is None:
            return 0.0

        try:
            return getter(cid)
        except Exception:
            return 0.0

    def get_ctb_commit_threshold(self) -> float:
        tl = getattr(self, "timeline", None)
        if tl is None:
            return 0.5
        getter = getattr(tl, "get_commit_threshold", None)
        if getter is None:
            return 0.5
        return float(getter())

    # ------------------------------------------------------
    # XVII.4 – enemy dispatch + finalize seams
    # ------------------------------------------------------

    def _dispatch_enemy_turn(self, controller, enemy_obj) -> None:
        """
        Build a MappedAction for the given enemy and let the controller
        execute it via the new enemy pipeline.
        """
        mapped = choose_basic_enemy_action(enemy_obj, controller)
        # BattleController is expected to provide execute_mapped_action().
        controller.execute_mapped_action(mapped)

    def finalize_enemy_action(self, mapped, result, controller) -> None:
        """
        XVII.18 – Enemy action bridge into the unified pipeline.

        Responsibilities:
          - If controller is already in a terminal state, do nothing.
          - Convert the enemy SkillResolutionResult into an ActionResult.
          - Apply that ActionResult via BattleSession.apply_action_result.
          - Emit a BattleEvent for FX/text, using the original SkillResolutionResult.
          - Ask Session to determine victory/defeat/ongoing.

        This mirrors the player path:
          SkillResolver.resolve(...)
            -> ActionResolver.build_from_skill_resolution(...)
            -> BattleSession.apply_action_result(...)
        """

        # XVII.5 – If the controller is already in a terminal state, do nothing.
        if getattr(controller, "state", None) in ("victory", "defeat"):
            return

        # ------------------------------------------------------
        # XVII.18 – Apply mechanical outcome via Session
        # ------------------------------------------------------
        if result is not None:
            # Local imports to avoid circular dependencies at module load time
            from engine.battle.action_resolver import ActionResolver
            from engine.battle.skills import registry

            session = self.session
            enemy = mapped.user

            # Retrieve or construct the skill definition
            skill_def = getattr(mapped, "skill_def", None)
            if skill_def is None:
                # Fall back to the registry if the mapped action didn't carry it
                skill_def = registry.get(mapped.skill_id)

            # Ensure we have an ActionResolver instance on the runtime
            resolver = getattr(self, "action_resolver", None)
            if resolver is None or getattr(resolver, "session", None) is not self.session:
                resolver = self.action_resolver = ActionResolver(self.session)
            # Build an ActionResult (math-only truth of this enemy action)
            targets = getattr(mapped, "targets", []) or []
            action_result = resolver.build_from_skill_resolution(
                actor=enemy,
                skill_def=skill_def,
                targets=targets,
                skill_result=result,
                command_type="enemy_skill",
            )
            # XVII.?? – Immediate-bucket status events (retaliation, on-hit procs)
            extra_events = getattr(result, "status_events", None)
            dbg = getattr(controller, "debug", None) if controller is not None else None
            if dbg is not None and hasattr(dbg, "runtime"):
                dbg.runtime(f"[IMMEDIATE EVENTS] count={len(extra_events) if extra_events else 0}")

            if extra_events:
                # DEBUG: inspect the first immediate StatusEvent so we know why it isn't translating
                if dbg is not None and hasattr(dbg, "runtime"):
                    ev0 = extra_events[0]
                    tgt0 = getattr(ev0, "target", None)
                    dbg.runtime(
                        "[IMMEDIATE EVENT DEBUG] "
                        f"type={type(ev0).__name__} "
                        f"target_type={type(tgt0).__name__ if tgt0 is not None else None} "
                        f"target.id={getattr(tgt0, 'id', None)!r} "
                        f"target.cid={getattr(tgt0, 'cid', None)!r} "
                        f"target.name={getattr(tgt0, 'name', None)!r}"
                    )

                from engine.battle.status.status_event_resolver import resolve_status_events

                extra_ar = resolve_status_events(
                    events=extra_events,
                    session=self.session,
                    source="status_immediate",
                )
                if dbg is not None and hasattr(dbg, "runtime"):
                    dbg.runtime(
                        f"[IMMEDIATE AR] targets={[(tr.target_id, tr.status_applied, tr.status_removed) for tr in extra_ar.targets]}"
                    )

                # Merge into the same mutation package (do NOT apply here)
                action_result.targets.extend(extra_ar.targets)

            # Apply the deltas to the actual combatants
            # Buffer for POST_RESOLVE (the only mutation phase)
            if getattr(self, "action_mapper", None) is not None:
                self.action_mapper.pending_action_result = action_result
            else:
                # Safety fallback (should not happen once runtime always has an action_mapper)
                session.apply_action_result(action_result)

            # Optional: debug summary of the applied deltas
            dbg = getattr(controller, "debug", None)
            if dbg is not None and hasattr(dbg, "enemy_ai"):
                summary = [
                    (tr.target_id, tr.hp_delta, tr.mp_delta)
                    for tr in action_result.targets
                ]
                dbg.enemy_ai(
                    f"[ENEMY PENDING AR] {getattr(enemy, 'name', '<??>')} -> {summary}"
                )

        # ------------------------------------------------------
        # XVII.8 – Emit a BattleEvent for enemy FX via Runtime
        # (unchanged, still based on the original SkillResolutionResult)
        # ------------------------------------------------------
        if result is not None:
            # Pick the first meaningful target change
            ev_target = None
            ev_damage = None
            ev_heal = None

            for change in getattr(result, "targets", []):
                tgt = getattr(change, "target", None)
                dmg = getattr(change, "damage", None)
                heal = getattr(change, "healed", None) or getattr(
                    change, "heal", None
                )
                if tgt is not None and (dmg is not None or heal is not None):
                    ev_target = tgt
                    ev_damage = dmg
                    ev_heal = heal
                    break

            if ev_target is not None and (ev_damage is not None or ev_heal is not None):
                from engine.battle.battle_controller import BattleEvent

                actor = mapped.user
                skill = getattr(mapped, "skill_def", None)
                if skill is None:
                    # If for some reason we didn't stash it, try registry as fallback
                    from engine.battle.skills import registry

                    skill = registry.get(mapped.skill_id)

                meta = getattr(skill, "meta", None) or skill
                label = getattr(meta, "label", getattr(skill, "id", "a skill"))
                actor_name = getattr(actor, "name", "<??>")
                message = f"{actor_name} used {label}."

                event = BattleEvent(
                    actor=actor,
                    target=ev_target,
                    skill=skill,
                    damage=ev_damage,
                    heal=ev_heal,
                    message=message,
                    choreo=None,
                    # FX metadata will be extracted from meta by FXSystem._extract_fx_meta
                )

                # Runtime decides topics & FX routing
                self.emit_effects_for_event(event, is_enemy=True)

        # ------------------------------------------------------
        # Forge XVII.13 – Let Session be the source of outcome truth
        # ------------------------------------------------------
        outcome = "ongoing"
        try:
            outcome = self.session.check_battle_outcome()
        except Exception as e:
            # Fallback to legacy controller helpers if something goes wrong.
            self.debug.runtime(
                f"[OUTCOME] error using Session.check_battle_outcome: {e}"
            )
            # 1) Check if the party has been wiped
            if not controller.living_party():
                outcome = "defeat"
            # 2) Check if all enemies are gone
            elif not controller.living_enemies():
                outcome = "victory"
            else:
                outcome = "ongoing"

        if outcome == "defeat":
            controller.state = "defeat"
            self.debug.runtime("Enemy action caused DEFEAT (Session outcome)")
            return

        if outcome == "victory":
            controller.state = "victory"
            self.debug.runtime("Enemy side defeated – VICTORY (Session outcome)")
            return

        # Otherwise, battle continues in CTB flow
        controller.state = "ctb"
        # Optional: uncomment for more flow spam
        # self.debug.runtime("Enemy action complete; returning to CTB.")

    # ------------------------------------------------------
    # Internal FX emitter
    # ------------------------------------------------------
    def _emit_fx_topic(self, topic: str, payload: dict) -> None:
        """
        Log an FX event via BattleDebug.

        NOTE: This does NOT call the router. The router should only see
        the canonical payload (with 'event', 'is_enemy', 'arena') from
        emit_effects_for_event().
        """
        if hasattr(self, "debug") and self.debug is not None:
            self.debug.fx_event(topic, payload)

    def emit_effects_for_event(
        self,
        event: Any,
        *,
        is_enemy: bool,
        arena: Any | None = None,
    ) -> None:
        """
        XVII.8 – Central FX dispatcher for battle events.

        Given a BattleEvent-like object, derive one or more semantic topics
        (battle.hit, battle.heal, battle.ko, etc.) and emit them through
        the EventRouter. Also logs via BattleDebug.fx_event.
        """
        router = getattr(self, "router", None)
        if router is None or event is None:
            return

        # Pull basic fields off the event
        damage = getattr(event, "damage", None)
        heal = getattr(event, "heal", None)
        target = getattr(event, "target", None)

        # --------------------------------------------------
        # Decide which topics this event should generate
        # --------------------------------------------------
        topics: list[str] = []

        if damage is not None and damage > 0:
            topics.append("battle.hit")
        if heal is not None and heal > 0:
            topics.append("battle.heal")

        # Optional: simple KO detection (can refine later)
        if target is not None and damage and damage > 0:
            if not getattr(target, "alive", True):
                topics.append("battle.ko")

        if not topics:
            # Nothing FX-worthy in this event.
            return

        # --------------------------------------------------
        # Canonical payload for FXSystem / handlers
        # --------------------------------------------------
        payload: dict[str, Any] = {
            "event": event,
            "is_enemy": is_enemy,
        }
        if arena is not None:
            payload["arena"] = arena

        # --------------------------------------------------
        # Debug payload (summary only; NOT passed to router)
        # --------------------------------------------------
        actor = getattr(event, "actor", None)
        dbg_payload = {
            "actor_name": getattr(actor, "name", None),
            "target_name": getattr(target, "name", None) if target is not None else None,
            "damage": damage,
            "heal": heal,
            "skill_id": getattr(event, "skill_id", None),
            "fx_tag": getattr(event, "fx_tag", None),
            "element": getattr(event, "element", None),
            "is_enemy": is_enemy,
        }

        # --------------------------------------------------
        # Emit topics: debug + router
        # --------------------------------------------------
        for topic in topics:
            # Log in a summarized form
            self._emit_fx_topic(topic, dbg_payload)
            # Send canonical payload to handlers (FXSystem expects "event")
            router.emit(topic, **payload)

    def emit_basic_hit_fx(
        self,
        *,
        source,
        target,
        damage: int,
        element: str | None = None,
        crit: bool = False,
        killing_blow: bool = False,
        context: dict | None = None,
        is_enemy: bool = False,
        arena: Any | None = None,
    ) -> None:
        """
        Lightweight helper to fire a one-off hit FX using the central
        emit_effects_for_event() path.

        Builds a minimal BattleEvent so FXSystem sees the same shape
        as a real resolved skill.
        """
        from engine.battle.battle_controller import BattleEvent  # local to avoid cycles

        # For now we don't thread element/crit/context into FX metadata; those
        # will flow from real SkillDefinitions. This helper is mainly for
        # ad-hoc hits or tests.
        msg = None
        event = BattleEvent(
            actor=source,
            target=target,
            skill=None,
            damage=damage,
            heal=None,
            message=msg,
            choreo=None,
        )

        self.emit_effects_for_event(event, is_enemy=is_enemy, arena=arena)
        # KO-specific FX will be handled via real battle events (where the
        # resolver knows the target actually died), so we don't emit a
        # separate "battle.ko" topic here.

    def emit_basic_heal_fx(
        self,
        *,
        source,
        target,
        amount: int,
        element: str | None = None,
        context: dict | None = None,
        is_enemy: bool = False,
        arena: Any | None = None,
    ) -> None:
        """
        Lightweight helper to fire a one-off heal FX using the central
        emit_effects_for_event() path.
        """
        from engine.battle.battle_controller import BattleEvent  # local to avoid cycles

        msg = None
        event = BattleEvent(
            actor=source,
            target=target,
            skill=None,
            damage=None,
            heal=amount,
            message=msg,
            choreo=None,
        )

        self.emit_effects_for_event(event, is_enemy=is_enemy, arena=arena)
    # ------------------------------------------------------
    # Status FX helpers (Part I)
    # ------------------------------------------------------
    def _build_status_dbg_payload(
        self,
        *,
        owner: Any,
        status: Any,
        amount: int | None = None,
        tick_kind: str | None = None,
        is_enemy: bool = False,
    ) -> dict:
        """
        Build a small, debug-friendly summary for status FX events.
        This does NOT go to the router, only to BattleDebug.fx_event().
        """
        owner_name = getattr(owner, "name", None)
        status_id = getattr(status, "id", None) or getattr(status, "name", None)
        return {
            "owner_name": owner_name,
            "status_id": status_id,
            "amount": amount,
            "tick_kind": tick_kind,
            "is_enemy": is_enemy,
        }
    def emit_status_apply_fx(
        self,
        *,
        owner: Any,
        status: Any,
        source: Any | None = None,
        is_enemy: bool = False,
        arena: Any | None = None,
    ) -> None:
        """
        Emit a semantic 'status applied' FX event.
        Example: Burn applied to Nyra, Shield applied to Setia, etc.
        """
        router = getattr(self, "router", None)
        if router is None:
            return

        payload: dict[str, Any] = {
            "owner": owner,
            "status": status,
            "source": source,
            "is_enemy": is_enemy,
        }
        if arena is not None:
            payload["arena"] = arena

        meta = get_status_fx_meta(status)
        payload["status_meta"] = meta
        payload["kind"] = meta.get("kind")
        payload["element"] = meta.get("element")

        topic = "battle.status_apply"

        battle_log("status", f"APPLY: {payload}")

        dbg_payload = self._build_status_dbg_payload(
            owner=owner,
            status=status,
            amount=None,
            tick_kind=None,
            is_enemy=is_enemy,
        )
        self._emit_fx_topic(topic, dbg_payload)

        router.emit(topic, **payload)

    def emit_status_tick_fx(
            self,
            *,
            owner: Any,
            status: Any,
            amount: int,
            tick_kind: str | None = None,
            is_enemy: bool = False,
            arena: Any | None = None,
        ) -> None:
            """
            Emit a semantic 'status tick' FX event.

            Example: Burn deals 5 damage, Regen heals 3, Poison ticks, etc.
            """
            router = getattr(self, "router", None)

            owner_name = getattr(owner, "name", owner)
            status_name = getattr(status, "id", None) or getattr(status, "name", None)

            # If no arena was passed, try to use the one attached to the runtime
            if arena is None:
                arena = getattr(self, "arena", None)

            topic = "battle.status_tick"

            # Build the payload FIRST
            payload: dict[str, Any] = {
                "owner": owner,
                "status": status,
                "amount": int(amount),
                "tick_kind": tick_kind,
                "is_enemy": is_enemy,
            }

            # Attach arena if we have one
            if arena is not None:
                payload["arena"] = arena

            # Annotate with status FX metadata
            from engine.battle.status.effects import get_status_fx_meta

            meta = get_status_fx_meta(status)
            payload["status_meta"] = meta
            payload["kind"] = meta.get("kind")
            payload["element"] = meta.get("element")

            # Structured log instead of raw prints
            battle_log(
                "status",
                f"TICK(battle.status_tick): owner={owner_name}, "
                f"status={status_name}, amount={amount}, tick_kind={tick_kind}, "
                f"is_enemy={is_enemy}",
            )

            # If there's no router, don't crash; just stop here.
            if router is None:
                return

            # For FX debug HUD
            dbg_payload = self._build_status_dbg_payload(
                owner=owner,
                status=status,
                amount=amount,
                tick_kind=tick_kind,
                is_enemy=is_enemy,
            )
            self._emit_fx_topic(topic, dbg_payload)

            router.emit(topic, **payload)
    # ------------------------------------------------------
    # New phase-driven update (XVII.11)
    # ------------------------------------------------------
    def update(self, dt: float, controller) -> None:
        """
        Preferred entry point for battle flow:
        delegates to the ActionMapper, which owns phase transitions.
        """
        # Ensure controller can call back into this runtime (existing seam)
        if getattr(controller, "runtime", None) is None:
            controller.runtime = self

        self.action_mapper.update(dt, controller)



