from __future__ import annotations
from typing import Callable


# Basic easing functions for future choreography. For now just a couple.

def ease_linear(t: float) -> float:
    return t


def ease_out_quad(t: float) -> float:
    return 1 - (1 - t) * (1 - t)


def ease_in_out_quad(t: float) -> float:
    if t < 0.5:
        return 2 * t * t
    return 1 - (-2 * t + 2) ** 2 / 2


EaseFunc = Callable[[float], float]
