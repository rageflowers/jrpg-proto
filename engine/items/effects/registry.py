# engine/items/effects/registry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Any


@dataclass(frozen=True)
class BattleItemContext:
    """
    Battle-only context for resolving an item into an ActionResult.

    NOTE: No LedgerState here yet. We'll hook consumption later.
    """
    session: Any
    runtime: Any
    actor_id: str
    item_id: str
    target_ids: list[str]


EffectFn = Callable[[BattleItemContext], Any]  # returns ActionResult | None


_EFFECTS: dict[str, EffectFn] = {}


def register_effect(effect_id: str, fn: EffectFn) -> None:
    if not effect_id or not isinstance(effect_id, str):
        raise ValueError("effect_id must be a non-empty string")
    if effect_id in _EFFECTS:
        return  # idempotent
    _EFFECTS[effect_id] = fn


def get_effect(effect_id: str) -> Optional[EffectFn]:
    return _EFFECTS.get(effect_id)


def initialize_default_effects() -> None:
    # ----------------------------
    # heal_hp_30
    # ----------------------------
    def _heal_hp_30(ctx: BattleItemContext):
        from engine.battle.action_resolver import ActionResult, TargetResult

        heal_amt = 30

        res = ActionResult(
            actor_id=ctx.actor_id,
            command_type="item",
            skill_id=None,
            item_id=ctx.item_id,
            item_qty=1,
            element=None,
            targets=[
                TargetResult(
                    target_id=tid,
                    hp_delta=+heal_amt,
                    mp_delta=0,
                    status_applied=[],
                    status_removed=[],
                )
                for tid in ctx.target_ids
            ],
        )
        res.success = True

        # Optional FX: use runtime helper if available
        try:
            arena = getattr(ctx.runtime, "arena", None)
            actor = ctx.session.get_combatant(ctx.actor_id)
            for tid in ctx.target_ids:
                tgt = ctx.session.get_combatant(tid)
                if hasattr(ctx.runtime, "emit_basic_heal_fx"):
                    ctx.runtime.emit_basic_heal_fx(
                        source=actor,
                        target=tgt,
                        amount=heal_amt,
                        is_enemy=False,
                        arena=arena,
                    )
        except Exception:
            pass

        return res

    register_effect("heal_hp_30", _heal_hp_30)
