# engine/battle/status/effects.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import random
from game.debug.debug_logger import log as battle_log
from engine.battle.status.status_events import DamageTickEvent
DamageType = str  # e.g. "physical", "magic", "mixed"
ElementType = str  # e.g. "fire", "ice", "holy", "shadow", "wind", "none"

# ----------------------------------------------------------------------
# DOT landing helpers (ATK vs DEF, MAG vs MRES)
# ----------------------------------------------------------------------

def _compute_hit_chance(
    attacker_stat: int,
    defender_stat: int,
    *,
    base: float = 0.70,
    slope: float = 0.03,
    min_chance: float = 0.10,
    max_chance: float = 0.95,
) -> float:
    """
    Generic stat-vs-stat chance curve.

    - base:    baseline chance when stats are equal (e.g. 70%)
    - slope:   how quickly chance shifts per point of difference
    - clamps:  so it never becomes 0% or 100%
    """
    delta = attacker_stat - defender_stat
    chance = base + slope * float(delta)
    if chance < min_chance:
        chance = min_chance
    elif chance > max_chance:
        chance = max_chance
    return chance


def compute_dot_land_chance(
    attacker: Any,
    defender: Any,
    damage_type: DamageType,
) -> float:
    """
    Returns the chance [0.0–1.0] for a DoT to land, based on:

        physical DOTs  → ATK vs DEF
        magical DOTs   → MAG vs MRES

    This is *only* the probability; rolling happens in the caller.
    """
    if damage_type == "magic":
        atk_val = int(getattr(attacker, "mag", 0))
        def_val = int(getattr(defender, "mres", 0))
    else:
        # treat anything else as physical for now
        atk_val = int(getattr(attacker, "atk", 0))
        def_val = int(getattr(defender, "defense", 0))

    return _compute_hit_chance(atk_val, def_val)


def roll_dot_land(
    attacker: Any,
    defender: Any,
    damage_type: DamageType,
) -> tuple[bool, float, float]:
    """
    Convenience helper:

        landed, roll, chance = roll_dot_land(attacker, defender, "physical"|"magic")

    - chance comes from compute_dot_land_chance()
    - roll is random.random()
    - landed = (roll <= chance)
    """
    chance = compute_dot_land_chance(attacker, defender, damage_type)
    roll = random.random()
    return roll <= chance, roll, chance

def get_status_fx_meta(status):
    """
    Returns structured FX metadata about a status effect.
    Used by Runtime when emitting FX events.
    """
    kind = "unknown"
    element = None

    # DOTs
    if isinstance(status, DotStatus):
        kind = "dot"
        element = getattr(status, "element", None)

    # HOTs – placeholder for later, once you have a concrete HotStatus type.
    # try:
    #     from engine.battle.status.hot import HotStatus  # example path
    #     if isinstance(status, HotStatus):
    #         kind = "hot"
    #         element = getattr(status, "element", None)
    # except ImportError:
    #     pass

    # Buffs / debuffs (if you later attach flags like is_buff/is_debuff)
    if getattr(status, "is_buff", False):
        kind = "buff"

    if getattr(status, "is_debuff", False):
        kind = "debuff"

    return {
        "kind": kind,
        "element": element,
        "status_key": getattr(status, "id", None) or getattr(status, "name", None),
        "status_name": status.__class__.__name__,
    }


