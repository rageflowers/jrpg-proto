# engine/cinematics/triggers.py
from __future__ import annotations
from typing import Dict, Tuple, Type, Any

from .base import Cinematic
from .player import CinematicPlayer


# (domain, key) -> Cinematic subclass
_CINEMATIC_REGISTRY: Dict[Tuple[str, str], Type[Cinematic]] = {}


def register_cinematic(domain: str, key: str, cls: Type[Cinematic]) -> None:
    """
    Register a cinematic class under (domain, key).

    Examples:
      register_cinematic("battle", "boss_defeated", BossDefeatCinematic)
      register_cinematic("map", "enter_region:ObeliskSanctum", ObeliskIntroCinematic)
    """
    _CINEMATIC_REGISTRY[(domain, key)] = cls


def trigger_cinematic(
    player: CinematicPlayer,
    domain: str,
    key: str,
    context: Dict[str, Any],
) -> bool:
    """
    Look up a cinematic for (domain, key) and, if found, play it
    on the given CinematicPlayer with the provided context.

    Returns True if a cinematic was found and started, False otherwise.
    """
    cls = _CINEMATIC_REGISTRY.get((domain, key))
    if cls is None:
        return False

    cinematic = cls(context)
    player.play(cinematic)
    return True
