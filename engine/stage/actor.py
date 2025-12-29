from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Tuple, Any


class SpriteLike(Protocol):
    """Minimal protocol for anything that can live on a Stage.

    Your existing BattleSprite already fits this:
      - has x / y
      - has update(dt)
      - has draw(surface)
    """

    x: int
    y: int

    def update(self, dt: float) -> None:
        ...

    def draw(self, surface: Any) -> None:
        ...


@dataclass
class StageActor:
    """A logical actor on a Stage.

    Wraps a sprite-like object and gives us:
      - an ID to refer to in choreography
      - a layer index for draw ordering
      - a simple active flag
    """

    id: str
    sprite: SpriteLike
    layer: int = 0
    active: bool = True

    @property
    def pos(self) -> Tuple[int, int]:
        return (self.sprite.x, self.sprite.y)

    @pos.setter
    def pos(self, value: Tuple[int, int]) -> None:
        self.sprite.x, self.sprite.y = value

    def update(self, dt: float) -> None:
        if self.active:
            self.sprite.update(dt)

    def draw(self, surface: Any) -> None:
        if self.active:
            self.sprite.draw(surface)
