# engine/meta/battle_outcome.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set


@dataclass(frozen=True)
class BattleOutcome:
    """
    Pure, meta-facing result of a battle.
    Built from BattleSession logs and/or battle runtime state.
    """
    victory: bool
    defeat: bool

    # Copies from BattleSession logs (battle-local facts)
    xp_log: List[Dict[str, Any]] = field(default_factory=list)
    loot_log: List[Dict[str, Any]] = field(default_factory=list)

    # Optional world mutations (story/quest gating)
    set_flags: Set[str] = field(default_factory=set)
    clear_flags: Set[str] = field(default_factory=set)
