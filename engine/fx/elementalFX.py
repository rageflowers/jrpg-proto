"""
Elemental FX shared by all casters in the Fire and Ice schools.

These are not character-specific; they define how the *school* feels at
different tiers.
"""

from typing import Any, Optional, Dict


def hit_fx(
    fx_tag: Optional[str],
    element: Optional[str],
    meta: Any,
) -> Optional[Dict[str, Any]]:
    if element not in ("fire", "ice"):
        return None

    tier = getattr(meta, "tier", None)

    # Very light starter tuning; you can refine per fx_tag later.
    if element == "fire":
        if tier == 1:
            return {"shake_strength": 2, "shake_duration": 0.14}
        if tier == 2:
            return {"shake_strength": 3, "shake_duration": 0.18}
        if tier == 3:
            return {"shake_strength": 5, "shake_duration": 0.22}
        if tier == 4:
            return {"shake_strength": 7, "shake_duration": 0.28}
        # fallback for fire if tier unknown
        return {"shake_strength": 3, "shake_duration": 0.18}

    if element == "ice":
        if tier == 1:
            return {"shake_strength": 1, "shake_duration": 0.12}
        if tier == 2:
            return {"shake_strength": 2, "shake_duration": 0.16}
        if tier == 3:
            return {"shake_strength": 3, "shake_duration": 0.20}
        if tier == 4:
            return {"shake_strength": 4, "shake_duration": 0.24}
        return {"shake_strength": 2, "shake_duration": 0.16}

    return None


def heal_fx(
    fx_tag: Optional[str],
    element: Optional[str],
    meta: Any,
) -> Optional[Dict[str, Any]]:
    # If you ever have elemental-based heals (e.g. fire regen, ice ward), they can live here.
    return None
