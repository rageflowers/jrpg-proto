from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Any, Callable, List, Sequence, TYPE_CHECKING
from engine.battle.status.effects import roll_dot_land

from game.debug.debug_logger import log as battle_log

from .base import (
    SkillEffect,
    SkillResolutionResult,
    ElementType,
    TargetChange,
)

if TYPE_CHECKING:
    # Only for type-checkers; at runtime we don't require a concrete status class.
    from engine.battle.status.effects import StatusEffect, roll_dot_land  # type: ignore[misc]
from engine.battle.status.effects import roll_dot_land


DamageType = str  # "physical", "magic", "mixed"
# ---------------------------------------------------------------------------
# SkillEffect / Result contract – Forge XVII.16
# ---------------------------------------------------------------------------
# This module implements concrete SkillEffect subclasses (DamageEffect,
# HealEffect, status application, etc.) that all follow the same pattern:
#
#   - SkillResolver builds a SkillResolutionResult and then calls:
#         effect.apply(user, targets, battle_state, result)
#     for each SkillEffect in the SkillDefinition.effects list.
#
#   - Each effect is responsible for BOTH:
#         1) Applying its mechanical changes immediately to the battle state
#            (HP, MP, statuses on the underlying combatant objects).
#         2) Recording what happened into the shared SkillResolutionResult
#            via TargetChange entries.
#
# TargetChange invariants:
#   - There is at most one TargetChange per concrete target object in
#     SkillResolutionResult.targets.
#   - All effects that interact with the same target MUST reuse that
#     TargetChange via _get_or_create_target_change(result, target).
#   - Damage and healing are *additive* across effects:
#         tc.damage += <amount>
#         tc.healed += <amount>
#
# Multi-component skills:
#   - A single skill may contain multiple DamageEffect instances (e.g.
#     Setia's Wind Strike uses one physical component and one magical
#     component).
#   - Each DamageEffect applies its share of damage and writes into the
#     same TargetChange for a given target, so the final TargetChange.damage
#     is the sum of all components for that target.
#
# ActionResolver and BattleSession:
#   - Downstream, ActionResolver reads SkillResolutionResult.targets and
#     converts each TargetChange into a TargetResult with a single HP delta
#     (negative for damage, positive for healing).
#   - BattleSession.apply_action_result() then applies those HP/MP deltas
#     to the underlying combatants.
#
# Forge XVII.16 builds on this contract and clarifies multi-component
# semantics without changing the basic shape of SkillResolutionResult.


def _get_or_create_target_change(result: SkillResolutionResult, target: Any) -> TargetChange:
    """Find or create the TargetChange entry for a given target."""
    for tc in result.targets:
        if tc.target is target:
            return tc
    tc = TargetChange(target=target)
    result.targets.append(tc)
    return tc


# ---------------------------------------------------------------------------
# Core mechanical effects
# ---------------------------------------------------------------------------
@dataclass
class ChanceStatusEffect(SkillEffect):
    status_factory: Callable[[Any, Any, Any], "StatusEffect"]
    chance: float = 1.0

    def apply(self, user, targets, battle_state, result):
        p = max(0.0, min(1.0, float(self.chance)))
        if p <= 0.0:
            return

        triggered_any = False
        proc_names: list[str] = []

        for t in targets:
            if hasattr(t, "hp") and getattr(t, "hp") <= 0:
                continue

            if random.random() >= p:
                continue

            status_mgr = getattr(t, "status", None)
            if status_mgr is None:
                continue

            status = self.status_factory(user, t, battle_state)
            status_mgr.add(status, context=battle_state)

            tc = _get_or_create_target_change(result, t)
            tc.status_applied.append(status.id)

            triggered_any = True
            proc_names.append(getattr(status, "name", status.id))

        if triggered_any:
            base_msg = result.message or ""
            extra = " " + " ".join(f"{name} takes hold!" for name in proc_names)
            result.message = (base_msg + extra).strip()

