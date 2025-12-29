from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Sequence

from engine.battle.skills import registry
from engine.battle.action_mapper import MappedAction  # or move this dataclass too later


@dataclass
class EnemyAIContext:
    enemy: Any
    controller: Any
    runtime: Any


def choose_basic_enemy_action(ctx: EnemyAIContext) -> MappedAction | None:
    """
    Current 'lowest HP with any damage skill' behavior, extracted from ActionMapper.

    This function is intended to be behavior-identical to your existing logic:
    - Pick the first damage skill from registry.get_for_user(enemy.name)
    - Target the lowest-HP living party member
    """
    enemy = ctx.enemy
    controller = ctx.controller
    runtime = ctx.runtime

    # 1) Look up skills for this enemy
    lookup_name = getattr(enemy, "skill_user_key", enemy.name)
    skills = controller.get_skills_for(lookup_name)
    damage_skills = [s for s in skills if s.meta.category == "damage"]
    if not damage_skills:
        return None

    skill_def = damage_skills[0]

    # 2) Pick a target: lowest HP living party member
    living_party = [p for p in controller.party if p.is_alive()]
    if not living_party:
        return None

    target = min(living_party, key=lambda p: p.hp)

    return MappedAction(
        user=enemy,
        skill_id=skill_def.meta.id,
        targets=[target],
        reason="basic_enemy_ai_lowest_hp",
    )
