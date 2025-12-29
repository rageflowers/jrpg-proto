# engine/battle/skills/base.py
#
# Core skill data structures for the Forge battle system.
#
# This layer is intentionally logic-only:
#   - NO pygame
#   - NO Arena / Stage / Camera references
#
# BattleController + SkillResolver will use these types, and the
# visual layer (Arena / FX router) will look at fx_tag + result data
# to decide how to animate things.

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Callable
from engine.battle.status.status_events import StatusEvent

SkillEffectFunc = Callable[[Any, Any, Any], None]  # (user, target, battle_state)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

ElementType = str   # "fire", "ice", "holy", "shadow", "wind", "none"
TargetType = str    # "self", "ally_single", "ally_all", "enemy_single", "enemy_all"
CategoryType = str  # "damage", "heal", "buff", "debuff", "shield", "revive", "hybrid"


# ---------------------------------------------------------------------------
# Skill metadata + definition
# ---------------------------------------------------------------------------

@dataclass
class SkillMeta:
    """
    Describes *what* a skill is, but not *how* it works internally.

    This is the canonical place to store:
      - name, id
      - which character uses it
      - its category (heal, damage, buff, etc.)
      - its element (fire/ice/holy/shadow/wind/none)
      - MP cost
      - targeting rules
      - tier/evolution information
      - any tags used by UI or FX (e.g. "nyra_heal", "setia_wind", etc.)
      - fx_tag: a simple string so the FX router can choose choreography
    """

    id: str                        # unique key, e.g. "nyra_heal_1"
    name: str
    user: str                      # "Setia", "Nyra", "Kaira", "shared", etc.
    category: CategoryType
    element: ElementType = "none"
    tier: int = 1                  # evolution stage (1..4)
    mp_cost: int = 0
    target_type: TargetType = "enemy_single"
    description: str = ""
    tags: set[str] = field(default_factory=set)
    fx_tag: Optional[str] = None   # used by FX router / Arena
    menu_group: str = "arts"  # "attack", "arts", "fire", "ice", "item"

    # Later we can add things like:
    #   ui_icon: Optional[str]
    #   unlock_level: int
    #   story_gate_id: Optional[str]
    # without touching the rules engine.


class SkillEffect:
    """
    Base class for all mechanical skill effects.

    Concrete subclasses will handle things like:
      - DamageEffect
      - HealEffect
      - BuffEffect
      - ShieldEffect
      - ApplyStatusEffect
      - MPChangeEffect
      - ReviveEffect
      - etc.

    The SkillResolver will call .apply(...) on each effect in sequence.
    """
    apply_to_user: bool = False
    def apply(
        self,
        user: Any,
        targets: Sequence[Any],
        battle_state: Any,
        result: "SkillResolutionResult",
    ) -> None:
        """
        Mutate battle_state / targets / result according to this effect.

        `battle_state` will typically be the BattleController or a thin
        facade around it that exposes methods like:
          - deal_damage(user, target, amount, element, flags)
          - heal(target, amount)
          - apply_status(target, status_instance)
          - etc.

        `result` is a structured log of what happened, for UI + FX.
        """
        raise NotImplementedError("SkillEffect.apply() must be implemented")


@dataclass
class SkillDefinition:
    """
    A complete skill: metadata + one or more SkillEffect components.

    This is what the SkillResolver will consume during battle.
    """

    meta: SkillMeta
    effects: List[SkillEffect] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Resolution result (what the resolver returns to the controller/arena)
# ---------------------------------------------------------------------------

@dataclass
class TargetChange:
    """
    Records what happened to a single target during a skill resolution.

    The FX layer and battle log can use this to show:
      - numbers flying up
      - status icons appearing
      - KO animations
    """

    target: Any
    damage: int = 0
    healed: int = 0
    mp_delta: int = 0              # negative = MP spent/drained, positive = restored
    status_applied: List[str] = field(default_factory=list)
    status_removed: List[str] = field(default_factory=list)
    was_revived: bool = False
    hit_weakness: bool = False
    was_resisted: bool = False
    # Optional per-component breakdown (Forge XVII.16):
    # each entry is a small dict, e.g.:
    #   {"kind": "physical", "element": "none",
    #    "base_power": 16, "raw": 22, "final": 22}
    components: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SkillResolutionResult:
    """
    High-level outcome of resolving a single skill use.

    This object is:
      - returned by SkillResolver.resolve(...)
      - consumed by BattleController to update logs
      - consumed by BattleArena / FX router to trigger choreography
    """

    skill: SkillMeta
    user: Any
    targets: List[TargetChange] = field(default_factory=list)

    status_events: List[StatusEvent] = field(default_factory=list)

    # Optional message to display in the battle log (can be auto-generated or custom).
    message: Optional[str] = None
    # Optional additional flags / metadata (e.g. "multi_hit", "critical", etc.)
    flags: Dict[str, Any] = field(default_factory=dict)

    @property
    def fx_tag(self) -> Optional[str]:
        """Convenience access to the skill's fx_tag."""
        return self.skill.fx_tag
