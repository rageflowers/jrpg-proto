"""
Shared FX for generic enemy attacks.

Reusable feel for claws, bites, dark bolts, poison spits, etc.
"""

from typing import Any, Optional, Dict


def hit_fx(
    fx_tag: Optional[str],
    element: Optional[str],
    meta: Any,
) -> Optional[Dict[str, Any]]:
    if not fx_tag:
        return None

    # Generic melee
    if fx_tag == "enemy.claw":
        return {"shake_strength": 3, "shake_duration": 0.15}
    if fx_tag == "enemy.bite":
        return {"shake_strength": 4, "shake_duration": 0.18}

    # Simple magic examples
    if fx_tag == "enemy.dark_bolt":
        return {"shake_strength": 4, "shake_duration": 0.20}
    if fx_tag == "enemy.poison_spit":
        return {"shake_strength": 3, "shake_duration": 0.17}

    return None
