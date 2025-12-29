from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple


@dataclass
class Camera:
    """Very simple camera for 2D stages.

    For now:
      - holds an (x, y) offset
      - later we can add shake, zoom, easing, targets, etc.
    """

    offset: Tuple[int, int] = (0, 0)

    def move_to(self, x: int, y: int) -> None:
        self.offset = (x, y)

    def translate(self, dx: int, dy: int) -> None:
        ox, oy = self.offset
        self.offset = (ox + dx, oy + dy)
