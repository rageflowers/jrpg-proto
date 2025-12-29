from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional, List, Any, Sequence

from engine.battle.skills.base import SkillDefinition, SkillMeta, SkillResolutionResult
from engine.battle.skills.resolver import SkillResolver
from engine.battle.action_mapper import MappedAction  # XVII.4 seam
from game.debug.debug_logger import BattleDebug, log as battle_log  # XVII.6 – battle logger

# TEMP: Stress-test knob; harness can override this.
ENEMY_DAMAGE_MULTIPLIER: float = 0.2

# ------------------------------------------------------------
# Choreography request (logic layer → visuals layer)
# ------------------------------------------------------------
@dataclass
class ChoreoRequest:
    kind: str              # "melee", "spell", "item", etc.
    actor_id: str          # "Setia", "Nyra", "Kaira"
    primary_target_index: Optional[int] = None

# ------------------------------------------------------------
# A single logical battle outcome (legacy-friendly wrapper)
# ------------------------------------------------------------
@dataclass
class BattleEvent:
    actor: Any
    target: Any
    skill: Any                       # usually SkillMeta or SkillDefinition
    damage: Optional[int]
    heal: Optional[int]
    message: str
    choreo: Optional[ChoreoRequest]
    # NEW: FX-related metadata
    skill_id: Optional[str] = None   # e.g. "nyra_first_light_1"
    fx_tag: Optional[str] = None     # e.g. "hit_light", "heal_single"
    element: Optional[str] = None    # e.g. "holy", "shadow", "wind", "physical"
# ------------------------------------------------------------
# The main controller (turn logic, HP/MP, targeting)
# ------------------------------------------------------------
class BattleController:
    """
    BattleController (Legacy Adapter)

    XVII.26:
    - No longer owns input, targeting, or turn authority
    - Retained as a mechanical helper and registry adapter
    - Scheduled for further slimming or replacement

    Do not add new authority here.
    """

    def __init__(
        self,
        party: List[Any],
        enemies: List[Any],
        get_skills_for: Callable[[str], List[SkillDefinition]],
    ):
        """
        UI / input adapter for battle flow.

        Responsibilities:
        - Maintain menu + targeting UI state
        - Translate player input into BattleCommand
        - Bridge Arena/UI to the battle engine (no mechanics authority)

        NOTE:
            get_skills_for(name: str) -> List[SkillDefinition]
            is expected to return SkillDefinition objects from skills.registry.
        """
        # --- Core references ---
        self.party = party
        self.enemies = enemies
        self.get_skills_for = get_skills_for
        # Runtime hook (set externally by Arena/Runtime)
        self.runtime: Any | None = None
        # --- Controller state ---
        # High-level input mode (e.g. "player_turn", "target_select", etc.)

        # LEGACY: Prefer ActionMapper phases / Runtime authority over controller.state.
        # Kept temporarily for old input wiring; do not add new dependencies.


        # Index into party for the currently active player actor
        self.active_index: int = 0
        # --- Debug ---
        self.debug = BattleDebug()

