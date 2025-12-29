# jrpg_story.py

from __future__ import annotations
from enum import Enum, auto

class StoryFlag(Enum):
    VELASTRA_INTRO_DONE = auto()
    TUTORIAL_BATTLE_WON = auto()
    VAELARAS_BEHEMOTH_DEFEATED = auto()
    ALL_GATES_ALIGNED = auto()
    FINAL_BOSS_DEFEATED = auto()

class StoryState:
    def __init__(self) -> None:
        self.flags: set[StoryFlag] = set()

    def has(self, flag: StoryFlag) -> bool:
        return flag in self.flags

    def set(self, flag: StoryFlag) -> None:
        self.flags.add(flag)

    def debug(self) -> None:
        print("Story Flags:", ", ".join(f.name for f in self.flags))