@dataclass
class DamageEffect(SkillEffect):
    """
    Basic damage effect.

    Forge XVII.18c:

      - This effect is responsible for computing a single base_damage value
        that already includes the user's effective ATK/MAG and any scaling.

      - engine.battle.damage.compute_damage() then:

          * applies DEF/MRES mitigation
          * applies variance
          * feeds the result into the status pipeline (shields, reflect, etc.)
    """

    # Flat component that can always be added on top
    base_damage: int
    element: ElementType = "none"
    damage_type: DamageType = "magic"
    hit_all: bool = False

    # Optional MAG-ratio scaling (legacy elemental spells)
    mag_ratio: float | None = None

    # Hybrid scaling metadata (Wind Strike, melee skills, etc.)
    scaling: str | None = None   # "atk" or "mag"
    coeff: float = 1.0

    def compute_base_damage(self, user: Any, target: Any, battle_state: Any) -> int:
        """
        Compute the base_damage BEFORE defenses/variance.

        Priority:
          1) If scaling is set ("atk" or "mag"), use effective stat * coeff (+ power).
          2) Else if mag_ratio is set, use effective MAG * mag_ratio (+ power).
          3) Else use the fixed power value.
        """
        from engine.battle.damage import _get_effective_stats

        eff = _get_effective_stats(user)
        base = 0.0

        # --- 1) Explicit scaling path (preferred) ---
        if self.scaling == "atk":
            stat_val = eff["atk"]
            base = stat_val * float(self.coeff)
        elif self.scaling == "mag":
            stat_val = eff["mag"]
            base = stat_val * float(self.coeff)
        else:
            stat_val = 0  # for clarity

        if self.scaling is not None:
            base += float(self.base_damage or 0)
            return max(1, int(base))

        # --- 2) Legacy MAG scaling path ---
        if self.mag_ratio is not None:
            mag_val = eff["mag"]
            base = mag_val * float(self.mag_ratio)
            base += float(self.base_damage or 0)
            return max(1, int(base))

        # --- 3) Pure flat power ---
        return max(1, int(self.base_damage))

    def apply(
        self,
        user: Any,
        targets: Sequence[Any],
        battle_state: Any,
        result: SkillResolutionResult,
    ) -> None:
        """
        Core damage application for skills.

        Forge XVII.18c flow:

          1) compute_base_damage() → pre-defense base_damage
          2) compute_damage() → apply DEF/MRES + variance → raw
          3) StatusManager.apply_incoming_damage_modifiers() →
             shields, Fire Shield reflect, bonus heals, retaliation events
          4) Apply final HP changes directly to the target
          5) Hand retaliation events to 
          6) Log + FX

        battle_state is the BattleController.
        """
        from engine.battle.damage import compute_damage
        from game.debug.debug_logger import log as battle_log

        for t in targets:
            # Skip dead/KO targets
            if hasattr(t, "hp") and getattr(t, "hp") <= 0:
                continue

            # 1) Pre-defense base_damage from user stats + skill scaling
            base_damage = self.compute_base_damage(user, t, battle_state)

            # 2) Shared damage model: DEF/MRES + variance
            base, breakdown = compute_damage(
                attacker=user,
                defender=t,
                element=self.element,
                base_damage=base_damage,
                damage_type=self.damage_type,
            )

            # 3) Status pipeline (Fire Shield, barriers, reflect, etc.)
            status_mgr = getattr(t, "status", None)
            modified = base
            bonus_heal = 0
            from engine.battle.status.status_events import StatusEvent
            retaliation_events: list[StatusEvent] = []


            if status_mgr is not None:
                ctx = {
                    "attacker": user,
                    "battle_state": battle_state,
                }
                modified, bonus_heal, retaliation_events = status_mgr.apply_incoming_damage_modifiers(
                    amount=base,
                    element=self.element,
                    damage_type=self.damage_type,
                    context=ctx,
                )

            # 4) Apply HP changes directly on the target
            before_hp = getattr(t, "hp", None)

            if modified > 0:
                if hasattr(t, "take_damage"):
                    t.take_damage(modified)
                elif hasattr(t, "hp"):
                    t.hp = max(0, int(t.hp) - int(modified))

            if bonus_heal > 0:
                if hasattr(t, "heal"):
                    t.heal(bonus_heal)
                elif hasattr(t, "hp") and hasattr(t, "max_hp"):
                    t.hp = min(int(t.max_hp), int(t.hp) + int(bonus_heal))

            after_hp = getattr(t, "hp", None)

            # 5) Emit FX via Runtime (optional, safe if missing)
            runtime = getattr(battle_state, "runtime", None)
            if runtime is not None and hasattr(runtime, "emit_basic_hit_fx") and modified > 0:
                try:
                    runtime.emit_basic_hit_fx(
                        source=user,
                        target=t,
                        damage=modified,
                        element=self.element,
                        killing_blow=bool(
                            before_hp is not None
                            and before_hp > 0
                            and after_hp == 0
                        ),
                        is_enemy=getattr(user, "is_enemy", False),
                        arena=getattr(battle_state, "arena", None),
                    )
                except Exception:
                    # FX failures shouldn't break the battle
                    pass

            # 6) Update SkillResolutionResult
            tc = _get_or_create_target_change(result, t)
            tc.damage += modified
            if bonus_heal > 0:
                tc.healed += bonus_heal

            # 7) Queue retaliation events into the immediate bucket (no BattleController mutation)
            if retaliation_events:
                result.status_events.extend(retaliation_events)

            # 8) Logging
            dbg = getattr(battle_state, "debug", None)
            msg = (
                f"[BATTLE SKILL] [DMG] {getattr(user, 'name', '?')} "
                f"-> {getattr(t, 'name', '?')} "
                f"| type={self.damage_type}, element={self.element} "
                f"| base_damage={base_damage}, raw={base}, "
                f"final={modified}, bonus_heal={bonus_heal}"
            )
            if dbg is not None and hasattr(dbg, "runtime"):
                dbg.runtime(msg)
            else:
                battle_log("skill", msg)

