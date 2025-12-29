# engine/cinematics/base.py
from __future__ import annotations
from typing import Any, Dict


class Cinematic:
    """
    Base class for all engine-level cinematics.

    A cinematic:
      - gets a context dict (battle, map, story, etc.)
      - runs over time via update(dt)
      - signals completion via is_finished()
    """

    def __init__(self, context: Dict[str, Any]):
        self.context = context
        self._finished = False

    def start(self) -> None:
        """Called once when the cinematic begins. Override in subclasses."""
        raise NotImplementedError

    def update(self, dt: float) -> None:
        """Advance the cinematic. Override in subclasses."""
        raise NotImplementedError

    def is_finished(self) -> bool:
        return self._finished

    def finish(self) -> None:
        """Mark the cinematic as finished."""
        self._finished = True


class BattleCinematic(Cinematic):
    """
    Convenience base for cinematics that specifically run in battles.

    Expects context to contain:
      - 'arena': the BattleArena instance
      - (optionally) 'actor', 'target', 'event', 'boss', etc.
    """

    @property
    def arena(self):
        return self.context.get("arena")

    @property
    def actor(self):
        return self.context.get("actor")

    @property
    def target(self):
        return self.context.get("target")

    @property
    def event(self):
        return self.context.get("event")

    @property
    def boss(self):
        return self.context.get("boss")
