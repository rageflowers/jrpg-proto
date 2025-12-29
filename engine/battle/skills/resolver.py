# engine/battle/skills/resolver.py
#
# Central logic for resolving a skill use in battle.
#
# This module is intentionally independent of Pygame and the visual layer.
# It:
#   - Takes a SkillDefinition + user + chosen targets + battle_state
#   - Executes each SkillEffect in order
#   - Produces a SkillResolutionResult that the BattleController and
#     BattleArena / FX router can consume.

from __future__ import annotations

from typing import Any, Sequence

from .base import SkillDefinition, SkillResolutionResult


class SkillResolver:
    """
    Resolves a skill into concrete changes to battle state.

    Typical usage from BattleController:
        result = SkillResolver.resolve(skill_def, actor, targets, self)

    Where:
        - skill_def: SkillDefinition (meta + effects)
        - actor: the combatant using the skill
        - targets: sequence of target combatants (already chosen by UI/controller)
        - battle_state: usually the BattleController instance or a thin facade
    """

    @staticmethod
    def resolve(
        skill_def: SkillDefinition,
        user: Any,
        targets: Sequence[Any],
        battle_state: Any,
    ) -> SkillResolutionResult:
        """
        Apply the mechanical effects of the given skill to the battle state.

        This does NOT:
          - choose targets (that is done by the controller/UI)
          - play any visuals (Arena/FX router handle that)
          - manage turn order (CTB logic stays in BattleController)

        It ONLY:
          - runs each SkillEffect
          - records what happened in a SkillResolutionResult
        """
        # Ensure we treat targets like a list (needed for repeated passes).
        targets = list(targets)

        result = SkillResolutionResult(
            skill=skill_def.meta,
            user=user,
        )

        # Run each component effect in order.
        for effect in skill_def.effects:
            # If an effect wants to apply to the user (self-buff, self-heal, etc.),
            # we override the targets list for this effect only.
            if getattr(effect, "apply_to_user", False):
                actual_targets = [user]
            else:
                actual_targets = targets

            effect.apply(user, actual_targets, battle_state, result)
            
        # If no message has been set by any effect, generate a simple default.
        if result.message is None:
            user_name = getattr(user, "name", "???")
            result.message = f"{user_name} used {skill_def.meta.name}!"

        return result
