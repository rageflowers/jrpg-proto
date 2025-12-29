# engine/battle/damage.py
#
# Centralized damage model for Forge XVI.7 — By the Four Winds.
# All damage (player skills, enemy attacks, weapon strikes, magical arts)
# flows through this one shared function.

from __future__ import annotations
from typing import Any, Tuple, Dict


def _get_effective_stats(entity: Any) -> Dict[str, float]:
    """
    Build a full effective stat block from entity:
      - base stats (atk, mag, defense, mres, spd)
      - status modifiers (mults + adds via StatusManager.get_stat_modifiers)
    """
    base_atk = float(getattr(entity, "atk", 0))
    base_mag = float(getattr(entity, "mag", 0))
    base_def = float(getattr(entity, "defense", 0))
    base_mres = float(getattr(entity, "mres", 0))
    base_spd = float(getattr(entity, "spd", 0))

    status_mgr = getattr(entity, "status", None)
    if status_mgr and hasattr(status_mgr, "get_stat_modifiers"):
        mods = status_mgr.get_stat_modifiers()
    else:
        # default neutral
        mods = {
            "atk_mult": 1.0, "def_mult": 1.0, "mag_mult": 1.0, "mres_mult": 1.0, "spd_mult": 1.0,
            "atk_add": 0.0, "def_add": 0.0, "mag_add": 0.0, "mres_add": 0.0, "spd_add": 0.0,
        }

    return {
        "atk": base_atk * mods["atk_mult"] + mods["atk_add"],
        "mag": base_mag * mods["mag_mult"] + mods["mag_add"],
        "def": base_def * mods["def_mult"] + mods["def_add"],
        "mres": base_mres * mods["mres_mult"] + mods["mres_add"],
        "spd": base_spd * mods["spd_mult"] + mods["spd_add"],
        "mods": mods,
    }


def compute_damage(
    attacker: Any,
    defender: Any,
    *,
    element: str = "none",
    base_damage: float = 1.0,
    damage_type: str = "physical",
    variance: float = 0.10,   # ±10%
) -> Tuple[int, Dict[str, float]]:
    """
    Shared damage model – Forge XVII.18c.

    Args:
        attacker: source entity (for stat lookups & logs).
        defender: target entity.
        element: elemental tag ("none", "fire", etc.) – currently informational.
        base_damage: pre-defense damage value that ALREADY includes
            the attacker's offensive stat and any skill scaling.
        damage_type: "physical" or "magic" (selects DEF vs MRES).
        variance: ±percentage random variance (0.10 = ±10%).

    Returns:
        final_raw_damage_before_statuses, breakdown_dict

    This is the *unmodified* damage that will be fed into the
    status pipeline (shields, buffs, reflect, etc.)
    """
    atk = _get_effective_stats(attacker)
    dfd = _get_effective_stats(defender)

    # ------------------------------------------------------------
    # 1) Choose appropriate defense axis for mitigation
    # ------------------------------------------------------------
    if damage_type == "magic":
        offensive = atk["mag"]
        defensive = dfd["mres"]
    else:
        offensive = atk["atk"]
        defensive = dfd["def"]

    # ------------------------------------------------------------
    # 2) Base formula (tunable)
    #
    # Forge XVII.18c convention:
    #   - base_damage is pre-defense damage (already includes ATK/MAG & skill coeffs)
    #   - defensive stat shaves off a linear portion
    # ------------------------------------------------------------
    raw = base_damage - (defensive * 0.6)

    # ------------------------------------------------------------
    # 3) Apply ±variance %
    # ------------------------------------------------------------
    if variance > 0:
        import random
        factor = 1.0 + random.uniform(-variance, variance)
        raw *= factor

    # ------------------------------------------------------------
    # 4) Clamp minimum
    # ------------------------------------------------------------
    raw = int(max(1, raw))

    breakdown = {
        "offensive": offensive,
        "defensive": defensive,
        "base_damage": base_damage,
        "element": element,
        "damage_type": damage_type,
        "variance_applied": variance,
        "final_raw": raw,
    }

    return raw, breakdown

