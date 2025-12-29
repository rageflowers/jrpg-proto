# engine/battle/battle_command.py

from dataclasses import dataclass, field
from typing import List, Any, Optional

@dataclass
class BattleCommand:
    """
    A neutral, side-agnostic representation of an intended action.
    This is where AI or Player input 'interfaces' with the combat engine.
    """
    actor_id: str

    # "skill", "item", "defend", "wait", "flee", etc.
    command_type: str = "skill"

    skill_id: Optional[str] = None
    item_id: Optional[str] = None
    item_qty: int = 1

    # Concrete target objects or combatant IDs.
    targets: List[Any] = field(default_factory=list)

    # Debug / introspection fields (used by AI)
    source: str = "player"   # or "ai"
    reason: Optional[str] = None
