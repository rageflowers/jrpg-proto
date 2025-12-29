"""
Boss & special NPC FX.

This is also where cinematic staged sequences can hook in later, using
custom camera calls and choreography.

For now, it just returns per-tag FX parameters for boss/guest moves.
"""

from typing import Any, Optional, Dict


def hit_fx(
    fx_tag: Optional[str],
    element: Optional[str],
    meta: Any,
) -> Optional[Dict[str, Any]]:
    if not fx_tag:
        return None

    # Example placeholder for a big boss attack
    if fx_tag == "boss.sandwyrm.quake_tail":
        return {
            "shake_strength": 10,
            "shake_duration": 0.45,
        }

    return None


def cinematic_fx(
    scene_id: str,
    step: str,
) -> Dict[str, Any]:
    """
    Stub for later Forge XV/XVI:

    A place where story scripts and choreography can ask for complex
    camera + FX sequences, keyed by scene/step identifiers.
    """
    # For now just return an empty dict; you'll fill this in later.
    return {}
