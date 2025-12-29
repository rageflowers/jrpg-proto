# engine/battle/status/status_events.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union


@dataclass
class DamageTickEvent:
    """
    Describes a single tick of damage or healing from a status.

    Convention:
      - amount < 0  => damage
      - amount > 0  => healing
    """
    target: Any                  # combatant object
    amount: int                  # signed HP change
    kind: str                    # "burn", "poison", "bleed", "regen", etc.
    damage_type: str             # "physical" or "magic"
    source_status_id: str        # e.g. "burn_1"
    source_combatant: Optional[Any] = None  # who applied it (for logs/FX)


@dataclass
class ApplyStatusEvent:
    """
    Request to apply a status to a target.

    Typically emitted by retaliation, auras, or other statuses.
    """
    target: Any
    status: Any                  # concrete StatusEffect instance OR a factory token
    source_combatant: Optional[Any] = None
    reason: Optional[str] = None


@dataclass
class RemoveStatusEvent:
    """
    Request to remove a status (or set of statuses) from a target.
    """
    target: Any
    status_id: str               # exact id to remove, e.g. "burn_1"
    reason: Optional[str] = None


@dataclass
class RetaliationEvent:
    """
    Describes reflected or retaliatory damage originating from a status.

    Convention:
      - amount < 0 => damage to attacker
      - amount > 0 => healing (rare, but possible)
    """
    attacker: Any                # the combatant who gets hit by the retaliation
    amount: int                  # signed HP change
    kind: str                    # "fire_reflect", "thorns", etc.
    damage_type: str             # "physical" or "magic"
    source_status_id: str        # e.g. "fire_shield_1"
    owner: Optional[Any] = None  # shield owner, for logs/FX
    status_to_apply: Optional[Any] = None  # e.g. Burn I applied to attacker

# A convenience union of all supported status-event types.
StatusEvent = Union[
    DamageTickEvent,
    ApplyStatusEvent,
    RemoveStatusEvent,
    RetaliationEvent,
]
