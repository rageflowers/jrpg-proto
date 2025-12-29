# engine/battle/outcome_builder.py
from __future__ import annotations

from engine.meta.battle_outcome import BattleOutcome


def build_battle_outcome(*, runtime, controller) -> BattleOutcome:
    """
    Build the META-facing BattleOutcome only.
    No battle-facing outcome class exists anymore.
    """

    session = getattr(runtime, "session", None)

    # Prefer controller.state for terminal truth, fall back to session if needed.
    state = getattr(controller, "state", None)
    victory = bool(state == "victory")
    defeat = bool(state == "defeat")

    if session is not None and not (victory or defeat):
        try:
            s = session.check_battle_outcome()
            victory = (s == "victory")
            defeat = (s == "defeat")
        except Exception:
            pass

    xp_log = list(getattr(session, "xp_log", []) or []) if session is not None else []
    loot_log = list(getattr(session, "loot_log", []) or []) if session is not None else []

    return BattleOutcome(
        victory=victory,
        defeat=defeat,
        xp_log=xp_log,
        loot_log=loot_log,
        set_flags=set(),
        clear_flags=set(),
    )
