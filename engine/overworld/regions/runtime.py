# engine/overworld/regions/runtime.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any
import random

from engine.overworld.regions.spec import RegionSpec
from engine.overworld.presenters.mode7_presenter import SkyState
from engine.overworld.regions.silhouettes import SilhouetteSystem

@dataclass
class RegionRuntime:
    """
    Mutable region instance state.
    Spec is immutable identity; runtime owns time/state and resolved runtime objects.
    """
    spec: RegionSpec
    sky: SkyState
    celestial: Optional[Any]          # CelestialProfile (kept Any to avoid import cycles)
    aerial_actor: Optional[Any]       # AerialActor runtime (duck-typed)
    rng: random.Random
    silhouettes: SilhouetteSystem

    def update(self, dt: float) -> None:
        # Authoritative sky clock
        self.sky.t += dt

        # Optional simulation ticking for sky life
        if self.aerial_actor is not None and hasattr(self.aerial_actor, "update"):
            self.aerial_actor.update(dt)
