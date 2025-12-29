# engine/cinematics/battle_examples.py
from __future__ import annotations
from typing import Any

from .base import BattleCinematic


class BossDefeatCinematic(BattleCinematic):
    """
    Example: quick zoom-out + fade when a major boss dies.

    Uses:
      - arena.camera_rig
      - arena.stage
      - maybe a small overlay fade you add later
    """

    def __init__(self, context: dict[str, Any]):
        super().__init__(context)
        self._timer = 0.0
        self._phase = 0

    def start(self) -> None:
        arena = self.arena
        if not arena:
            self.finish()
            return

        # Pull camera back a bit to show full battlefield
        arena.camera_rig.clear()
        arena.camera_rig.queue_tween(
            target_offset=(0, -10),
            target_zoom=0.9,
            duration=0.5,
        )
        self._phase = 0
        self._timer = 0.0

    def update(self, dt: float) -> None:
        arena = self.arena
        if not arena:
            self.finish()
            return

        self._timer += dt

        # Simple two-phase example:
        #  0–0.8s: zoom-out settles
        #  0.8–1.6s: hold + maybe darken
        if self._phase == 0:
            if self._timer >= 0.8:
                self._phase = 1
        elif self._phase == 1:
            if self._timer >= 1.6:
                # Snap camera back to normal and finish.
                arena.camera_rig.clear()
                self.finish()
