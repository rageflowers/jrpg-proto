"""
Setia-specific FX.

All of Setia's martial / wind / weapon techniques, including higher-tier
evolutions, should live here.
"""

from typing import Any, Optional, Dict


def hit_fx(
    fx_tag: Optional[str],
    element: Optional[str],
    meta: Any,
) -> Optional[Dict[str, Any]]:
    """
    Return a dict describing how a Setia hit should feel, or None if this
    module doesn't handle the given fx_tag.

    Keys (all optional):
      - shake_strength: int
      - shake_duration: float
      - flash_duration: float
    """
    if not fx_tag:
        return None

    # Example: placeholder for your existing wind strike
    if fx_tag == "setia.t1.wind_strike":
        return {
            "shake_strength": 6,
            "shake_duration": 0.20,
            "flash_duration": 0.22,
        }

    # Future: t2, t3, t4 evolutions etc.
    # if fx_tag == "setia.t2.whirl_kick": ...

    return None
