# engine/battle/skills/elemental.py

from __future__ import annotations

from typing import Callable, Iterable

from .base import SkillMeta, SkillDefinition
from .effects import DamageEffect, ApplyStatusEffect, ChanceStatusEffect
from .statuses import (
    make_iceshield_t1,
    make_frostbite_basic,
)
from engine.battle.status.effects import BurnStatus
# Anything that accepts a SkillDefinition (e.g. registry.register)
RegisterFn = Callable[[SkillDefinition], None]

# Only our core trio should ever see Elemental skills
ELEMENTAL_USERS: Iterable[str] = ("Setia", "Nyra", "Kaira")
# ---------------------------------------------------------------------------
# Burn DoT tiers (elemental fire status source-of-truth)
# ---------------------------------------------------------------------------

# In XVII.9d we start with a single tier (Burn I), but this structure is
# ready for Burn II / III, etc.
BURN_TIERS = {
    "burn_1": {
        "id": "burn_1",
        "name": "Burn I",
        "duration": 3,
        # This scalar plugs into DotStatus.compute_base_total →
        # engine.battle.damage.compute_damage(base_damage=...)
        "power_scalar": 0.8,
        "stackable": True,
    },
    # Future:
    # "burn_2": {...},
    # "burn_3": {...},
}

def make_burn_t1(user, target, battle_state):
    """
    Canonical Burn I factory for elemental fire skills.

    Returns a DotStatus-based BurnStatus instance using the global DOT
    engine, but with all tuning (duration, power, stack behavior) defined
    here in elemental.py.
    """
    cfg = BURN_TIERS["burn_1"]

    status = BurnStatus(
        id=cfg["id"],
        name=cfg["name"],
        duration_turns=cfg["duration"],
        dispellable=True,
        stackable=cfg["stackable"],
    )

    # Tier-specific tuning: adjust the power scalar per tier if desired.
    status.base_power_scalar = cfg["power_scalar"]

    # Ensure tags are consistent with the DOT pipeline and FX system
    if not hasattr(status, "tags") or status.tags is None:
        status.tags = set()

    status.tags.update({"burn", "dot", "fire", "debuff"})
    status.icon_type = "debuff"   # or "dot"
    status.icon_id = "burn"
    return status


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _register_shield_for_core_users(
    register: RegisterFn,
    base_id: str,
    display_name: str,
    element: str,
    mp_cost: int,
    description: str,
    fx_tag: str,
    status_factory,
) -> None:
    """
    Register a single-target elemental shield for Setia, Nyra, and Kaira.
    """
    for user in ELEMENTAL_USERS:
        meta = SkillMeta(
            id=f"{user.lower()}_{base_id}",
            name=display_name,
            user=user,
            category="buff",
            element=element,
            tier=1,
            mp_cost=mp_cost,
            target_type="ally_single",
            description=description,
            tags={"elemental", "shield", element, user.lower()},
            fx_tag=fx_tag,
            menu_group="elemental",
        )

        skill_def = SkillDefinition(
            meta=meta,
            effects=[
                ApplyStatusEffect(status_factory=status_factory),
            ],
        )

        register(skill_def)


def _register_elemental_spell_for_core_users(
    register: RegisterFn,
    *,
    base_id: str,
    display_name: str,
    element: str,
    mp_cost: int,
    description: str,
    fx_tag: str,
    mag_ratio: float,
    status_factory,
    status_chance: float,
) -> None:
    """
    Register a single-target elemental attack spell (Ember, Frost, etc.)
    for Setia, Nyra, and Kaira.

    Damage is MAG-scaled via mag_ratio, with an optional on-hit status proc.
    """
    for user in ELEMENTAL_USERS:
        meta = SkillMeta(
            id=f"{user.lower()}_{base_id}",
            name=display_name,
            user=user,
            category="damage",
            element=element,
            tier=1,
            mp_cost=mp_cost,
            target_type="enemy_single",
            description=description,
            tags={"elemental", "spell", element, user.lower()},
            fx_tag=fx_tag,
            menu_group="elemental",
        )

        effects = [
            # MAG-based elemental damage
            DamageEffect(
                base_damage=0,
                element=element,
                mag_ratio=mag_ratio,
            ),
        ]

        # Optional Burn / Frostbite proc
        if status_factory is not None and status_chance > 0.0:
            effects.append(
                ChanceStatusEffect(
                    status_factory=status_factory,
                    chance=status_chance,
                )
            )

        skill_def = SkillDefinition(meta=meta, effects=effects)
        register(skill_def)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def register_elemental_skills(register: RegisterFn) -> None:
    """
    Register all elemental skills (shields, Ember, Frost) for the core trio.

    This will create per-user variants like:
        setia_fire_shield_1
        nyra_fire_shield_1
        kaira_fire_shield_1

        setia_ember_bolt_1
        nyra_ember_bolt_1
        kaira_ember_bolt_1

        setia_frost_shot_1
        nyra_frost_shot_1
        kaira_frost_shot_1
    """


    # ------------------------------------------------------------------
    # Ice Shield (Tier 1)
    # ------------------------------------------------------------------
    _register_shield_for_core_users(
        register=register,
        base_id="ice_shield_1",
        display_name="Chill Ward",
        element="ice",
        mp_cost=10,
        description=(
            "A basic ice shield that reduces incoming damage and can "
            "retaliate with numbing frost."
        ),
        fx_tag="fx_ice_shield_1",
        status_factory=make_iceshield_t1,
    )

    # ------------------------------------------------------------------
    # Ember Bolt (Burn I proc)
    # ------------------------------------------------------------------
    _register_elemental_spell_for_core_users(
        register=register,
        base_id="ember_bolt_1",
        display_name="Ember Bolt",
        element="fire",
        mp_cost=6,
        description=(
            "A dart of living flame that scorches a single foe. "
            "May inflict Burn I."
        ),
        fx_tag="fx_ember_bolt_1",
        mag_ratio=0.85,          # MAG × 0.85
        status_factory=make_burn_t1,
        status_chance=0.25,      # 25% Burn I
    )

    # ------------------------------------------------------------------
    # Frost Shot (Frostbite I proc)
    # ------------------------------------------------------------------
    _register_elemental_spell_for_core_users(
        register=register,
        base_id="frost_shot_1",
        display_name="Frost Shot",
        element="ice",
        mp_cost=6,
        description=(
            "A razor shard of ice that chills a single foe. "
            "May inflict Frostbite I."
        ),
        fx_tag="fx_frost_shot_1",
        mag_ratio=0.85,          # MAG × 0.85
        status_factory=make_frostbite_basic,
        status_chance=0.25,      # 25% Frostbite I
    )
