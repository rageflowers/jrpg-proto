from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal, Tuple


CelestialKind = Literal[
    "sun",
    "moon",
    "stars",
    "comet",
    "void_comet",
]

AngleMode = Literal[
    "world",    # uses world / camera-relative angle (e.g. sun today)
    "fixed",    # fixed angle in sky-dome
    "time",     # derived from time-of-day (future)
    "scripted", # driven by story/event overrides (future)
]


@dataclass(frozen=True)
class CelestialObjectSpec:
    """
    Declarative description of a single celestial object.
    No rendering logic. No time logic. Pure truth.
    """
    kind: CelestialKind

    # How this object's angle is determined
    angle_mode: AngleMode = "world"

    # Used if angle_mode == "fixed"
    fixed_angle_rad: Optional[float] = None

    # Visual intent (renderer decides how)
    radius_px: int = 24
    halo_strength: int = 0
    alpha: int = 255

    # Optional sprite (moon texture, comet head, etc.)
    sprite_path: Optional[str] = None

    # Whether clouds should occlude this object
    occludable: bool = True

    # Draw ordering hint relative to clouds
    draw_layer: Literal["behind_clouds", "in_front_of_clouds"] = "behind_clouds"


@dataclass(frozen=True)
class CelestialProfile:
    """A named configuration of celestial objects for a region/state."""
    id: str
    objects: Tuple[CelestialObjectSpec, ...]
