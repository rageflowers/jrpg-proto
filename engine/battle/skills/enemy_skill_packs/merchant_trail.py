# engine/battle/skills/enemy_skill_packs/merchant_trail.py

from __future__ import annotations

from typing import Callable

from engine.battle.skills.base import SkillMeta, SkillDefinition
from engine.battle.skills.effects import DamageEffect

RegisterSkillFn = Callable[[SkillDefinition], None]


def register_merchant_trail_enemy_skills(register: RegisterSkillFn) -> None:
    """
    Register basic enemy skills for Merchant Trail foes.
    """

    # Trail Wolf – Claw Swipe
    register(
        SkillDefinition(
            meta=SkillMeta(
                id="trail_wolf_claw_1",
                name="Claw Swipe",
                user="Trail Wolf",
                category="damage",
                element="physical",
                tier=1,
                mp_cost=0,
                target_type="enemy_single",
                description="A vicious claw swipe.",
                tags={"enemy", "basic", "physical", "trail"},
                fx_tag=None,
            ),
            effects=[
                DamageEffect(
                    base_damage=8,
                    damage_type="physical",
                    element="physical",
                )
            ],
        )
    )

    # Merchant Wasp – Sting
    register(
        SkillDefinition(
            meta=SkillMeta(
                id="merchant_wasp_sting_1",
                name="Sting",
                user="Merchant Wasp",
                category="damage",
                element="physical",
                tier=1,
                mp_cost=0,
                target_type="enemy_single",
                description="A sharp sting from an oversized wasp.",
                tags={"enemy", "basic", "trail"},
                fx_tag=None,
            ),
            effects=[
                DamageEffect(
                    base_damage=6,
                    damage_type="physical",
                    element="physical",
                )
            ],
        )
    )

    # Burrow Sprite – Dust Kick
    register(
        SkillDefinition(
            meta=SkillMeta(
                id="burrow_sprite_dust_kick_1",
                name="Dust Kick",
                user="Burrow Sprite",
                category="damage",
                element="physical",
                tier=1,
                mp_cost=0,
                target_type="enemy_single",
                description="Kicks up dust into the enemy's face.",
                tags={"enemy", "trail"},
                fx_tag=None,
            ),
            effects=[
                DamageEffect(
                    base_damage=5,
                    damage_type="physical",
                    element="physical",
                )
            ],
        )
    )

    # Briar Kobold – Rusty Shiv
    register(
        SkillDefinition(
            meta=SkillMeta(
                id="briar_kobold_shiv_1",
                name="Rusty Shiv",
                user="Briar Kobold",
                category="damage",
                element="physical",
                tier=1,
                mp_cost=0,
                target_type="enemy_single",
                description="A quick stab with a corroded blade.",
                tags={"enemy", "basic", "trail"},
                fx_tag=None,
            ),
            effects=[
                DamageEffect(
                    base_damage=9,
                    damage_type="physical",
                    element="physical",
                )
            ],
        )
    )

    # Trail Shade – Shadow Nip
    register(
        SkillDefinition(
            meta=SkillMeta(
                id="trail_shade_nip_1",
                name="Shadow Nip",
                user="Trail Shade",
                category="damage",
                element="shadow",
                tier=1,
                mp_cost=0,
                target_type="enemy_single",
                description="A small bite from the darkness.",
                tags={"enemy", "shade", "trail"},
                fx_tag=None,
            ),
            effects=[
                DamageEffect(
                    base_damage=7,
                    damage_type="physical",
                    element="shadow",
                )
            ],
        )
    )
