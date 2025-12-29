from __future__ import annotations
import math
from engine.overworld.camera.controller import CameraMode
from engine.overworld.regions.spec import (
    RegionSpec,
    CameraSpec,
    CelestialProfileRef,
    SilhouetteBandSpec,
    EncounterProfileRef,
    AerialActorSpec,
    WeatherProfileRef,
    ExitSpec,
)

REGION = RegionSpec(
    id="velastra_highlands",
    name="Velastra Highlands",
    presenter_type="mode7",
    default_camera_mode="follow",
    tmx_path="assets/maps/velastra_highlands.tmx",    
    aerial_actor=AerialActorSpec(
        kind="birds",
        render_mode="strokes",
        params={
            "count": 8,
            "calm": 0.55,
            "x_pad": 80,          # allow drift wrap padding
            "y_min": 95,
            "y_max": 165,
            "scale_min": 0.50,
            "scale_max": 0.90,
            "vx_min": 0.15,
            "vx_max": 1.60,
            "span_mul_min": 0.90,
            "span_mul_max": 1.20,
            "flap_hz_min": 0.70,
            "flap_hz_max": 1.80,
            "flap_amp_min": 0.04,
            "flap_amp_max": 0.10,
            "bob_hz_min": 0.08,
            "bob_hz_max": 0.25,
            "bob_amp_min": 0.20,
            "bob_amp_max": 0.80,
        },
    ),
    celestial=CelestialProfileRef(profile_id="standard_noon_sun"),
    camera=CameraSpec(
        focal_len=240.0,
        alt=120.0,
        horizon=120.0,
        scale=1.0,
        vanish_shift=0.0,
    ),
    silhouettes=(
        # NOTE: Replace image paths with your actual silhouette assets.
        # Tier 3: FAR_DEEP (behind floor)
        SilhouetteBandSpec(
            image_path="silhouettes/velastra/distant_aurethil.png",
            tier=3,
            target_height_px=80,
            preserve_aspect=False,
            tile_width_mul=1.0,
            y_offset=40,
            yaw_factor=0.18,
            facing_angle_rad=math.pi / 2,
            fade_inner_rad=0.18,
            fade_outer_rad=0.95,
            alpha_max=190,
            alpha_min=0,
            horizon_overlap=55,
        ),
        # Tier 2: FAR (in front of floor)
        SilhouetteBandSpec(
            image_path="silhouettes/velastra/velastra_far.png",
            tier=2,
            target_height_px=100,
            preserve_aspect=False,
            tile_width_mul=0.7,
            y_offset=0,
            yaw_factor=0.18,
            facing_angle_rad=-math.pi / 2,
            fade_inner_rad=0.18,
            fade_outer_rad=0.95,
            alpha_max=235,
            alpha_min=0,
            horizon_overlap=30,
        ),
        # Tier 1: MID
        SilhouetteBandSpec(
            image_path="silhouettes/velastra/north_subalpine_base.png",
            tier=1,
            target_height_px=100,
            preserve_aspect=False,
            tile_width_mul=2.0,
            y_offset=10,
            yaw_factor=0.18,
            facing_angle_rad=-math.pi,
            fade_inner_rad=0.18,
            fade_outer_rad=0.95,
            alpha_max=235,
            alpha_min=0,
            horizon_overlap=30,
        ),
    ),
    weather=WeatherProfileRef(profile_id="velastra_clear_noon"),
    exits=(
        ExitSpec(
            id="to_narrow_pass",
            to_region_id="narrow_pass",
            to_spawn="from_velastra",  # spawn resolution comes next
        ),
    ),
    enemy_packs=("merchant_trail",),
    encounters=EncounterProfileRef(profile_id="velastra_highlands__wander"),

)