@dataclass
class StatusEffect:
    """
    Base class for any ongoing status affecting a combatant.

    This is intentionally generic and light. Concrete subclasses handle:
      - stat modifiers (ATK/DEF/MAG/MRES/SPD etc.)
      - per-turn regen / damage
      - shields (Fire/Ice, generic barriers)
      - debuffs (poison, slow, mindrot, etc.)

    Durations are expressed in *turns of the owner*:
      - Typically decremented after the owner takes a turn.
    """

    id: str                   # Unique string identifier, e.g. "nyra_affirmation"
    name: str                 # For UI display
    duration_turns: int       # Remaining full turns
    dispellable: bool = True  # Can be removed by cleanse-like skills
    stackable: bool = False   # If False, re-applying replaces the old one
    tags: set[str] = field(default_factory=set)

    # --- Lifecycle -----------------------------------------------------

    def on_apply(self, owner: Any, context: Any) -> None:
        """Called once when the status is first added."""
        pass

    def on_expire(self, owner: Any, context: Any) -> None:
        """Called once when the status is removed (duration <= 0 or dispelled)."""
        pass

    # --- Turn-based hooks ----------------------------------------------

    def on_turn_start(self, owner: Any, context: Any) -> None:
        """Called at the start of owner's turn BEFORE they act."""
        pass

    def on_turn_end(self, owner: Any, context: Any) -> None:
        """Called at the end of owner's turn AFTER they act."""
        pass

    # --- Action hooks --------------------------------------------------

    def on_before_owner_acts(self, owner: Any, context: Any) -> None:
        """Called right before the owner performs an action."""
        pass

    # --- Damage hooks --------------------------------------------------

    def on_before_owner_takes_damage(
        self,
        owner: Any,
        amount: int,
        element: ElementType,
        damage_type: DamageType,
        context: Any,
    ) -> Tuple[int, int, List[Dict[str, Any]]]:
        """
        Called before the owner takes damage.

        Returns:
            (modified_amount, bonus_heal, retaliation_events)

        - modified_amount: the new damage after reductions/shields.
        - bonus_heal: healing to apply to the owner (e.g. elemental shield absorb).
        - retaliation_events: a list of side effects the BattleController
          can process, e.g. "apply burn to attacker", "slow attacker", etc.

        retaliation_events are free-form dicts that the battle logic can interpret.
        Example:
            {"kind": "apply_status", "target": attacker, "status_factory": some_func}
        """
        return amount, 0, []

    def modify_stat_modifiers(self, modifiers: Dict[str, float]) -> None:
        """
        Adjusts the stat modifiers dict in-place.

        The dict uses a simple naming convention:
          - atk_mult, def_mult, mag_mult, mres_mult, spd_mult: multiplicative factors
          - atk_add,  def_add,  mag_add,  mres_add,  spd_add: flat additions

        Example:
            modifiers["def_mult"] *= 1.25
            modifiers["spd_mult"] *= 0.8
        """
        pass

# ----------------------------------------------------------------------
# Basic building blocks: regen, DOT, generic buffs
# ----------------------------------------------------------------------

@dataclass
class RegenStatus(StatusEffect):
    """
    Simple regen-over-time status.

    Now fully migrated to the unified pipeline:
    - Does NOT directly mutate HP.
    - Emits a DamageTickEvent, which ActionMapper converts to an
      ActionResult and routes through BattleSession.apply_action_result.
    """

    def __init__(
        self,
        id: str,
        name: str,
        duration_turns: int,
        dispellable: bool = True,
        stackable: bool = False,
        heal_per_turn: int = 0,
    ) -> None:
        super().__init__(
            id=id,
            name=name,
            duration_turns=duration_turns,
            dispellable=dispellable,
            stackable=stackable,
        )
        self.heal_per_turn = int(heal_per_turn)

    def on_turn_end(self, owner, context=None):
        """
        XVII.18 – migrated path:
        - No direct owner.heal().
        - Only emits DamageTickEvent with a positive amount.

        HP actually changes when ActionMapper builds an ActionResult from
        these events and BattleSession.apply_action_result applies it.
        """
        amount = self.heal_per_turn
        if amount == 0:
            return []

        # Optional debug log so you still see regen in the DOT log channel.
        if context is not None:
            dbg = getattr(context, "debug", None)
            if dbg is not None and hasattr(dbg, "runtime"):
                dbg.runtime(
                    f"[DOT HP] {owner.name} will heal {amount} from {self.name} via Session"
                )

        event = DamageTickEvent(
            target=owner,
            amount=amount,                 # positive = healing
            kind="regen",                  # key we’ll filter on in ActionMapper
            damage_type="none",            # neutral; not physical/magic damage
            source_status_id=self.id,
            source_combatant=None,
        )
        return [event]

