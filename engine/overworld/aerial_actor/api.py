# engine/overworld/aerial_actor/api.py
from __future__ import annotations

from typing import Protocol, runtime_checkable
import pygame


@runtime_checkable
class AerialActor(Protocol):
    kind: str

    def draw(
        self,
        surf: pygame.Surface,
        *,
        cam_angle: float,
        horizon_y: int,
        dt: float,
        sky_t: float = 0.0,
        view_left: float = 0.0,
        view_top: float = 0.0,
        world_w: float = 0.0,
        world_h: float = 0.0,
    ) -> None: ...

