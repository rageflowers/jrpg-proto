from __future__ import annotations
from typing import Optional

from engine.stage.choreo import MoveTo, Wait, Sequence, Action, Timeline
from engine.stage.stage import Stage
from engine.stage.actor import StageActor


def _get_actor(stage: Stage, actor_id: str) -> Optional[StageActor]:
    for a in stage.actors:
        if a.id == actor_id:
            return a
    return None


def build_melee_dash_sequence(
    stage: Stage,
    actor_id: str,
    enemy_id: str,
    dash_duration: float = 0.20,
    back_duration: float = 0.20,
    linger: float = 0.08,
) -> Optional[Action]:
    """Create a simple dash-in, pause, dash-back sequence."""

    actor = _get_actor(stage, actor_id)
    enemy = _get_actor(stage, enemy_id)
    if actor is None or enemy is None:
        return None

    start_x, start_y = actor.pos
    enemy_x, enemy_y = enemy.pos

    # Impact position: between actor and enemy, bias towards enemy
    impact_x = int(start_x + (enemy_x - start_x) * 0.6)
    impact_y = start_y  # stay on ground plane

    dash_out = MoveTo(actor=actor, target_pos=(impact_x, impact_y),
                      duration=dash_duration)
    wait = Wait(linger)
    dash_back = MoveTo(actor=actor, target_pos=(start_x, start_y),
                       duration=back_duration)

    return Sequence([dash_out, wait, dash_back])


def queue_melee_dash(
    timeline: Timeline,
    stage: Stage,
    actor_id: str,
    enemy_index: int,
) -> None:
    """Convenience helper BattleArena can call."""
    enemy_id = f"Enemy_{enemy_index}"
    seq = build_melee_dash_sequence(stage, actor_id, enemy_id)
    if seq is not None:
        timeline.add(seq)