@dataclass
class DamageOverTimeStatus(StatusEffect):
    """
    Simple damage-over-time effect: poison, burn, etc.

    damage_per_turn can later be extended to scale with MAG or weapon potency.
    """

    damage_per_turn: int = 0
    element: ElementType = "none"

    def on_turn_end(self, owner: Any, context: Any) -> None:
        if self.damage_per_turn <= 0:
            return
        owner.take_damage(self.damage_per_turn)


@dataclass
class StatBuffStatus(StatusEffect):
    """
    Generic stat buff/debuff.

    Example usage:
        # +25% DEF, +10 flat DEF, -10% SPD
        StatBuffStatus(
            id="nyra_affirmation",
            name="Affirmation",
            duration_turns=3,
            mults={"def_mult": 1.25, "spd_mult": 0.9},
            adds={"def_add": 10},
        )
    """

    mults: Dict[str, float] = field(default_factory=dict)
    adds: Dict[str, float] = field(default_factory=dict)

    def modify_stat_modifiers(self, modifiers: Dict[str, float]) -> None:
        for key, factor in self.mults.items():
            modifiers[key] = modifiers.get(key, 1.0) * factor
        for key, inc in self.adds.items():
            modifiers[key] = modifiers.get(key, 0.0) + inc


# ---------------------------------------------------------------------------
# Elemental Shields (Embered Guard / Chill Ward)
# ---------------------------------------------------------------------------
  

class IceShieldStatus(StatusEffect):
    """
    Chill Ward (T1)

    -15% Physical damage taken
    -20% Ice damage taken
    No reflect damage
    Always applies Frostbite I via retaliation event ("frostbite")
    """

    def __init__(
        self,
        id: str,
        name: str,
        duration_turns: int,
        dispellable: bool = True,
        stackable: bool = False,
        *,
        phys_reduction: float = 0.15,
        magic_reduction: float = 0.0,
        elemental_heal_ratio: float = 0.0,
        retaliation_kind: str | None = "frostbite",
        retaliation_chance: float = 1.0,
        tier: int = 1,
    ):
        super().__init__(
            id=id,
            name=name,
            duration_turns=duration_turns,
            dispellable=dispellable,
            stackable=stackable,
        )

        self.phys_reduction = phys_reduction
        self.magic_reduction = magic_reduction
        self.elemental_heal_ratio = elemental_heal_ratio
        self.retaliation_kind = retaliation_kind or "frostbite"
        self.retaliation_chance = retaliation_chance
        self.tier = tier

        self.icon_type = "buff"
        self.icon_id = "shield_ice"

    def on_before_owner_takes_damage(
        self,
        owner,
        amount: int,
        element: str,
        damage_type: str,
        context,
    ):
        """
        Chill Ward (T1+):

        Uses instance attributes configured by the factory:
          - self.phys_reduction       (e.g. 0.15)
          - self.magic_reduction      (repurposed as ice_reduction, e.g. 0.20)
          - self.elemental_heal_ratio (fraction of ICE turned into heal)

        No reflect damage. Emits Frostbite I retaliation.
        """
        if amount <= 0:
            return amount, 0, []

        raw_amount = amount

        phys_red = float(getattr(self, "phys_reduction", 0.0) or 0.0)
        ice_red = float(getattr(self, "magic_reduction", 0.0) or 0.0)
        heal_ratio = float(getattr(self, "elemental_heal_ratio", 0.0) or 0.0)

        if element == "physical":
            amount = int(raw_amount * (1.0 - phys_red))
        elif element == "ice":
            amount = int(raw_amount * (1.0 - ice_red))
        else:
            amount = raw_amount
        from engine.battle.status.status_events import StatusEvent
        retaliation_events: list[StatusEvent] = []
        attacker = context.get("attacker") if isinstance(context, dict) else None

        # Matching-element heal (ice)
        if element == "ice" and heal_ratio > 0.0 and raw_amount > 0:
            heal_amount = max(1, int(raw_amount * heal_ratio))

            if hasattr(owner, "heal"):
                owner.heal(heal_amount)
            elif hasattr(owner, "hp") and hasattr(owner, "max_hp"):
                owner.hp = min(owner.max_hp, owner.hp + heal_amount)

        # Frostbite retaliation event (StatusEvent, not dict)
        if attacker is not None:
            from engine.battle.status.status_events import ApplyStatusEvent
            from engine.battle.skills.statuses import make_frostbite_basic

            battle_state = context.get("battle_state") if isinstance(context, dict) else None

            retaliation_events.append(
                ApplyStatusEvent(
                    target=attacker,
                    status=make_frostbite_basic(owner, attacker, battle_state),
                    source_combatant=owner,
                    reason="chill_ward_retaliation",
                )
            )


        return amount, 0, retaliation_events



