# engine/state/save_state.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any

from engine.actors.character_sheet import (
    CharacterInstance,
    new_default_party,
)


@dataclass
class SaveGame:
    """
    High-level representation of a save slot.

    For now this only stores:
      - the party (Setia/Nyra/Kaira)
      - a handful of story flags
      - a simple 'world_state' blob for coords, region, etc.

    Later we can extend with:
      - inventory
      - gold
      - unlocked skills
      - per-area completion flags
    """

    party: Dict[str, CharacterInstance] = field(default_factory=dict)
    story_flags: Dict[str, bool] = field(default_factory=dict)
    world_state: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new_game(cls, starting_level: int = 1) -> "SaveGame":
        party = new_default_party(level=starting_level)
        world_state = {
            "region": "grasslands",
            "map_id": "overworld_01",
            "player_x": 0,
            "player_y": 0,
        }
        story_flags = {
            # Example: these will be toggled by story scripting
            "met_nyra": True,
            "met_kaira": False,
        }
        return cls(
            party=party,
            story_flags=story_flags,
            world_state=world_state,
        )
