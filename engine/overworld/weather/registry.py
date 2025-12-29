from __future__ import annotations
from engine.overworld.weather.spec import WeatherProfile, CloudLayerSpec, SkyGradientSpec, HazeBandSpec

VELASTRA_CLEAR_NOON = WeatherProfile(
    id="velastra_clear_noon",
    sky=SkyGradientSpec(
        top=(120, 185, 255),
        bottom=(185, 220, 255),
        step=4,
    ),
    haze=(
        HazeBandSpec(
            y_from_horizon=-10,
            height_px=28,
            alpha_top=0,
            alpha_bottom=55,
        ),
    ),
    clouds=(
        CloudLayerSpec(
            image_path="sky/clouds_far.png",
            width_mul=3.0,
            height_px=140,
            speed_px_s=6.0,
            yaw_factor=0.2,
            y=0,
            alpha=160,
        ),
        CloudLayerSpec(
            image_path="sky/clouds_near.png",
            width_mul=3.0,
            height_px=180,
            speed_px_s=14.0,
            yaw_factor=0.4,
            y=0,
            alpha=190,
        ),
    ),
)

_TABLE = {
    VELASTRA_CLEAR_NOON.id: VELASTRA_CLEAR_NOON,
}

def get_weather_profile(profile_id: str) -> WeatherProfile:
    try:
        return _TABLE[profile_id]
    except KeyError as e:
        known = ", ".join(sorted(_TABLE.keys()))
        raise KeyError(f"Unknown weather_profile_id='{profile_id}'. Known: {known}") from e
