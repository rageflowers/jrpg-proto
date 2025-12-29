# engine/cinematics/player.py
from __future__ import annotations
from typing import Optional

from .base import Cinematic


class CinematicPlayer:
    """
    Lightweight runner for a single active cinematic.

    You call:
      - player.play(cinematic_instance)
      - player.update(dt) each frame
    And it clears itself when the cinematic finishes.
    """

    def __init__(self):
        self._active: Optional[Cinematic] = None

    def play(self, cinematic: Cinematic) -> None:
        """Start a new cinematic, replacing any currently active one."""
        self._active = cinematic
        cinematic.start()

    def update(self, dt: float) -> None:
        """Tick the active cinematic, if any, and clear it when done."""
        if not self._active:
            return

        self._active.update(dt)
        if self._active.is_finished():
            self._active = None

    def is_running(self) -> bool:
        return self._active is not None

    @property
    def active(self) -> Optional[Cinematic]:
        return self._active