# ----------------------------------------------------------------------
# Canonical basic statuses for Forge XVI.0
# ----------------------------------------------------------------------

@dataclass
class DefendStatus(StatBuffStatus):
    """
    Defend (1 turn):
      - +25% DEF
      - +15% MRES

    Pure stat modifiers only (no direct damage scaling here).
    """
    def __post_init__(self) -> None:
        if not self.id:
            self.id = "defend_1"
        if not self.name:
            self.name = "Defend"

        self.tags.add("defend")
        self.tags.add("buff")
        self.tags.add("defense")
        self.tags.add("mres")

        # Set defaults if caller didn't provide
        if not self.mults:
            self.mults = {"def_mult": 1.25, "mres_mult": 1.15}

# =====================================================================
# DOT BASE CLASS
# =====================================================================
class DotStatus(StatusEffect):
    """
    Base for snapshot-style DoTs used by Poison, Bleed, Burn.
    This status:
      - Stores snapshot attacker stats & victim stats at application time
      - Computes base_total and per-tick upfront
      - Deals damage ONLY on victim's turn end
    """

    # Should be overridden by child classes:
    dot_element = "none"       # "poison", "bleed", "fire"
    dot_damage_type = "physical"  # or "magic"
    dot_potency = 0.2          # how much DEF/MRES reduces the DoT per tick
    base_power_scalar = 1.0    # scalar fed into compute_damage()
    max_stacks = 1             # Poison=1, Bleed=3, Burn=3

    # StatusEffect defaults
    stackable = True           # Bleed/Burn need this; Poison overridden to False

    def __post_init__(self):
        # Required fields: id, name, icon, tags
        if not self.id:
            self.id = self.dot_element
        if not self.name:
            self.name = self.dot_element.capitalize()

        self.tags.add("dot")
        self.element = self.dot_element

        # computed later in on_apply
        self.per_tick = 0
        self.base_total = 0
        self.snapshot_def_or_mres = 0
        self.source = None     # attacker
        self.is_from_shield = False

    # -----------------------------------------------------------------
    def compute_base_total(self, owner, context):
        """Runs once on_apply: ATK/MAG vs DEF/MRES → base_total.

        Forge XVII.18c:
          - We treat base_damage as already including the attacker's effective
            ATK/MAG and this status's scalar.
          - compute_damage then only applies defensive mitigation + variance.
        """
        from engine.battle.damage import compute_damage, _get_effective_stats

        attacker = self.source
        defender = owner

        # If we have a valid attacker, use their effective stats (with buffs)
        # to build a pre-defense base_damage. Otherwise fall back to a flat
        # scalar so shield-generated DoTs still do *something*.
        offensive = 0.0
        if attacker is not None:
            eff = _get_effective_stats(attacker)
            if self.dot_damage_type == "magic":
                offensive = eff["mag"]
            else:
                offensive = eff["atk"]

        base_damage = offensive * float(self.base_power_scalar)
        if base_damage <= 0:
            # Fallback: treat scalar alone as base_damage so we don't end up
            # with a permanent 1-damage DoT when attacker is unknown.
            base_damage = float(self.base_power_scalar)

        base_total, breakdown = compute_damage(
            attacker=attacker,
            defender=defender,
            element=self.dot_element,
            damage_type=self.dot_damage_type,
            base_damage=base_damage,
        )

        return max(0, int(base_total))

    # -----------------------------------------------------------------
    def on_apply(self, owner, context):
        """
        Snapshot victim and attacker stats,
        compute base_total and per_tick.
        """
        attacker = None
        from_shield = False

        if isinstance(context, dict):
            attacker = context.get("attacker")
            from_shield = context.get("from_shield", False)
        else:
            # Fallback for object-style context (e.g. BattleController)
            attacker = getattr(context, "attacker", None)
            from_shield = getattr(context, "from_shield", False)

        self.source = attacker
        self.is_from_shield = from_shield

        # Snapshot defense stat
        if self.dot_damage_type == "physical":
            self.snapshot_def_or_mres = getattr(owner, "defense", 0)
        else:  # magic DoT
            self.snapshot_def_or_mres = getattr(owner, "mres", 0)

        # Compute total fire/poison/bleed potential
        self.base_total = self.compute_base_total(owner, context)

        # Duration is already set by factory (bleed 2 turns, poison 4, etc.)
        turns = max(1, self.duration_turns)

        per_tick_raw = self.base_total / turns

        # Apply victim mitigation
        mitigated = per_tick_raw - self.snapshot_def_or_mres * self.dot_potency
        self.per_tick = max(1, int(mitigated))

        battle_log(
            "status",
            f"[DOT APPLY] {self.name} applied to {owner.name}: "
            f"per_tick={self.per_tick}, duration={self.duration_turns}, "
            f"from={'shield' if self.is_from_shield else 'spell'}",
        )
        # --------------------------------------------------
        # FX hook: notify Runtime so FXSystem can react
        # (Runtime is optional and comes from context when present.)
        # --------------------------------------------------
        runtime = None
        arena = None
        if isinstance(context, dict):
            runtime = context.get("runtime")
            arena = context.get("arena")

        if runtime is not None:
            runtime.emit_status_apply_fx(
                owner=owner,
                status=self,
                source=self.source,
                is_enemy=bool(getattr(owner, "is_enemy", False)),
                arena=arena,
            )        
    # -----------------------------------------------------------------
    def on_turn_end(self, owner, context):
        """
        Damage ticks at end of victim's turn.

        XVII.18 — dual-path base:
        - Legacy statuses: still directly mutate HP.
        - Migrated statuses (use_session_pipeline=True):
          emit DamageTickEvent only, Session will apply HP via ActionResult.
        """
        if self.per_tick <= 0:
            return []

        # ----------------------------------------
        # Figure out debug/runtime/arena context
        # ----------------------------------------
        runtime = None
        arena = None
        dbg = None

        if isinstance(context, dict):
            runtime = context.get("runtime")
            arena = context.get("arena")
            dbg = context.get("debug")
        elif context is not None:
            runtime = getattr(context, "runtime", None)
            arena = getattr(context, "arena", None)
            dbg = getattr(context, "debug", None)

        name = getattr(owner, "name", "<??>")
        status_id = getattr(self, "id", "<no-id>")
        status_name = getattr(self, "name", status_id)

        # ----------------------------------------
        # MIGRATED PATH: Session pipeline (no direct HP mutate)
        # ----------------------------------------
        if getattr(self, "use_session_pipeline", False):
            # Optional FX hook – we still want tick FX even though we don't
            # mutate HP here.
            if runtime is not None:
                runtime.emit_status_tick_fx(
                    owner=owner,
                    status=self,
                    amount=self.per_tick,
                    tick_kind=self.dot_element,  # "poison", "bleed", "fire"
                    is_enemy=bool(getattr(owner, "is_enemy", False)),
                    arena=arena,
                )

            # Log intent instead of HP delta
            if dbg is not None and hasattr(dbg, "runtime"):
                dbg.runtime(
                    f"[DOT HP] {name} will suffer {self.per_tick} {status_name} "
                    f"damage via Session"
                )

            # Emit event only; Session will do the HP change
            ev = DamageTickEvent(
                target=owner,
                amount=-int(self.per_tick),              # negative = damage
                kind=self.dot_element,                   # "fire" for Burn
                damage_type=self.dot_damage_type,        # "magic" for Burn
                source_status_id=status_id,
                source_combatant=getattr(self, "source", None),
            )
            return [ev]

        # ----------------------------------------
        # LEGACY PATH: direct HP mutation (Poison/Bleed/etc. still here)
        # ----------------------------------------
        # Snapshot HP *before* damage
        before_hp = getattr(owner, "hp", None)

        if hasattr(owner, "take_damage"):
            owner.take_damage(self.per_tick)
        elif hasattr(owner, "hp"):
            owner.hp = max(0, int(owner.hp) - int(self.per_tick))

        after_hp = getattr(owner, "hp", None)

        # FX hook (unchanged)
        if runtime is not None:
            runtime.emit_status_tick_fx(
                owner=owner,
                status=self,
                amount=self.per_tick,
                tick_kind=self.dot_element,
                is_enemy=bool(getattr(owner, "is_enemy", False)),
                arena=arena,
            )

        # Core DOT logs: HP delta + tick line
        if before_hp is not None and after_hp is not None:
            msg_hp = (
                f"[DOT HP] {name} {before_hp} -> {after_hp} "
                f"(-{self.per_tick}) from {status_name}"
            )
            if dbg is not None and hasattr(dbg, "runtime"):
                dbg.runtime(msg_hp)
            else:
                battle_log("status", msg_hp)

        msg_tick = (
            f"[DOT TICK] {name} suffers {self.per_tick} {status_name} damage. "
            f"(status_id={status_id}, turns_left={self.duration_turns})"
        )
        if dbg is not None and hasattr(dbg, "runtime"):
            dbg.runtime(msg_tick)
        else:
            battle_log("status", msg_tick)

        # Emit an event mirror for the legacy path too (unchanged)
        ev = DamageTickEvent(
            target=owner,
            amount=-int(self.per_tick),
            kind=self.dot_element,
            damage_type=self.dot_damage_type,
            source_status_id=status_id,
            source_combatant=getattr(self, "source", None),
        )
        return [ev]


    def get_status_fx_meta(status):
        """
        Return structured FX metadata about a status effect.

        Used by BattleRuntime when emitting status FX events so FXSystem can
        decide how to style DOT/HOT/buff/debuff visuals.
        """
        kind = "unknown"
        element = None

        # DOTs (Poison, Bleed, Burn, etc.)
        if isinstance(status, DotStatus):
            kind = "dot"
            # Prefer explicit dot_element; fall back to generic element if present.
            element = getattr(status, "dot_element", None) or getattr(
                status, "element", None
            )

        # Buffs
        if getattr(status, "is_buff", False):
            kind = "buff"

        # Debuffs
        if getattr(status, "is_debuff", False):
            kind = "debuff"

        return {
            "kind": kind,
            "element": element,
            "status_key": getattr(status, "key", None),
            "status_name": status.__class__.__name__,
        }