# ------------------------------------------------------------------
# LEGACY BRIDGE (XVII.26+):
# The following fields exist only to support the transitional
# controller.player_confirm() path used by BattleRuntime.resolve_player_command().
# New UIFlow/ActionMapper flow MUST NOT use these as sources of truth.
# These will be deleted once Runtime resolves commands directly.
# ------------------------------------------------------------------

        # --- Menu / UI indices ---
        self.menu_index: int = 0

        # Current actor's available skills
        if self.party:
            idx = self.active_index if 0 <= self.active_index < len(self.party) else 0
            self.skills: List[SkillDefinition] = self.get_skills_for(self.party[idx].name)
        else:
            self.skills = []

        self._target_hover_id: str | None = None

        # --- Pending action state ---
        # Used while assembling a BattleCommand
        self.pending_primary_target: Any | None = None

    # ------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------
    def living_party(self) -> List[Any]:
        return [c for c in self.party if getattr(c, "alive", True)]

    def living_enemies(self) -> List[Any]:
        return [e for e in self.enemies if getattr(e, "alive", True)]

    def first_living_index(self) -> Optional[int]:
        for i, c in enumerate(self.party):
            if getattr(c, "alive", True):
                return i
        return None

    def next_living_after(self, idx: int) -> Optional[int]:
        for j in range(idx + 1, len(self.party)):
            if getattr(self.party[j], "alive", True):
                return j
        return None

    # ============================================================
    # Start player's turn
    # ============================================================
    def begin_player_turn(self, actor) -> bool:
        # UI/view preparation only; does not control phase or CTB.

        actor_id = getattr(actor, "id", None)
        if actor_id is None:
            return False

        idx = None
        for i, member in enumerate(self.party):
            if getattr(member, "id", None) == actor_id:
                idx = i
                break

        if idx is None:
            return False

        member = self.party[idx]
        if not getattr(member, "alive", True):
            return False

        # Active actor for UI/menu rendering
        self.active_index = idx

        # Legacy view caches (keep if BattleUI/UIFlow still reads them)
        try:
            self.menu_index = 0
        except Exception:
            pass

        try:
            self.skills = self.get_skills_for(member.name)
        except Exception:
            # If registry fails, still allow turn; just show empty menu
            self.skills = []

        return True

    def execute_mapped_action(self, mapped: MappedAction) -> None:
        """
        Execute an enemy action fully through the skill pipeline.
        """
        from engine.battle.skills import registry

        enemy = mapped.user

        # If this enemy is somehow dead/KO before acting, bail.
        if not getattr(enemy, "alive", True):
            self.debug.enemy_ai(
                f"{getattr(enemy, 'name', '<??>')} is not alive; skipping action."
            )
            return

        # We'll store the resolver output here IF the action actually fires.
        result = None

        # 1) Look up the skill definition
        skill_def = registry.get(mapped.skill_id)
        meta: SkillMeta = skill_def.meta

        # 2) MP check & cost (mirrors player_confirm behavior)
        mp_cost = getattr(meta, "mp_cost", 0)
        if mp_cost > 0:
            current_mp = getattr(enemy, "mp", 0)
            if current_mp < mp_cost:
                # Not enough MP – log it and end the turn.
                self.debug.enemy_ai(
                    f"{getattr(enemy, 'name', '<??>')} tries to use {meta.name} "
                    f"but lacks the aether."
                )
                # XVII.18 – end-of-turn status ticking now lives in
                # ActionMapper._phase_post_resolve, not here.
                return
            # Pay the cost
            enemy.mp = current_mp - mp_cost


        # 3) Respect mapped targets, but filter to living ones
        if mapped.targets:
            targets = [t for t in mapped.targets if getattr(t, "alive", True)]
        else:
            targets = []

        # If no valid targets, end the turn gracefully
        if not targets:
            # XVII.18 – end-of-turn status ticking is handled in
            # ActionMapper._phase_post_resolve for this actor.
            self.debug.enemy_ai(
                f"{getattr(enemy, 'name', '<??>')} has no valid targets for {meta.name}."
            )
            return

        # 4) Resolve the skill mechanically
        result = SkillResolver.resolve(
            skill_def=skill_def,
            user=enemy,
            targets=targets,
            battle_state=self,
        )
        # XVII.13 – mirror into Runtime/ActionResolver (no behavior change)
        runtime = getattr(self, "runtime", None)
        if runtime is not None and hasattr(runtime, "capture_enemy_resolution"):
            try:
                runtime.capture_enemy_resolution(
                    enemy=enemy,
                    skill_def=skill_def,
                    targets=targets,
                    skill_result=result,
                )
            except Exception as exc:
                self.debug.enemy_ai(f"[RESOLVER] enemy mirror error: {exc!r}")

        # DEBUG: temporarily buff enemy damage for testing (XVII.6 knob)
        if ENEMY_DAMAGE_MULTIPLIER != 1.0:
            for change in result.targets:
                if change.damage:
                    change.damage = int(change.damage * ENEMY_DAMAGE_MULTIPLIER)
            self.debug.enemy_ai(
                f"{getattr(enemy, 'name', '<??>')} damage scaled by "
                f"{ENEMY_DAMAGE_MULTIPLIER}x for testing."
            )
        # 5) Status end-of-turn hooks (DOTs, regen, durations, etc.)
        # XVII.18 – moved to ActionMapper._phase_post_resolve
        # 6) Let runtime decide victory/defeat/continue for ENEMY turns
        runtime = getattr(self, "runtime", None)
        if result is not None and runtime is not None:
            runtime.finalize_enemy_action(mapped, result, self)

    # ------------------------------------------------------------
    # Turn management
    # ------------------------------------------------------------
    def set_active_actor(self, index: int) -> None:
        self.active_index = index
        actor = self.party[self.active_index]
        self.skills = self.get_skills_for(actor.name)
        self.menu_index = 0

    # ------------------------------------------------------------
    # Target selection for skills (based on SkillMeta.target_type)
    # ------------------------------------------------------------
    def _select_targets(self, actor: Any, meta: SkillMeta, primary_target: Any | None = None) -> List[Any]:
        """
        Returns a list of targets according to the skill's target_type.

        Supported target_type values:
          - "self"
          - "ally_single"
          - "ally_lowest"
          - "ally_all"
          - "enemy_single"
          - "enemy_all"
        """
        ttype = getattr(meta, "target_type", "enemy_single")

        # If the player provided an explicit primary target via the cursor,
        # prefer that for single-target skills. This is the first step
        # toward free-targeting and friendly fire.
        if primary_target is not None:
            # If the explicit target is dead, try to redirect to a living one
            if not getattr(primary_target, "alive", True):
                if ttype.startswith("enemy"):
                    candidates = self.living_enemies()
                    if not candidates:
                        return []
                    primary_target = candidates[0]
                elif ttype.startswith("ally"):
                    candidates = self.living_party()
                    if not candidates:
                        return []
                    primary_target = candidates[0]

            if ttype == "self":
                return [actor]
            if ttype == "ally_all":
                return self.living_party()
            if ttype == "enemy_all":
                return self.living_enemies()
            if ttype == "ally_lowest":
                candidates = self.living_party()
                if not candidates:
                    return []
                target = min(
                    candidates,
                    key=lambda c: c.hp / max(1, c.max_hp),
                )
                return [target]
            # Default: treat it as a single explicit target, regardless of side.
            return [primary_target]


        # --- existing logic (no primary_target, e.g. for AI) ---
        if ttype == "self":
            return [actor]

        if ttype == "ally_all":
            return self.living_party()

        if ttype == "ally_lowest":
            candidates = self.living_party()
            if not candidates:
                return []
            target = min(candidates, key=lambda c: c.hp / max(1, c.max_hp))
            return [target]

        if ttype == "ally_single":
            # For now, default to the actor themselves
            return [actor]

        if ttype == "enemy_all":
            return self.living_enemies()

        # Default: enemy_single
        enemies = self.living_enemies()
        return [enemies[0]] if enemies else []

    # ------------------------------------------------------------
    # FX routing helper
    # ------------------------------------------------------------
    def _build_choreo_request(
        self,
        actor: Any,
        meta: SkillMeta,
    ) -> ChoreoRequest:
        """
        Decide what kind of choreography to request based on the skill.

        For now:
        - healing / buffs / shields / revive → "spell"
        - everything else → "melee"

        Later you can refine this by element/tags.
        """
        supportive_categories = {"heal", "buff", "shield", "revive"}
        if meta.category in supportive_categories:
            kind = "spell"
            primary_target_index = None
        else:
            kind = "melee"
            # For enemy-targeting skills, compute the index directly from the
            # selected combatant object (no legacy targeting helpers).
            if meta.target_type.startswith("enemy"):
                primary_target_index = None
                pt = getattr(self, "pending_primary_target", None)
                if pt is not None and pt in self.enemies:
                    primary_target_index = self.enemies.index(pt)
            else:
                primary_target_index = None

        return ChoreoRequest(
            kind=kind,
            actor_id=getattr(actor, "name", "???"),
            primary_target_index=primary_target_index,
        )

    # ------------------------------------------------------------
    # BattleEvent builder from SkillResolutionResult
    # ------------------------------------------------------------
    def _build_battle_event_from_result(
        self,
        actor: Any,
        result: SkillResolutionResult,
    ) -> BattleEvent:
        """
        Convert a SkillResolutionResult into a legacy BattleEvent structure
        so the existing Arena/UI can continue to function.

        If there is exactly one target, we expose damage/heal on that target.
        If there are multiple, we leave damage/heal as None and rely on
        result.message and FX to convey what happened.
        """
        skill_obj = result.skill   # Could be SkillDefinition OR SkillMeta

        # Work out the metadata in a safe way
        if isinstance(skill_obj, SkillDefinition):
            skill_def = skill_obj
            meta: SkillMeta = skill_def.meta
        else:
            # Assume it's already a SkillMeta (or similar)
            skill_def = None
            meta = skill_obj

        choreo = self._build_choreo_request(actor, meta)

        target_entity: Any = None
        damage_val: Optional[int] = None
        heal_val: Optional[int] = None

        if len(result.targets) == 1:
            tc = result.targets[0]
            target_entity = tc.target
            damage_val = tc.damage or None
            heal_val = tc.healed or None

        msg = result.message or f"{getattr(actor, 'name', '???')} used {meta.name}!"

        return BattleEvent(
            actor=actor,
            target=target_entity,
            # Prefer to store the full SkillDefinition when available,
            # otherwise fall back to the meta itself.
            skill=skill_def or meta,
            damage=damage_val,
            heal=heal_val,
            message=msg,
            choreo=choreo,
            # NEW: FX metadata
            skill_id=getattr(meta, "id", None),
            fx_tag=getattr(meta, "fx_tag", None),
            element=getattr(meta, "element", None),
        )

    # ------------------------------------------------------------
    # Reset battle (used by Arena)
    # ------------------------------------------------------------
    def reset_battle(self) -> None:
        for c in self.party:
            c.hp = c.max_hp
            if hasattr(c, "max_mp"):
                c.mp = c.max_mp

        for e in self.enemies:
            e.hp = e.max_hp
            if hasattr(e, "max_mp"):
                e.mp = e.max_mp

        first_idx = self.first_living_index() or 0

        self.state = "player_turn"
        self.menu_index = 0
        self.active_index = first_idx
        self.skills = self.get_skills_for(self.party[first_idx].name)


    # ------------------------------------------------------------
    # Debug helpers – Forge XIII.6 (now delegated to BattleDebug)
    # ------------------------------------------------------------
    def debug_print_targets(self) -> None:
        """
        Delegate to the centralized BattleDebug helper so this file
        stays slimmer. The heavy formatting lives in debug_logger.py.
        """
        self.debug.targets_snapshot(self)

