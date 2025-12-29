from __future__ import annotations

from typing import Callable

from .base import SkillMeta, SkillDefinition
from .effects import DamageEffect

RegisterFn = Callable[[SkillDefinition], None]


def register_enemy_basic_skills(register: RegisterFn) -> None:
    """
    Register basic enemy skills.

    This includes:
      - Core Shade physical attacks
      - Region-based enemy packs (e.g. Merchant Trail)
    """

    # ------------------------------------------------------------------
    # 1) Core Shade enemy basics (existing behavior)
    # ------------------------------------------------------------------
    enemy_attacks = [
        # id,                   display_name,    user_name,       power
        ("shade_attack_1",       "Claw",          "Shade",         10),
        ("shade_brute_attack_1", "Heavy Swing",   "Shade Brute",   12),
        ("shade_adept_bonk_1",   "Wand Strike",   "Shade Adept",    8),
    ]

    for skill_id, display_name, user_name, base_damage in enemy_attacks:
        meta = SkillMeta(
            id=skill_id,
            name=display_name,
            user=user_name,             # MUST match EnemyTemplate.name
            category="damage",
            target_type="enemy_single",
            element="physical",
            mp_cost=0,
            tier=1,
            fx_tag=None,
            tags={"enemy", "basic"},
        )

        effects = [
            DamageEffect(
                base_damage=base_damage,
                element="physical",
                damage_type="physical",
            )
        ]

        register(SkillDefinition(meta=meta, effects=effects))

    # ------------------------------------------------------------------
    # 2) Region packs – e.g. Merchant Trail enemies
    # ------------------------------------------------------------------
    # Import inside the function to avoid circular imports.
    try:
        from engine.battle.skills.enemy_skill_packs.merchant_trail import (
            register_merchant_trail_enemy_skills,
        )

        register_merchant_trail_enemy_skills(register)
    except ImportError:
        # Safe fallback if the pack isn't present yet.
        # Optional: log something here later.
        pass
