"""
Kaira-specific FX.

Poison edges, curses, shadowy slashes and DoT applications.
"""

from typing import Any, Optional, Dict


def hit_fx(
    fx_tag: Optional[str],
    element: Optional[str],
    meta: Any,
) -> Optional[Dict[str, Any]]:
    if not fx_tag:
        return None

    # Example: poison edge stab
    if fx_tag == "kaira.poison_edge":
        return {
            "shake_strength": 4,
            "shake_duration": 0.22,
            "flash_duration": 0.20,
            # Later: you might add "tint": (r,g,b) for sprite color flashes
        }

    return None
