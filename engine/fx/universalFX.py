# engine/fx/universalFX.py

from __future__ import annotations
from typing import Dict, Any, Optional

# Minimal early-game FX recipes.
# Each recipe is tiny and describes *intent*, not draw logic.
_RECIPES: Dict[str, Dict[str, Any]] = {
    # Light, satisfying melee impact for basic attacks
    "hit_light": {
        "kind": "hit",
        "impact_flash": 0.10,   # seconds
    },
    # Heavier melee / special attacks
    "hit_heavy": {
        "kind": "hit",
        "impact_flash": 0.14,
        "pulse": 0.28,
        "camera": "sweep",      # tell FXSystem to shove the camera sideways
    },
    # Single-target heal pulse (Nyra T1)
    "heal_single": {
        "kind": "heal",
        "pulse": 0.30,          # seconds
    },
    # Soft aura for buffs (Blessing / future buffs)
    "buff_aura": {
        "kind": "buff",
        "aura": 0.40,           # seconds
    },
    # Shadowy curse-styled strike (Kaira bleed / curses)
    "curse_pulse": {
        "kind": "hit",
        "impact_flash": 0.10,
        "pulse": 0.22,
        "camera": "lurch",
    },
}


def get_recipe(fx_tag: Optional[str], *, default: str) -> Dict[str, Any]:
    """
    Look up a universal FX recipe by fx_tag.

    Args:
        fx_tag: tag from BattleEvent / meta (e.g., "hit_light", "heal_single").
        default: fallback tag if fx_tag is None or missing.

    Returns:
        A small dict describing intent, e.g.:
            { "impact_flash": 0.10, "pulse": 0.22 }
        or {} if no recipe is defined.
    """
    tag = (fx_tag or default).strip() or default
    return _RECIPES.get(tag, {})