@dataclass
class HealEffect(SkillEffect):
    """
    Simple healing effect.

    power:
        Base heal amount. You can later adapt this to scale with MAG or
        max HP if desired.
    """

    base_heal: int
    # Whether to clamp heal so we don't heal dead targets (can be changed later).
    skip_if_dead: bool = True

    def compute_heal_amount(self, user: Any, target: Any, battle_state: Any) -> int:
        # TODO: later, include scaling by MAG or healing power.
        return max(0, self.base_heal)

    def apply(
        self,
        user: Any,
        targets: Sequence[Any],
        battle_state: Any,
        result: SkillResolutionResult,
    ) -> None:
        for t in targets:
            # Basic life-state check
            if self.skip_if_dead and hasattr(t, "hp") and getattr(t, "hp") <= 0:
                continue

            amt = self.compute_heal_amount(user, t, battle_state)
            if amt <= 0:
                continue

            # ❗ No direct HP mutation here. Just record the heal for downstream.
            tc = _get_or_create_target_change(result, t)
            tc.healed += int(amt)

@dataclass
class MPDeltaEffect(SkillEffect):
    """
    Adjusts MP for targets (or for the user).

    mp_delta:
        Positive to restore MP, negative to drain/spend MP.

    apply_to_user:
        If True, use `user` as the target instead of the provided targets list.
    """

    mp_delta: int
    apply_to_user: bool = False

    def apply(
        self,
        user: Any,
        targets: Sequence[Any],
        battle_state: Any,
        result: SkillResolutionResult,
    ) -> None:
        actual_targets = [user] if self.apply_to_user else list(targets)
        for t in actual_targets:
            if not hasattr(t, "mp") or not hasattr(t, "max_mp"):
                continue

            before = t.mp
            # Compute clamped MP after this effect, but don't apply it yet.
            after = max(0, min(t.max_mp, t.mp + self.mp_delta))
            delta = after - before

            if delta == 0:
                continue

            tc = _get_or_create_target_change(result, t)
            tc.mp_delta += int(delta)

