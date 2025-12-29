from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple

Color = Tuple[int, int, int]

@dataclass(frozen=True)
class CloudLayerSpec:
    image_path: str                 # asset-relative path (rooted under assets/)
    width_mul: float = 3.0          # internal_w * width_mul
    height_px: int = 140
    speed_px_s: float = 6.0
    yaw_factor: float = 0.2
    y: int = 0
    alpha: Optional[int] = None     # if None, leave as-is


@dataclass(frozen=True)
class SkyGradientSpec:
    top: Color = (120, 185, 255)
    bottom: Color = (185, 220, 255)
    step: int = 4                   # matches your current 0..ih step size


@dataclass(frozen=True)
class WeatherProfile:
    id: str
    sky: SkyGradientSpec | None = None
    haze: tuple[HazeBandSpec] = ()
    clouds: tuple[CloudLayerSpec] = ()

@dataclass(frozen=True)
class HazeBandSpec:
    """
    A simple vertical haze band blended over the sky near the horizon.
    y_from_horizon: offset relative to horizon (negative = above horizon).
    height_px: vertical size of the haze band.
    alpha_top/bottom: alpha ramp within the band.
    """
    y_from_horizon: int = -30
    height_px: int = 80
    alpha_top: int = 0
    alpha_bottom: int = 160