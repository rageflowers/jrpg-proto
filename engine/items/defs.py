# engine/items/defs.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


Targeting = Literal["self", "ally", "party", "enemy", "none"]
ItemKind = Literal["consumable", "weapon", "armor", "accessory", "key", "material"]


@dataclass(frozen=True)
class ItemDef:
    id: str
    name: str
    kind: ItemKind
    targeting: Targeting = "none"

    # For consumables (battle use)
    effect_id: Optional[str] = None

    # For later (equipment compatibility)
    weapon_tags: tuple[str, ...] = ()
    allowed_weapon_tags: tuple[str, ...] = ()


# ---------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------
_ITEMS: dict[str, ItemDef] = {}


def register_item(defn: ItemDef) -> None:
    if not defn.id or not isinstance(defn.id, str):
        raise ValueError("ItemDef.id must be a non-empty string")
    if defn.id in _ITEMS:
        return  # idempotent
    _ITEMS[defn.id] = defn


def get_item(item_id: str) -> ItemDef | None:
    return _ITEMS.get(item_id)


def all_items() -> tuple[ItemDef, ...]:
    return tuple(_ITEMS.values())


# ---------------------------------------------------------------------
# Defaults (v0)
# ---------------------------------------------------------------------
def initialize_default_items() -> None:
    # v0 potion used by the battle Items menu test
    register_item(
        ItemDef(
            id="potion_small",
            name="Potion",
            kind="consumable",
            targeting="ally",
            effect_id="heal_hp_30",
        )
    )
