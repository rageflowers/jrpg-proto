from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple


@dataclass(frozen=True)
class WeaponBonus:
    atk_bonus: float = 0.0
    mag_bonus: float = 0.0


def get_weapon_bonus_for_user(user: Any, battle_state: Any) -> WeaponBonus:
    """
    Battle-local weapon bonuses only.

    Reads:
      battle_state.runtime.equipment[actor_id] -> weapon_id
    Looks up weapon def via engine.items.defs.get_item(weapon_id).

    If anything is missing, returns neutral bonuses.
    """
    runtime = getattr(battle_state, "runtime", None)
    if runtime is None:
        return WeaponBonus()

    equip_map = getattr(runtime, "equipment", None)
    if not isinstance(equip_map, dict):
        return WeaponBonus()

    actor_id = getattr(user, "id", None)
    if not actor_id:
        return WeaponBonus()

    weapon_id = equip_map.get(str(actor_id))
    if not weapon_id:
        return WeaponBonus()

    # local import keeps cycles down
    from engine.items.defs import get_item
    wdef = get_item(str(weapon_id))
    if wdef is None or getattr(wdef, "kind", None) != "weapon":
        return WeaponBonus()

    # These fields will exist once we extend ItemDef + weapon library.
    atk = float(getattr(wdef, "atk_bonus", 0.0) or 0.0)
    mag = float(getattr(wdef, "mag_bonus", 0.0) or 0.0)
    return WeaponBonus(atk_bonus=atk, mag_bonus=mag)
