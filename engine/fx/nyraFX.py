"""
Nyra-specific FX.

Holy, supportive, shielding and radiant attacks go here.
"""

from typing import Any, Optional, Dict


def hit_fx(
    fx_tag: Optional[str],
    element: Optional[str],
    meta: Any,
) -> Optional[Dict[str, Any]]:
    if not fx_tag:
        return None

    # Example offensive holy hit
    if fx_tag == "nyra.holy_lance":
        return {
            "shake_strength": 4,
            "shake_duration": 0.18,
        }

    return None


def heal_fx(
    fx_tag: Optional[str],
    element: Optional[str],
    meta: Any,
) -> Optional[Dict[str, Any]]:
    if not fx_tag:
        return None

    # Example: Affirmation heal
    if fx_tag == "nyra.affirmation":
        return {
            "flash_duration": 0.26,  # soft, radiant
        }

    return None
