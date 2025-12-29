from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class EncounterRules:
    """Pure data rules for when rolls happen (distance-based)."""

    # Roll cadence: accumulate moved pixels, roll once each time meter crosses step_px.
    step_px: float

    # After a successful trigger, suppress rolls for at least this many pixels.
    cooldown_px: float = 0.0

    # --- Threat accumulation ---
    threat_threshold: float = 1.0   # value needed to trigger encounter

    threat_base_add: float = 0.08   # always added per step
    threat_rand_lo: float = 0.00    # random add range (low)
    threat_rand_hi: float = 0.22    # random add range (high)

    threat_spike_chance: float = 0.07
    threat_spike_add_lo: float = 0.20
    threat_spike_add_hi: float = 0.55


@dataclass(frozen=True)
class EncounterEntry:
    """One weighted choice on the encounter table."""
    enemy_party_id: str
    weight: int = 1


@dataclass(frozen=True)
class EncounterGating:
    """Optional flag gating. Validator checks shape; runtime checks truth."""
    requires_flags_all: Tuple[str, ...] = ()
    forbids_flags_any: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EncounterProfile:
    """Resolved encounter profile (pure authoring data)."""
    id: str
    rules: EncounterRules
    table: Sequence[EncounterEntry]
    gating: EncounterGating = EncounterGating()

    # Optional authoring hints for later
    backdrop_id: str | None = None
