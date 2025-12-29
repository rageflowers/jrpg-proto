from __future__ import annotations

import math
from engine.overworld.celestial.spec import CelestialProfile, CelestialObjectSpec

# -----------------------------
# Profiles
# -----------------------------

STANDARD_NOON_SUN = CelestialProfile(
    id="standard_noon_sun",
    objects=(
        CelestialObjectSpec(
            kind="stars",
            angle_mode="world",
            radius_px=0,            # unused for stars
            halo_strength=0,
            alpha=255,               # overall star visibility (tune)
            occludable=False,       # stars usually "behind everything"
            draw_layer="behind_clouds",
        ),
        CelestialObjectSpec(
            kind="sun",
            angle_mode="world",      # uses your current sun_angle + camera yaw wrap
            radius_px=22,            # matches your current “smaller disc”
            halo_strength=0,       # matches your current glare vibe
            alpha=255,
            occludable=True,
            draw_layer="behind_clouds",  # clouds naturally occlude
        ),
        
    ),
)


_TABLE = {
    STANDARD_NOON_SUN.id: STANDARD_NOON_SUN,
}


def get_celestial_profile(profile_id: str) -> CelestialProfile:
    try:
        return _TABLE[profile_id]
    except KeyError as e:
        known = ", ".join(sorted(_TABLE.keys()))
        raise KeyError(f"Unknown celestial_profile_id='{profile_id}'. Known: {known}") from e
