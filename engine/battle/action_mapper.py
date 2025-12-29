from __future__ import annotations

from typing import Optional, List, Callable, Any

from dataclasses import dataclass

from .session import BattleSession
from .ctb_timeline import CTBTimeline, ReadyBatch
from .action_resolver import ActionResolver
from engine.battle.status.status_event_resolver import resolve_status_events

from engine.battle.action_phases import ActionPhase
from engine.battle.battle_command import BattleCommand
from engine.battle.action_resolver import ActionResult
from engine.battle.outcome_builder import build_battle_outcome



@dataclass(frozen=True)
class MappedAction:
    """
    A fully-decided action ready to be executed by the controller.

    Fields:
        user:
            The combatant object performing the action
            (enemy, boss, guest, etc.).
        skill_id:
            The id of the skill to use (must exist in the
            engine.battle.skills.registry).
        targets:
            A list of combatant objects that this action will apply to.
        reason:
            Optional text describing why this action was chosen
            (for debugging / AI tuning).
    """
    user: Any
    skill_id: str
    targets: List[Any]
    reason: Optional[str] = None


def choose_basic_enemy_action(enemy: Any, controller: Any) -> MappedAction:
    """
    Forge XVII.19 – basic enemy decision helper.

    Behavior:
      - Look up damage-type skills registered for this enemy's archetype
        (using enemy.skill_user_key if present, otherwise enemy.name).
      - Prefer non-heal-like damage skills (ignore items/heals/support).
      - If no damage skills exist but some skills are present, use the first.
      - If no skills exist at all, hard error so we can catch misconfigurations.
      - Target the lowest-HP living party member.
    """

    def pick_damage_skill_for(name: str) -> tuple[Any | None, list[Any]]:
        """
        Helper:
          - Fetch skills via controller.get_skills_for(name)
          - Split into (damage_skills, non_damage_skills)
          - Return (first_damage_or_None, full_skill_list)
        """
        skills: List[Any] = controller.get_skills_for(name)
        if not skills:
            return None, []

        damage_skills: list[Any] = []
        non_damage_skills: list[Any] = []

        for s in skills:
            meta = getattr(s, "meta", None)
            if meta is None:
                non_damage_skills.append(s)
                continue

            category = getattr(meta, "category", None)
            sid = getattr(meta, "id", "") or ""
            sname = getattr(meta, "name", "") or ""
            tags = set(getattr(meta, "tags", []) or [])

            # Healy / support-ish if it looks like an item, heal, or potion
            is_heal_like = (
                category in ("heal", "support")
                or "item" in tags
                or "heal" in tags
                or "support" in tags
                or "potion" in sid.lower()
                or "potion" in sname.lower()
            )

            if category == "damage" and not is_heal_like:
                damage_skills.append(s)
            else:
                non_damage_skills.append(s)

        if damage_skills:
            return damage_skills[0], skills
        return None, skills

    # -----------------------------
    # 1) Choose a damage skill
    # -----------------------------
    # Use canonical archetype name for lookup ("Shade", "Shade Brute", etc.)
    lookup_name = getattr(enemy, "skill_user_key", enemy.name)
    skill_def, enemy_skill_list = pick_damage_skill_for(lookup_name)

    # If we still have nothing, but the enemy has *some* skills, grab the first.
    if skill_def is None:
        if enemy_skill_list:
            skill_def = enemy_skill_list[0]
        else:
            # Absolute last resort: hard error so we see misconfigurations
            raise RuntimeError(
                f"No usable skills found for enemy: {getattr(enemy, 'name', '?')}"
            )

    # -----------------------------
    # 2) Choose a target
    # -----------------------------
    party = getattr(controller, "party", [])
    living_party = [c for c in party if getattr(c, "alive", True)]

    if not living_party:
        targets: List[Any] = []
    else:
        # Prefer the lowest-HP living target if 'hp' exists,
        # otherwise just pick the first.
        def _hp_or_big(c: Any) -> int:
            return getattr(c, "hp", 10_000_000)

        best_target = min(living_party, key=_hp_or_big)
        targets = [best_target]

    return MappedAction(
        user=enemy,
        skill_id=skill_def.meta.id,
        targets=targets,
        reason="basic_enemy_ai_lowest_hp",
    )


