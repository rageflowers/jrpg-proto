# engine/battle/command_handlers.py
from __future__ import annotations

from typing import Any, Optional


def resolve_defend(command: Any) -> Any | None:
    """
    Build a defend ActionResult.
    No CTB policy here; ActionMapper decides turn-flow.
    """
    actor_id = getattr(command, "actor_id", None)
    if not actor_id:
        return None

    from engine.battle.action_resolver import ActionResult, TargetResult

    res = ActionResult(
        actor_id=actor_id,
        command_type="defend",
        skill_id=None,
        item_id=None,
        element=None,
        targets=[
            TargetResult(
                target_id=actor_id,
                hp_delta=0,
                mp_delta=0,
                status_applied=["defend_1"],
                status_removed=[],
            )
        ],
    )
    res.success = True
    return res


def resolve_flee(command: Any, *, session: Any) -> Any | None:
    """
    Build an escape ActionResult with success flag.
    """
    actor_id = getattr(command, "actor_id", None)
    if not actor_id:
        return None

    import random
    from engine.battle.action_resolver import ActionResult

    can_escape = bool(getattr(getattr(session, "flags", None), "can_escape", True))
    success = can_escape and (random.random() < 0.50)

    res = ActionResult(
        actor_id=actor_id,
        command_type="escape",
        skill_id=None,
        item_id=None,
        element=None,
        targets=[],
    )
    res.success = success
    return res


def resolve_item(command: Any, *, session: Any, runtime: Any) -> Any | None:
    """
    Item usage is routed through item effect registry.
    """
    actor_id = getattr(command, "actor_id", None)
    item_id = getattr(command, "item_id", None)
    if not actor_id or not item_id:
        return None

    target_ids = list(getattr(command, "targets", []) or [])
    if not target_ids:
        return None

    # Local imports to avoid cycles
    from engine.items.defs import get_item
    from engine.items.effects.registry import get_effect, BattleItemContext

    item_def = get_item(item_id)
    if item_def is None:
        return None

    effect_id = getattr(item_def, "effect_id", None)
    if not effect_id:
        return None

    fn = get_effect(effect_id)
    if fn is None:
        return None

    ctx = BattleItemContext(
        session=session,
        runtime=runtime,
        actor_id=actor_id,
        item_id=item_id,
        target_ids=target_ids,
    )

    try:
        return fn(ctx)
    except Exception:
        return None


def resolve_equip_weapon(command: Any) -> Any | None:
    """
    Battle-local weapon swap. Does NOT mutate Session or Ledger.
    Returns an ActionResult with command_type='equip_weapon' and no targets.
    """
    actor_id = getattr(command, "actor_id", None)
    weapon_id = getattr(command, "item_id", None)
    if not actor_id or not weapon_id:
        return None

    from engine.items.defs import get_item
    item_def = get_item(weapon_id)
    if item_def is None or getattr(item_def, "kind", None) != "weapon":
        return None

    from engine.battle.action_resolver import ActionResult

    res = ActionResult(
        actor_id=actor_id,
        command_type="equip_weapon",
        skill_id=None,
        item_id=str(weapon_id),
        item_qty=1,
        element=None,
        targets=[],
    )
    res.success = True
    return res


def resolve_skill(
    command: Any,
    *,
    runtime: Any,
    controller: Any | None,
    arena: Any | None,
) -> Any | None:
    """
    Resolve a skill BattleCommand into an ActionResult (captured for POST_RESOLVE).
    Keeps legacy lookup via controller.get_skills_for(actor.name) for now.
    """
    session = getattr(runtime, "session", None)
    if session is None:
        return None

    # --- Resolve actor + targets from Session truth
    actor_id = getattr(command, "actor_id", None)
    if not actor_id:
        return None

    try:
        actor = session.get_combatant(actor_id)
    except Exception:
        return None

    target_ids = list(getattr(command, "targets", []) or [])
    if not target_ids:
        return None

    try:
        targets = [session.get_combatant(tid) for tid in target_ids]
    except Exception:
        return None

    # --- Resolve SkillDefinition by id
    skill_id = getattr(command, "skill_id", None)
    if not skill_id:
        return None

    skill_def: Optional[Any] = None
    defs: list[Any] = []

    if controller is not None and hasattr(controller, "get_skills_for"):
        try:
            defs = controller.get_skills_for(getattr(actor, "name", ""))
        except Exception:
            defs = []

    for d in defs:
        meta = getattr(d, "meta", None)
        if meta is not None and getattr(meta, "id", None) == skill_id:
            skill_def = d
            break

    if skill_def is None:
        return None

    meta = getattr(skill_def, "meta", None)

    # --- Affordance check (soft fail): MP
    mp_cost = getattr(meta, "mp_cost", 0) if meta is not None else 0
    if mp_cost and getattr(actor, "mp", 0) < mp_cost:
        # Use runtime's UI hook (safe no-op if absent)
        if hasattr(runtime, "_emit_player_message"):
            runtime._emit_player_message(
                arena=arena,
                actor=actor,
                meta=meta,
                msg=(
                    f"{getattr(actor, 'name', '???')} tries to use "
                    f"{getattr(meta, 'name', 'a skill')}, but lacks the aether."
                ),
            )
        return None

    # --- Mechanical resolution
    try:
        from engine.battle.skills.resolver import SkillResolver
        skill_result = SkillResolver.resolve(skill_def, actor, targets, controller)
    except Exception:
        return None

    if skill_result is None:
        return None

    # --- Convert to ActionResult (captured for POST_RESOLVE mutation)
    try:
        return runtime.capture_player_resolution(
            actor=actor,
            skill_def=skill_def,
            targets=targets,
            skill_result=skill_result,
        )
    except Exception:
        return None
