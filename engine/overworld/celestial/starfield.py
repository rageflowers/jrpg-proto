from __future__ import annotations
import random
import pygame
from typing import Dict, Tuple


# -------------------------------------------------
# Starfield cache
# -------------------------------------------------

_StarKey = Tuple[int, int, int]  # (width, height, alpha)
_star_cache: Dict[_StarKey, pygame.Surface] = {}


def get_starfield(
    *,
    width: int,
    height: int,
    alpha: int,
    seed: int = 1337,
) -> pygame.Surface:
    """
    Return a cached starfield surface of the given size and alpha.
    Generated once per (width, height, alpha).
    """

    key = (width, height, int(alpha))
    surf = _star_cache.get(key)
    if surf is not None:
        return surf

    stars = pygame.Surface((width, height), pygame.SRCALPHA)

    # Density scales gently with area
    count = max(60, int((width * height) / 5000))

    rng = random.Random(seed)

    for _ in range(count):
        x = rng.randrange(0, width)
        y = rng.randrange(0, height)

        # Bias away from horizon (fewer stars near bottom)
        if rng.random() < (y / max(1, height)) * 0.6:
            continue

        roll = rng.random()
        if roll < 0.70:
            a = int(alpha * 0.65)
            r = 1
        elif roll < 0.92:
            a = int(alpha * 0.90)
            r = 1
        else:
            a = int(alpha * 1.10)
            r = 2

        a = max(0, min(255, a))
        col = (255, 255, 255, a)

        stars.fill(col, rect=pygame.Rect(x, y, r, r))

    _star_cache[key] = stars
    return stars
