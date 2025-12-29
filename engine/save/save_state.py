# engine/save/save_state.py

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Set
import json
import os

from engine.actors.character_sheet import (
    CharacterInstance,
    default_templates,
    StatBlock,
)


@dataclass
class WorldPosition:
    region_id: str
    x: int
    y: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldPosition":
        return cls(
            region_id=data.get("region_id", "start"),
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
        )


@dataclass
class SaveGame:
    """
    Represents a single save slot.

      - characters: all known CharacterInstance objects by template_id
      - party_order: list of template_ids in the current active party
      - world_position: where the leader is on the overworld
      - story_flags: unlocked events / milestones, used for story gating
    """
    characters: Dict[str, CharacterInstance]
    party_order: List[str]
    world_position: WorldPosition
    story_flags: Set[str]

    # -----------------------------
    # Serialization helpers
    # -----------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "characters": {
                cid: char.to_dict()
                for cid, char in self.characters.items()
            },
            "party_order": list(self.party_order),
            "world_position": self.world_position.to_dict(),
            "story_flags": list(self.story_flags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SaveGame":
        chars_data = data.get("characters", {})
        characters: Dict[str, CharacterInstance] = {}
        for cid, cdata in chars_data.items():
            characters[cid] = CharacterInstance.from_dict(cdata)

        party_order = list(data.get("party_order", []))
        world_position = WorldPosition.from_dict(data.get("world_position", {}))
        story_flags = set(data.get("story_flags", []))

        return cls(
            characters=characters,
            party_order=party_order,
            world_position=world_position,
            story_flags=story_flags,
        )

    # -----------------------------
    # Convenience methods
    # -----------------------------
    @classmethod
    def new_game(cls) -> "SaveGame":
        """
        Build a brand new save with default templates at level 1.
        """
        templates = default_templates()
        characters: Dict[str, CharacterInstance] = {
            tid: CharacterInstance.new_from_template(tmpl, level=1)
            for tid, tmpl in templates.items()
        }

        party_order = ["setia", "nyra", "kaira"]  # default party

        world_position = WorldPosition(region_id="grasslands", x=0, y=0)
        story_flags: Set[str] = set()

        return cls(
            characters=characters,
            party_order=party_order,
            world_position=world_position,
            story_flags=story_flags,
        )

    def add_flag(self, flag: str) -> None:
        self.story_flags.add(flag)

    def has_flag(self, flag: str) -> bool:
        return flag in self.story_flags

    # XP handling
    def award_xp_to_party(self, amount: int, templates=None) -> Dict[str, List[int]]:
        """
        Give XP to all party members.

        Returns:
            {template_id: [levels_gained...], ...}
        """
        if templates is None:
            from engine.actors.character_sheet import default_templates
            templates = default_templates()

        results: Dict[str, List[int]] = {}
        for cid in self.party_order:
            char = self.characters.get(cid)
            if char is None:
                continue
            gained = char.gain_xp(amount, templates)
            if gained:
                results[cid] = gained
        return results


# -----------------------------
# Disk I/O helpers
# -----------------------------

def save_to_file(save: SaveGame, filepath: str) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    data = save.to_dict()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_from_file(filepath: str) -> SaveGame:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return SaveGame.from_dict(data)