@dataclass
class ApplyStatusEffect(SkillEffect):
    """
    Applies a status effect to each target.

    status_factory:
        A callable that, when invoked as
            status_factory(user, target, battle_state),
        returns a *new* StatusEffect instance.

        This indirection keeps this module generic: it doesn't need to know about
        concrete status classes like FireShieldStatus / PoisonStatus.
    """

    status_factory: Callable[[Any, Any, Any], "StatusEffect"]  # type: ignore[name-defined]
    apply_to_user: bool = False

    def apply(
        self,
        user: Any,
        targets: Sequence[Any],
        battle_state: Any,
        result: SkillResolutionResult,
    ) -> None:
        for t in targets:
            status_mgr = getattr(t, "status", None)
            if status_mgr is None:
                continue

            status = self.status_factory(user, t, battle_state)
            if status is None:
                continue

            tags = getattr(status, "tags", None) or set()
            status_id = getattr(status, "id", "") or ""
            damage_type = getattr(status, "dot_damage_type", None)

            # ------------------------------------------------------
            # DoT landing logic (Poison, Bleed, Burn, etc.)
            # Only applies to statuses tagged as "dot" AND that
            # declare a dot_damage_type of "physical" or "magic".
            # ------------------------------------------------------
            if "dot" in tags and damage_type in ("physical", "magic"):
                landed, roll, chance = roll_dot_land(user, t, damage_type)

                if not landed:
                    # Friendly debug + flavor message
                    if status_id == "poison":
                        msg = f"Poisoning failed on {t.name}"
                    elif status_id == "bleed":
                        msg = f"{t.name} avoids bleed"
                    elif status_id == "burn":
                        msg = f"Burn fails to ignite on {t.name}"
                    else:
                        msg = f"{status.name} fails to take hold on {t.name}"

                    battle_log(
                        "status",
                        f"[DOT FAIL] {msg} "
                        f"(roll={roll:.2f}, chance={chance:.2f})",
                    )
                    # Do not add the status if it failed to land
                    continue

            # ------------------------------------------------------
            # If we get here, either:
            #   - it's not a DoT, or
            #   - it is a DoT that successfully passed the land check.
            # For now, all skill-applied statuses are from a spell,
            # so from_shield=False. FireShield will use a custom context
            # later when it applies Burn on retaliation.
            # ------------------------------------------------------
            status_mgr.add(status, context={"attacker": user})

            tc = _get_or_create_target_change(result, t)
            tc.status_applied.append(status.id)

@dataclass
class ApplyStatusToUserEffect(SkillEffect):
    """
    Applies a status to the *user* of the skill (self-buffs like Flow I).
    """

    status_factory: Callable[[Any, Any, Any], "StatusEffect"]  # type: ignore[name-defined]

    def apply(
        self,
        user: Any,
        targets: Sequence[Any],
        battle_state: Any,
        result: SkillResolutionResult,
    ) -> None:
        status_mgr = getattr(user, "status", None)
        if status_mgr is None:
            return

        status = self.status_factory(user, user, battle_state)
        status_mgr.add(status, context=battle_state)

        tc = _get_or_create_target_change(result, user)
        tc.status_applied.append(status.id)