@dataclass
class ActionMapper:
    """
    ActionMapper

    Single authority for:
    - Phase transitions
    - Turn consumption
    - CTB advancement

    Consumes:
    - BattleCommand payloads (from UIFlow / Arena routing)

    Produces:
    - ActionResult → Session mutation (POST_RESOLVE)
    """

    runtime: "BattleRuntime"

    def __post_init__(self) -> None:
        self.phase: str = ActionPhase.WAIT_CTB
        self.current_actor_id: Optional[str] = None
        self._ready_queue: List[str] = []
        self.pending_command: Optional[BattleCommand] = None  # later: BattleCommand
        self.pending_action_result: ActionResult | None = None
        self._outcome_built: bool = False
        setattr(self.runtime, "battle_outcome", None)
    # --------------------------------------------------
    # Public entry point (called by BattleRuntime.update)
    # --------------------------------------------------
    def update(self, dt: float, controller: "BattleController") -> None:

        # Terminal states -> BATTLE_END (CTB frozen; owner should tear down battle)
        state = getattr(controller, "state", None)
        if state in ("victory", "defeat", "flee") or self.phase == ActionPhase.BATTLE_END:
            # If phase already ended (e.g., set in POST_RESOLVE), ensure outcome is built once.
            if self.phase == ActionPhase.BATTLE_END:
                self._build_battle_outcome_once(controller)
                return

            # Transition into BATTLE_END
            self.phase = ActionPhase.BATTLE_END
            self._build_battle_outcome_once(controller)

            # Pause CTB deterministically (best-effort)
            try:
                if hasattr(self.runtime.timeline, "pause"):
                    self.runtime.timeline.pause()
            except Exception:
                pass
            return

        if self.phase == ActionPhase.WAIT_CTB:
            self._phase_wait_ctb(dt, controller)
        elif self.phase == ActionPhase.PREPARE_ACTOR:
            self._phase_prepare_actor(controller)
        elif self.phase == ActionPhase.PLAYER_COMMAND:
            self._phase_player_command(controller)
        elif self.phase == ActionPhase.ENEMY_COMMAND:
            self._phase_enemy_command(controller)
        elif self.phase == ActionPhase.RESOLVE_ACTION:
            self._phase_resolve_action(controller)
        elif self.phase == ActionPhase.POST_RESOLVE:
            self._phase_post_resolve(controller)
        elif self.phase == ActionPhase.BATTLE_END:
            # Nothing further to do; owner should tear down the battle.
            return

    def _build_battle_outcome_once(self, controller: "BattleController") -> None:
        """
        Build and stash BattleOutcome exactly once.

        - Does NOT change phase.
        - Does NOT pause CTB.
        - Safe to call from any BATTLE_END transition site.
        """
        if self._outcome_built:
            return

        try:
            outcome = build_battle_outcome(runtime=self.runtime, controller=controller)
        except Exception:
            outcome = None

        setattr(self.runtime, "battle_outcome", outcome)
        self._outcome_built = True

    # --------------------------------------------------
    # Phase handlers
    # --------------------------------------------------
    def _phase_wait_ctb(self, dt: float, controller: "BattleController") -> None:
        """
        WAIT_CTB:
        - CTB ticks.
        - We wait until CTB says one or more actors are ready.
        """

        batch = self.runtime.timeline.update(dt)
        if not batch:
            return

        # Filter out KO'd actors using the runtime helper
        ready_ids = [
            cid for cid in batch.combatant_ids
            if not self.runtime._is_cid_ko(cid)
        ]
        if not ready_ids:
            # Everyone who pinged ready this frame is KO'd.
            return

        self._ready_queue = ready_ids
        self.phase = ActionPhase.PREPARE_ACTOR

    def _phase_prepare_actor(self, controller: "BattleController") -> None:
        """
        PREPARE_ACTOR:
        - Decide which side acts this tick, and which actor ID.
        - If dead/invalid -> inform CTB indirectly by skipping.
        - If valid player actor -> PLAYER_COMMAND
        - If valid enemy actor -> ENEMY_COMMAND
        """
        session = self.runtime.session

        # Partition ready ids by side (party/enemy)
        ready_players: list[str] = []
        ready_enemies: list[str] = []
        for cid in self._ready_queue:
            try:
                side = session.get_side(cid)
            except KeyError:
                continue
            if side == "party":
                ready_players.append(cid)
            else:
                ready_enemies.append(cid)

        if not ready_players and not ready_enemies:
            # Nothing usable; back to CTB ticking.
            self._ready_queue.clear()
            self.phase = ActionPhase.WAIT_CTB
            return

        # Decide which side acts this tick (preserve your rotation rules)
        if ready_players and ready_enemies:
            # Alternate sides when both are available
            if self.runtime._last_side == "party":
                side_to_pick = "enemy"
            else:
                side_to_pick = "party"
        elif ready_players:
            side_to_pick = "party"
        else:
            side_to_pick = "enemy"

        chosen_id: Optional[str] = None
        pending_player_idx = self.runtime._last_player_idx
        pending_enemy_idx = self.runtime._last_enemy_idx

        if side_to_pick == "party":
            order = self.runtime.player_order_ids
            ready_set = set(ready_players)
            start_idx = self.runtime._last_player_idx + 1
            n = len(order)
            for offset in range(n):
                idx = (start_idx + offset) % n
                cid = order[idx]
                if cid in ready_set:
                    chosen_id = cid
                    pending_player_idx = idx
                    break
        else:
            order = self.runtime.enemy_order_ids
            ready_set = set(ready_enemies)
            start_idx = self.runtime._last_enemy_idx + 1
            n = len(order)
            for offset in range(n):
                idx = (start_idx + offset) % n
                cid = order[idx]
                if cid in ready_set:
                    chosen_id = cid
                    pending_enemy_idx = idx
                    break

        if chosen_id is None:
            # Nobody usable; back to CTB.
            self._ready_queue.clear()
            self.phase = ActionPhase.WAIT_CTB
            return

        # Respect controller busy flags (animating, resolving, etc.)
        if getattr(controller, "is_busy", None):
            if controller.is_busy():
                # Do not deliver a new actor while controller is in the middle
                # of something. Let CTB keep its gauge; we'll try again next frame.
                return

        if hasattr(controller, "is_animating") and controller.is_animating():
            return

        if hasattr(controller, "is_resolving") and controller.is_resolving():
            return

        # Lock in rotation state.
        self.runtime._last_side = side_to_pick
        if side_to_pick == "party":
            self.runtime._last_player_idx = pending_player_idx
        else:
            self.runtime._last_enemy_idx = pending_enemy_idx

        # Lock in actor id
        self.current_actor_id = chosen_id

        # -----------------------------
        # XVII.21 – canonical turn-start hook (fires exactly once per actor turn)
        # -----------------------------
        try:
            actor_obj = session.get_combatant(chosen_id)
        except KeyError:
            actor_obj = None

        if actor_obj is not None:
            status_mgr = getattr(actor_obj, "status", None)
            if status_mgr is not None:
                status_mgr.on_turn_start(context=controller)
        # Hi Nyra! <3 (say hi back!)
        dbg = getattr(controller, "debug", None)
        if dbg is not None and hasattr(dbg, "runtime"):
            dbg.runtime(f"[TURN_START] actor={getattr(actor_obj,'name',chosen_id)}")

        # Branch by side.
        try:
            side = session.get_side(chosen_id)
        except KeyError:
            # Shouldn't happen, but be defensive.
            self.phase = ActionPhase.WAIT_CTB
            return

        if side == "party":
            if controller.begin_player_turn(actor_obj):
                self.phase = ActionPhase.PLAYER_COMMAND
            else:
                # Could not start a player turn for this actor; keep flow moving.
                self.phase = ActionPhase.WAIT_CTB
        else:
            # ENEMY_COMMAND:
            self.phase = ActionPhase.ENEMY_COMMAND


        # Consume the queue for this tick; in v1 we only ever dispatch one actor
        self._ready_queue.clear()

    def _phase_player_command(self, controller: "BattleController") -> None:
        """
        PLAYER_COMMAND:
        We wait here until a BattleCommand is provided via on_player_command().
        """
        # If no command has been given yet, remain in this phase.
        if self.pending_command is None:
            return

        # A command was issued; proceed to resolution.
        self.phase = ActionPhase.RESOLVE_ACTION

    def _phase_enemy_command(self, controller: "BattleController") -> None:
        """
        ENEMY_COMMAND:
        - Ask the existing enemy-mapping logic to build a MappedAction.
        - Hand it to the controller.
        - Then move to RESOLVE_ACTION/POST_RESOLVE.
        """
        if self.current_actor_id is None:
            self.phase = ActionPhase.WAIT_CTB
            return

        session = self.runtime.session
        actor = session.get_combatant(self.current_actor_id)

        # Reuse your existing enemy mapping/dispatch
        self.runtime._dispatch_enemy_turn(controller, actor)

        # In current design, execute_mapped_action + finalize_enemy_action
        # effectively do RESOLVE_ACTION + POST_RESOLVE in one go.
        self.phase = ActionPhase.POST_RESOLVE

    def _phase_resolve_action(self, controller: "BattleController") -> None:

        cmd = self.pending_command
        self.pending_command = None

        if cmd is None:
            # Nothing to do; fall back to CTB.
            self.phase = ActionPhase.WAIT_CTB
            return

        # --- PLAYER COMMAND RESOLUTION (NEW) ---
        # Resolve using runtime bridge (BattleCommand -> ActionResult|None)
        result = self.runtime.resolve_player_command(cmd)

        if result is None:
            # Soft-failure: do NOT consume CTB, do NOT advance to POST_RESOLVE.
            # Also: ActionMapper must NOT reach into Arena/UIFlow to recover UI.
            # UI recovery is owned by UIFlow (Cut 2 will wire this cleanly).
            self.phase = ActionPhase.PLAYER_COMMAND
            return

        # Success: buffer result and proceed normally
        self.pending_action_result = result
        self.phase = ActionPhase.POST_RESOLVE
        return

    def _phase_post_resolve(self, controller: "BattleController") -> None:
        """
        POST_RESOLVE:
        - Apply ActionResult mutations
        - Handle escape outcome
        - Tick end-of-turn statuses
        - Reset CTB gauge
        - Check victory/defeat
        - Otherwise return to WAIT_CTB
        """
        result = self.pending_action_result
        # --------------------------------------------------
        # Apply ActionResult ONCE
        # --------------------------------------------------
        if result is not None:
            self.runtime.session.apply_action_result(result)
            if hasattr(self.runtime, "apply_action_result_meta"):
                self.runtime.apply_action_result_meta(result)
            # --------------------------------------------------
            # FREE ACTIONS (do not consume the turn)
            # - No status tick
            # - No CTB reset
            # - Same actor stays in PLAYER_COMMAND
            # --------------------------------------------------
            if getattr(result, "command_type", None) in ("equip_weapon",):
                self.pending_action_result = None
                self.phase = ActionPhase.PLAYER_COMMAND
                return

            # --------------------------------------------------
            # Escape / flee resolution (terminal)
            # --------------------------------------------------
            try:
                if getattr(result, "command_type", None) in ("escape", "flee"):
                    if bool(getattr(result, "success", False)):
                        controller.state = "flee"
                        self.phase = ActionPhase.BATTLE_END
                        self._build_battle_outcome_once(controller)
                        try:
                            if hasattr(self.runtime.timeline, "pause"):
                                self.runtime.timeline.pause()
                        except Exception:
                            pass
                        return
            except Exception:
                # Never let malformed results break the battle loop
                pass
            # --------------------------------------------------
            # Outcome check (player path fix)
            # --------------------------------------------------
            try:
                outcome = self.runtime.session.check_battle_outcome()
            except Exception:
                outcome = "ongoing"
            if outcome == "victory":
                controller.state = "victory"
                self.phase = ActionPhase.BATTLE_END
                self._build_battle_outcome_once(controller)
                try:
                    if hasattr(self.runtime.timeline, "pause"):
                        self.runtime.timeline.pause()
                except Exception:
                    pass
                return
            if outcome == "defeat":
                controller.state = "defeat"
                self.phase = ActionPhase.BATTLE_END
                self._build_battle_outcome_once(controller)
                try:
                    if hasattr(self.runtime.timeline, "pause"):
                        self.runtime.timeline.pause()
                except Exception:
                    pass
                return
        # --------------------------------------------------
        # End-of-turn status tick + CTB reset
        # --------------------------------------------------
        cid = self.current_actor_id
        if cid is not None:
            session = self.runtime.session
            try:
                actor = session.get_combatant(cid)
            except KeyError:
                actor = None

            status_mgr = getattr(actor, "status", None) if actor is not None else None
            if status_mgr is not None:
                events = status_mgr.on_turn_end(context=controller)
                if events:
                    ar = resolve_status_events(
                        events=events,
                        session=session,
                        source="status_turn_end",
                    )
                    
            self.runtime.timeline.reset_gauge(cid)

        # Clear current actor
        self.current_actor_id = None

        # --------------------------------------------------
        # Victory / defeat
        # --------------------------------------------------
        state = getattr(controller, "state", None)
        if state in {"victory", "defeat", "flee"}:
            self.phase = ActionPhase.BATTLE_END
            self._build_battle_outcome_once(controller)

            if hasattr(self.runtime.timeline, "pause"):
                self.runtime.timeline.pause()
            return
        # --------------------------------------------------
        # Narrative / multi-phase transitions (optional)
        # --------------------------------------------------
        scen = getattr(controller, "scenario", None)
        if scen is not None:
            try:
                # Ask scenario if we should transition phases at this beat
                should = False
                if hasattr(scen, "should_transition"):
                    should = bool(scen.should_transition(controller=controller, session=self.runtime.session))
                if should:
                    # Apply the transition immediately (swap enemies, set flags, etc.)
                    if hasattr(scen, "apply_transition"):
                        scen.apply_transition(controller=controller, session=self.runtime.session)
                    # Optional: clear hover/targeting or other UI bridge if you want later
            except Exception:
                pass

        # Back to CTB ticking
        self.phase = ActionPhase.WAIT_CTB

    # --------------------------------------------------
    # Future hook: when InputHandler is born, it will call:
    # runtime.mapper.on_player_command(command)
    # --------------------------------------------------
    def on_player_command(self, command: BattleCommand) -> None:
        """
        Called by the input layer (via BattleArena) when a player confirms.
        Stores the BattleCommand and nudges the phase machine forward if
        we're in PLAYER_COMMAND.
        """
        self.pending_command = command

        # Only advance if we're actually waiting for a player command.
        if self.phase == ActionPhase.PLAYER_COMMAND:
            self.phase = ActionPhase.RESOLVE_ACTION


