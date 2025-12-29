# engine/battle/skills/shared.py
#
# Shared skills that every combatant can access.
#
# Forge XVI.4: This module anchors the ITEM menu.
#   - All skills here use user="shared"
#   - They are grouped under menu_group="item"
#
# Elemental spells now live in elemental.py and are scoped per character.

from __future__ import annotations

from typing import Callable, List

from .base import SkillMeta, SkillDefinition, CategoryType, TargetType
from .effects import HealEffect, MPDeltaEffect

RegisterFn = Callable[[SkillDefinition], None]


def _build_item_skill(
    *,
    skill_id: str,
    name: str,
    description: str,
    category: CategoryType,
    target_type: TargetType,
    effects: List,
    consumes_item_id: str | None = None,
    fx_tag: str = "item_use",
) -> SkillDefinition:
    """
    Helper so all item skills share a consistent meta structure.
    """
    meta = SkillMeta(
        id=skill_id,
        name=name,
        user="shared",              # everyone (Setia/Nyra/Kaira/guests) can use items
        category=category,
        element="none",
        tier=1,
        mp_cost=0,                  # real item consumption handled by inventory later
        target_type=target_type,
        description=description,
        tags=({"item"} | ({f"consumes:{consumes_item_id}"} if consumes_item_id else set())),
        fx_tag=fx_tag,
        menu_group="item",          # drives the popup Items tab
    )
    return SkillDefinition(meta=meta, effects=effects)


def register_shared_skills(register_fn: RegisterFn) -> None:
    """
    Register shared skills that should appear for all combatants.

    In XVI.4 this is focused on basic Items. Later we can expand with:
      - More item tiers (Hi-Potion, Mega Potion, etc.)
      - Status cures (Antidote, Remedy) using RemoveStatus* effects
      - Revive items using ReviveEffect
      - Inventory-aware checks before use
    """
    skills: List[SkillDefinition] = []

    # --------------------------------------------------
    # Potion – basic HP restore item
    # --------------------------------------------------
    potion = _build_item_skill(
        skill_id="item_potion",
        name="Potion",
        description="Restore a small amount of HP to one ally.",
        category="heal",
        target_type="ally_single",
        effects=[HealEffect(base_heal=30)],
        consumes_item_id="potion_small",
        fx_tag="item_heal_small",
    )
    skills.append(potion)

    # --------------------------------------------------
    # Ether – basic MP restore item
    # --------------------------------------------------
    ether = _build_item_skill(
        skill_id="item_ether",
        name="Ether",
        description="Restore a small amount of MP to one ally.",
        category="heal",  # still a ‘heal’ category mechanically
        target_type="ally_single",
        effects=[MPDeltaEffect(mp_delta=10)],
        consumes_item_id="ether_small",
        fx_tag="item_mp_small",
    )
    skills.append(ether)

    # --------------------------------------------------
    # Register everything with the central registry
    # --------------------------------------------------
    for s in skills:
        register_fn(s)