@dataclass
class ChanceStatusOnHitEffect(SkillEffect):
    """
    Applies a status effect to each target with a given probability,
    but only if they actually took damage from a previous effect.

    Intended usage:
      - Place this AFTER a DamageEffect in a skill's effects list.
      - It will look at the SkillResolutionResult to see how much
        damage each target took, and only apply the status if
        damage > 0 and random() < chance.

    Perfect for:
      - Ember Bolt (25% Burn I on hit)
      - Frost Shot (25% Frostbite I on hit)
    """

    chance: float
    status_factory: Callable[[Any, Any, Any], "StatusEffect"]  # type: ignore[name-defined]

    def apply(
        self,
        user: Any,
        targets: Sequence[Any],
        battle_state: Any,
        result: SkillResolutionResult,
    ) -> None:
        from random import random

        for t in targets:
            # Find existing TargetChange (if any). We only want to proc on
            # targets that actually took damage earlier in this skill.
            tc = None
            for existing in result.targets:
                if existing.target is t:
                    tc = existing
                    break

            # If no TargetChange yet, or no damage, we skip.
            if tc is None or tc.damage <= 0:
                continue

            # Roll the per-target proc chance.
            if random() >= self.chance:
                continue

            status_mgr = getattr(t, "status", None)
            if status_mgr is None:
                continue

            # Build the status instance.
            status = self.status_factory(user, t, battle_state)
            if status is None:
                continue

            # Build a DOT-friendly / general context:
            # - attacker: who applied the status (for snapshot damage, etc.)
            # - runtime/arena: optional, for FX hooks.
            ctx: dict[str, object] = {"attacker": user}

            runtime = getattr(battle_state, "runtime", None)
            arena = getattr(battle_state, "arena", None)

            if runtime is not None:
                ctx["runtime"] = runtime
            if arena is not None:
                ctx["arena"] = arena

            status_mgr.add(status, context=ctx)

            # Record in SkillResolutionResult so FX / logs can see it.
            tc.status_applied.append(status.id)


@dataclass
class RemoveStatusByIdEffect(SkillEffect):
    """
    Removes specific statuses by id (exact match).

    Useful for targeted dispels or custom interactions.
    """

    status_ids: List[str] = field(default_factory=list)

    def apply(
        self,
        user: Any,
        targets: Sequence[Any],
        battle_state: Any,
        result: SkillResolutionResult,
    ) -> None:
        for t in targets:
            status_mgr = getattr(t, "status", None)
            if status_mgr is None:
                continue

            removed_ids: List[str] = []
            for e in list(status_mgr.effects):
                if e.id in self.status_ids:
                    removed_ids.append(e.id)
                    status_mgr.remove(e, context=battle_state)

            if removed_ids:
                tc = _get_or_create_target_change(result, t)
                tc.status_removed.extend(removed_ids)


@dataclass
class RemoveStatusByTagEffect(SkillEffect):
    """
    Removes statuses that contain any of the given tags.

    Example:
        tags={"poison", "shadow_slow"}
    """

    tags: set[str] = field(default_factory=set)

    def apply(
        self,
        user: Any,
        targets: Sequence[Any],
        battle_state: Any,
        result: SkillResolutionResult,
    ) -> None:
        for t in targets:
            status_mgr = getattr(t, "status", None)
            if status_mgr is None:
                continue

            removed_ids: List[str] = []
            for e in list(status_mgr.effects):
                if self.tags.intersection(e.tags):
                    removed_ids.append(e.id)
                    status_mgr.remove(e, context=battle_state)

            if removed_ids:
                tc = _get_or_create_target_change(result, t)
                tc.status_removed.extend(removed_ids)


@dataclass
class ReviveEffect(SkillEffect):
    """
    Revives KO'd allies.

    heal_amount:
        Fixed amount of HP to restore on revive. Later you can make this a ratio
        of max HP or scale with MAG.
    """

    heal_amount: int

    def apply(
        self,
        user: Any,
        targets: Sequence[Any],
        battle_state: Any,
        result: SkillResolutionResult,
    ) -> None:
        for t in targets:
            if not hasattr(t, "hp") or not hasattr(t, "max_hp"):
                continue

            if getattr(t, "hp") > 0:
                # Not dead, nothing to revive.
                continue

            # Basic revive: set HP to heal_amount, clamped to max_hp.
            new_hp = max(1, min(t.max_hp, self.heal_amount))
            t.hp = new_hp

            tc = _get_or_create_target_change(result, t)
            tc.was_revived = True
            tc.healed += new_hp
