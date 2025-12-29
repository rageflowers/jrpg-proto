from __future__ import annotations

from typing import Callable

from engine.actors.enemy_sheet import EnemyTemplate, EnemyStats

RegisterEnemyTemplateFn = Callable[[EnemyTemplate], None]

def register(register_enemy_template) -> None:
    register_merchant_trail_enemies(register_enemy_template)

def register_merchant_trail_enemies(register: RegisterEnemyTemplateFn) -> None:
    """
    Register early-game enemies for the Merchant Trail region.
    """

    # 1) Trail Wolf
    register(
        EnemyTemplate(
            id="trail_wolf",
            name="Trail Wolf",
            element="none",
            stats=EnemyStats(
                max_hp=45,
                max_mp=0,
                atk=12,
                mag=2,
                defense=6,
                mres=4,
                spd=11,
                luck=4,
                xp_reward=10,
            ),
            tags={"beast", "trail"},
        )
    )

    # 2) Merchant Wasp
    register(
        EnemyTemplate(
            id="merchant_wasp",
            name="Merchant Wasp",
            element="none",
            stats=EnemyStats(
                max_hp=25,
                max_mp=0,
                atk=9,
                mag=3,
                defense=4,
                mres=3,
                spd=15,
                luck=5,
                xp_reward=8,
            ),
            tags={"beast", "insect", "trail"},
        )
    )

    # 3) Burrow Sprite
    register(
        EnemyTemplate(
            id="burrow_sprite",
            name="Burrow Sprite",
            element="none",
            stats=EnemyStats(
                max_hp=30,
                max_mp=10,
                atk=7,
                mag=8,
                defense=5,
                mres=6,
                spd=12,
                luck=6,
                xp_reward=12,
            ),
            tags={"spirit", "trail"},
        )
    )

    # 4) Briar Kobold
    register(
        EnemyTemplate(
            id="briar_kobold",
            name="Briar Kobold",
            element="none",
            stats=EnemyStats(
                max_hp=55,
                max_mp=5,
                atk=11,
                mag=4,
                defense=7,
                mres=5,
                spd=10,
                luck=6,
                xp_reward=16,
            ),
            tags={"humanoid", "trail"},
        )
    )

    # 5) Trail Shade (rare)
    register(
        EnemyTemplate(
            id="trail_shade",
            name="Trail Shade",
            element="shadow",
            stats=EnemyStats(
                max_hp=35,
                max_mp=20,
                atk=8,
                mag=10,
                defense=4,
                mres=8,
                spd=13,
                luck=7,
                xp_reward=20,
            ),
            tags={"shade", "trail", "rare"},
        )
    )
