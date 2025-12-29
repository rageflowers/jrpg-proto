# engine/overworld/regions/builder.py
from __future__ import annotations

from typing import Optional
import random
import pygame

from engine.overworld.regions.validate import validate_region_spec

from engine.overworld.presenters.mode7_presenter import SkyState, SkyLayer
from engine.overworld.aerial_actor.factory import build_aerial_actor
from engine.overworld.celestial.registry import get_celestial_profile
from engine.overworld.weather.registry import get_weather_profile
from engine.overworld.regions.runtime import RegionRuntime
from engine.overworld.regions.spec import RegionSpec
from engine.overworld.regions.silhouette_builder import build_silhouettes

# If you're reading this during a refactor spiral:
# breathe — you're doing beautifully.


def build_region_runtime(
    spec: RegionSpec,
    *,
    assets,
    internal_w: int,
    horizon_y: int,
    seed: Optional[int] = None,
) -> RegionRuntime:
    """
    Resolve declarative RegionSpec into a living RegionRuntime.

    - Loads weather profile + builds cloud layer surfaces
    - Resolves celestial profile refs
    - Builds aerial actor runtime object
    - Seeds RNG for deterministic region-instance behavior
    """
    from engine.actors.enemy_packs.registry import load_enemy_packs
    load_enemy_packs(getattr(spec, "enemy_packs", ()))

    issues = validate_region_spec(spec)
    if issues:
        region_id = getattr(spec, "id", None) or getattr(spec, "name", None) or "<unnamed-region>"
        print(f"[RegionSpec] Validation warnings for {region_id}:")
        for msg in issues:
            print(f"  - {msg}")
    rng = random.Random(seed)

    # -----------------------------
    # Celestial Configuration
    # -----------------------------
    celestial_ref = getattr(spec, "celestial", None)
    celestial = get_celestial_profile(celestial_ref.profile_id) if celestial_ref else None

    # -----------------------------
    # Sky (weather-profile-driven)
    # -----------------------------
    weather_ref = getattr(spec, "weather", None)

    if weather_ref is not None:
        profile = get_weather_profile(weather_ref.profile_id)

        sky = SkyState(
            t=0.0,
            layers=[],
            gradient=getattr(profile, "gradient", None) or getattr(profile, "sky", None),
            haze=profile.haze,
        )

        for cl in profile.clouds:
            src = assets.image(cl.image_path)

            w = max(1, int(internal_w * cl.width_mul))
            h = max(1, int(cl.height_px))

            surf = pygame.transform.smoothscale(src, (w, h))

            if cl.alpha is not None:
                surf.set_alpha(int(cl.alpha))

            sky.layers.append(
                SkyLayer(
                    surf=surf,
                    speed_px_s=float(cl.speed_px_s),
                    yaw_factor=float(cl.yaw_factor),
                    y=int(cl.y),
                    alpha=int(cl.alpha) if cl.alpha is not None else 255,
                )
            )
    else:
        # No weather profile — clear sky, no haze, no clouds
        sky = SkyState(t=0.0, layers=[], gradient=None, haze=())

    # -----------------------------
    # Aerial Actor (region-owned runtime object)
    # -----------------------------
    aerial_actor = build_aerial_actor(
        spec.aerial_actor,
        assets=assets,
        internal_w=internal_w,
        horizon_y=int(horizon_y),
        rng=rng,
    )

    silhouettes = build_silhouettes(
        spec,
        assets=assets,
        internal_w=internal_w,
    )

    return RegionRuntime(
        spec=spec,
        sky=sky,
        celestial=celestial,
        aerial_actor=aerial_actor,
        silhouettes=silhouettes,
        rng=rng,
    )
