from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Mapping, Any, Sequence, Literal

CameraModeId = Literal["follow", "script"]

# -----------------------------
# Core region spec (immutable)
# -----------------------------

@dataclass(frozen=True)
class AerialActorSpec:
    """
    Declarative config for sky life (birds, bats, embers, fireflies, etc).
    No pygame surfaces. No timers. No randomness. No state.
    """
    kind: str                 # "birds", "bats", "embers", ...
    render_mode: str = "strokes"   # "strokes" now; later "sprite"
    params: Mapping[str, Any] = None

@dataclass(frozen=True)
class CameraSpec:
    # Defaults; actual camera runtime state lives elsewhere
    focal_len: float = 240.0
    alt: float = 120.0
    horizon: float = 120.0
    scale: float = 1.0
    vanish_shift: float = 0.0

@dataclass(frozen=True)
class CelestialProfileRef:
    profile_id: str

@dataclass(frozen=True)
class SilhouetteBandSpec:
    """
    Declarative authoring spec for a single horizon-anchored silhouette band.

    This is PURE DATA.
    - No surfaces
    - No scaling logic
    - No camera math

    All interpretation happens later in the builder and presenter.

    Think of a silhouette band as:
        "A wide, flat shape that hugs the horizon and reacts to camera yaw."

    Each PNG behaves differently depending on its own dimensions and internal margins,
    so these values are intentionally tuned per-asset and per-region.
    """

    # ------------------------------------------------------------------
    # Asset identity
    # ------------------------------------------------------------------

    #: Path to silhouette image (loaded via Assets cache).
    #: The image should already be horizontally tileable or visually forgiving.
    image_path: str

    #: Depth tier used by the presenter to decide *when* this band draws.
    #: Semantics are a presenter policy, but the current convention is:
    #:   3 = FAR_DEEP   (behind ground plane)
    #:   2 = FAR        (foreground horizon)
    #:   1 = MID
    #:   0 = NEAR
    tier: int = 2

    # ------------------------------------------------------------------
    # Size / scale
    # ------------------------------------------------------------------

    #: Final vertical size of the silhouette band in screen pixels.
    #: This is the single most important tuning knob.
    #:
    #: Larger values make the band feel closer / more dominant.
    #: Smaller values push it visually farther away.
    target_height_px: int = 128

    #: Horizontal span of the band, expressed as a multiple of the internal width.
    #:   1.0  = exactly screen width
    #:   >1.0 = wraps beyond edges (recommended for near/mid layers)
    #:   <1.0 = narrower, more distant feel
    #:
    #: Only used when preserve_aspect is False.
    tile_width_mul: float = 2.0

    #: If True:
    #:   - Image is scaled to target_height_px preserving aspect ratio
    #:   - Resulting slice is tiled horizontally to reach tile_width_mul * width
    #:
    #: If False:
    #:   - Image is scaled directly to (band_width, target_height_px)
    #:
    #: Use preserve_aspect=True for organic silhouettes (trees, ridges).
    #: Use preserve_aspect=False for painterly or already-wide assets.
    preserve_aspect: bool = True

    # ------------------------------------------------------------------
    # Placement / camera response
    # ------------------------------------------------------------------

    #: Vertical offset applied after horizon anchoring.
    #: Positive values move the band upward; negative move it downward.
    #: Use this to compensate for where the “visual base” of the PNG sits.
    y_offset: int = 0

    #: Horizontal parallax response to camera yaw.
    #: Higher values = stronger lateral drift as the camera turns.
    #: Typical range: 0.10 – 0.25
    yaw_factor: float = 0.0

    # ------------------------------------------------------------------
    # Visibility gating (camera-angle-based fade)
    # ------------------------------------------------------------------

    #: Camera yaw (radians) at which this silhouette is strongest / centered.
    #: Think of this as “which direction this silhouette faces.”
    facing_angle_rad: float = 0.0

    #: Inner fade angle (radians).
    #: Within this angle delta, the silhouette is fully visible.
    fade_inner_rad: float = 1.15

    #: Outer fade angle (radians).
    #: Beyond this angle delta, the silhouette is fully faded out.
    fade_outer_rad: float = 1.45

    # ------------------------------------------------------------------
    # Alpha envelope
    # ------------------------------------------------------------------

    #: Maximum alpha applied after fade (0–255).
    #: Lower values make distant layers feel more atmospheric.
    alpha_max: int = 255

    #: Minimum alpha threshold.
    #: If the computed alpha falls below this, the band is skipped entirely.
    alpha_min: int = 0

    # ------------------------------------------------------------------
    # Horizon blending
    # ------------------------------------------------------------------

    #: How many pixels the silhouette is allowed to overlap *below* the horizon.
    #: This softens the seam between sky and ground.
    #: Higher values = softer blend, but too high can feel like floating.
    horizon_overlap: int = 20



@dataclass(frozen=True)
class ExitSpec:
    """
    Region graph connectivity. Exits can be gated by a flag, evaluated by OverworldModel later.
    """
    id: str
    to_region_id: str
    # Optional: where the player appears in destination (could be spawn id)
    to_spawn: Optional[str] = None
    requires_flag: Optional[str] = None  # checked against world flags at runtime


@dataclass(frozen=True)
class EncounterProfileRef:
    """
    Placeholder for Phase 4: encounter logic changes by region.
    """
    profile_id: str


@dataclass(frozen=True)
class RegionSpec:
    id: str
    name: str

    presenter_type: str  # "mode7" or "overhead"
    tmx_path: str

    default_camera_mode: CameraModeId = "follow" 
    aerial_actor: Optional[AerialActorSpec] = None

    camera: CameraSpec = CameraSpec()
    celestial: Optional[CelestialProfileRef] = None

    silhouettes: Sequence[SilhouetteBandSpec] = ()
    weather: Optional[WeatherProfileRef] = None

    exits: Sequence[ExitSpec] = ()
    enemy_packs: tuple[str, ...] = ()
    encounters: Optional[EncounterProfileRef] = None

@dataclass(frozen=True)
class WeatherProfileRef:
    profile_id: str