# =====================================================================
# POISON
# =====================================================================

class PoisonStatus(DotStatus):
    dot_element = "poison"
    dot_damage_type = "physical"
    dot_potency = 0.2
    base_power_scalar = 1.0
    max_stacks = 1
    stackable = False  # no stacking for poison
    use_session_pipeline = True   # 🐍 let Session handle Poison damage

    def __post_init__(self):
        super().__post_init__()
        self.icon_type = "dot"
        self.icon_id = "poison"

# =====================================================================
# BLEED
# =====================================================================

class BleedStatus(DotStatus):
    dot_element = "bleed"
    dot_damage_type = "physical"
    dot_potency = 0.4     # bleeds hurt more
    base_power_scalar = 1.0
    max_stacks = 3        # up to 3 bleeds
    stackable = True
    use_session_pipeline = True

    def __post_init__(self):
        super().__post_init__()
        self.icon_type = "dot"
        self.icon_id = "bleed"

# =====================================================================
# BURN
# =====================================================================

class BurnStatus(DotStatus):
    dot_element = "fire"
    dot_damage_type = "magic"
    dot_potency = 0.15    # fire is mild annoyance
    base_power_scalar = 0.8
    max_stacks = 3
    stackable = True
    use_session_pipeline = True   # 🔥 let Session handle Burn damage

    def __post_init__(self):
        super().__post_init__()
        self.icon_type = "dot"
        self.icon_id = "burn"
