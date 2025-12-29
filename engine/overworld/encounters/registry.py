from __future__ import annotations

from typing import Dict, Optional
from engine.overworld.encounters.spec import EncounterProfile

_ENCOUNTER_TABLE: Dict[str, EncounterProfile] = {}

def register_encounter_profile(profile: EncounterProfile) -> None:
    if not isinstance(profile.id, str) or not profile.id.strip():
        raise ValueError("EncounterProfile.id must be a non-empty string")
    _ENCOUNTER_TABLE[profile.id] = profile

def get_encounter_profile(profile_id: str) -> Optional[EncounterProfile]:

    return _ENCOUNTER_TABLE.get(profile_id)
# ------------------------------------------------------------
# Minimal seed profiles (safe defaults for early testing)
# ------------------------------------------------------------

def _seed_defaults() -> None:
    # Import here to avoid circular imports if profiles later reference other registries.
    from engine.overworld.encounters.spec import (
        EncounterRules,
        EncounterEntry,
        EncounterGating,
        EncounterProfile,
    )

    # Velastra Highlands: sparse early danger
    register_encounter_profile(
        EncounterProfile(
            id="velastra_highlands__wander",
            rules=EncounterRules(
                step_px=200.0,
                cooldown_px=420.0,

                threat_threshold=1.0,
                threat_base_add=0.08,
                threat_rand_hi=0.22,
                threat_spike_chance=0.07,
                threat_spike_add_hi=0.55,
            ),

            table=(
                EncounterEntry(enemy_party_id="trail_wolf", weight=70),
                EncounterEntry(enemy_party_id="merchant_wasp", weight=30),
            ),
            gating=EncounterGating(),
            backdrop_id="velastra_highlands",
        )
    )


_seed_defaults()
