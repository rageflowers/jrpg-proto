from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Any, Iterable, Tuple

import pygame

from .actor import StageActor


@dataclass
class Stage:
    """A 2D stage to render actors and effects on.

    For now this is deliberately simple:
      - knows its size
      - optional background Surface
      - holds a list of StageActor objects
      - supports a basic camera offset

    Later phases will add:
      - layered rendering
      - atmosphere overlays
      - VFX
      - choreography hooks
    """

    width: int
    height: int
    background: Optional[pygame.Surface] = None
    actors: List[StageActor] = field(default_factory=list)

    # simple camera offset (pixel space)
    camera_offset: Tuple[int, int] = (0, 0)

    def add_actor(self, actor: StageActor) -> None:
        self.actors.append(actor)
        # Keep things roughly in layer order
        self.actors.sort(key=lambda a: a.layer)

    def remove_actor(self, actor_id: str) -> None:
        self.actors = [a for a in self.actors if a.id != actor_id]

    def find_actor(self, actor_id: str) -> Optional[StageActor]:
        for a in self.actors:
            if a.id == actor_id:
                return a
        return None

    def update(self, dt: float) -> None:
        for actor in self.actors:
            actor.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        # Camera offset is applied to everything drawn on this Stage
        ox, oy = self.camera_offset

        # Background (if any)
        if self.background:
            bg_rect = self.background.get_rect()
            bg_rect.center = surface.get_rect().center
            surface.blit(self.background, (bg_rect.x + ox, bg_rect.y + oy))
        else:
            surface.fill((0, 0, 0))

        # Actors
        for actor in self.actors:
            # For now we just temporarily offset the sprite, draw, restore
            sprite = actor.sprite
            px, py = sprite.x, sprite.y
            sprite.x = px + ox
            sprite.y = py + oy
            actor.draw(surface)
            sprite.x, sprite.y = px, py
