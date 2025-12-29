# engine/overworld/regions/narrow_pass.py
# ============================================================
# NARROW PASS — FORGE XVIII.11
# ------------------------------------------------------------
# Status: COMPLETE (for now)
#
# Purpose:
#   Transitional space between openness and enclosure.
#   Emotional compression before the Great Forest.
#
# Design Notes:
#   - Camera restraint over spectacle
#   - Vegetation escalates tension, not density
#   - Encounters tuned for anticipation, not punishment
#
# Narrative Role:
#   This pass prepares the player to *need* Kaira.
#   Silence, narrowing paths, and watchful growth do the work.
#
# Revisit Later For:
#   - Soundscape
#   - Kaira join beat
#   - Final encounter tuning
# ============================================================

from __future__ import annotations

from engine.overworld.regions.spec import (
    RegionSpec,
    CameraSpec,
    ExitSpec,
    EncounterProfileRef,
    WeatherProfileRef,
    AerialActorSpec,
)

REGION = RegionSpec(
    id="narrow_pass",
    name="Narrow Pass",
    presenter_type="overhead",  # contrast testbed (we'll add overhead presenter next)
    default_camera_mode="follow",
    tmx_path="assets/maps/narrow_pass.tmx",
    aerial_actor=AerialActorSpec(
    kind="crow",
    params={
        "frames": [
            "sprites/overworld/crow_00.png",
            "sprites/overworld/crow_01.png",
            "sprites/overworld/crow_02.png",
        ],
        # orbit + “life” (tune later)
        "radius_x": 170.0,
        "radius_y": 90.0,
        "angular_speed": 0.22,
        "alpha_center": 190,
        "alpha_amp": 14,
        "scale_center": 1.0,
        "scale_amp": 0.05,
        "rot_jitter_deg": 2.0,

        # anchor in INTERNAL coords (overhead presenter’s internal surface space)
        "anchor_x_norm": 0.55,
        "anchor_y_norm": 0.22,

        # animation cadence: flap → glide → glide → flap → glide
        "anim_pattern": [2, 1, 0, 2, 1],
        "anim_fps": 6.0,
        },
    ),
    # CameraSpec is still required by RegionSpec even if overhead ignores it later.
    # Keep conservative defaults; we can tune once overhead presenter exists.
    camera=CameraSpec(
        focal_len=240.0,
        alt=120.0,
        horizon=120.0,
        scale=1.0,
        vanish_shift=0.0,
    ),

    # Placeholder weather so RegionRuntime builder stays happy if you want it.
    # If you don't have a profile yet, set this to None.
    weather=WeatherProfileRef(profile_id="velastra_clear_noon"),

    # Exits are REGION INTENT; TMX exits are the collision truth.
    # IMPORTANT: these ExitSpec.id values must match the TMX exit object names.
    exits=(
        ExitSpec(
            id="to_velastra_highlands",
            to_region_id="velastra_highlands",
            to_spawn="from_pass",   # semantic label (spawn system coming next)
        ),
    ),

    # Optional: if you want encounters here later, set an actual profile id.
    # encounters=EncounterProfileRef(profile_id="narrow_pass__scripted"),
    encounters=None,
)
