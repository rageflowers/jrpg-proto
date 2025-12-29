# engine/overworld/aerial_actor/factory.py
from __future__ import annotations

import random
from typing import Optional

from engine.overworld.regions.spec import AerialActorSpec
from engine.overworld.aerial_actor.api import AerialActor
from engine.overworld.aerial_actor.birds_strokes import build_birds_strokes
from engine.overworld.aerial_actor.crow import build_crow


def build_aerial_actor(
    spec: Optional[AerialActorSpec],
    *,
    assets,
    internal_w: int,
    horizon_y: int,
    rng: Optional[random.Random] = None,
) -> AerialActor | None:
    if spec is None:
        return None

    if spec.kind == "birds" and (spec.render_mode or "strokes") == "strokes":
        return build_birds_strokes(spec, internal_w=internal_w, horizon_y=horizon_y, rng=rng)

    if spec.kind == "crow":
        return build_crow(
            spec,
            assets=assets,
            internal_w=internal_w,
            horizon_y=horizon_y,
            rng=rng,
        )

    raise ValueError(f"Unknown aerial_actor kind={spec.kind!r} render_mode={spec.render_mode!r}")
