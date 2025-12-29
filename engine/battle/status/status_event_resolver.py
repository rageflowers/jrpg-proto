from __future__ import annotations

from typing import Sequence

from engine.battle.action_resolver import ActionResult, build_action_result_from_status_events
from engine.battle.status.status_events import StatusEvent
from engine.battle.session import BattleSession

def resolve_status_events(
    *,
    events: Sequence[StatusEvent],
    session: "BattleSession",
    source: str = "status",
) -> ActionResult:
    """Translate StatusEvent objects into exactly one ActionResult.

    Macro-law (Forge XVII.22):
      - StatusManager emits events only.
      - This helper converts *all* events into one mutation package.
      - BattleSession.apply_action_result remains the only mutation gate.

    Notes:
      - This is a thin wrapper around the existing resolver logic to avoid
        duplicating/fragmenting event math.
      - Do not filter events here. Preserve intent and ordering.
    """
    # Local import for type-check friendliness without introducing cycles
    from engine.battle.session import BattleSession  # noqa: F401

    return build_action_result_from_status_events(
        events=events,
        session=session,
        source=source,
    )
