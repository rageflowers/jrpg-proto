# engine/items/weapons.py
from engine.items.defs import ItemDef, register_item
from dataclasses import field

weapon_tags: set[str] = field(default_factory=set)


def register_weapons():
    """
    Central weapon library.
    Called during item bootstrap.
    """

    register_item(
        ItemDef(
            id="iron_sword",
            name="Iron Sword",
            kind="weapon",
            atk_bonus=4.0,
            mag_bonus=0.0,
            weapon_tags={"sword"},
            description="A simple but reliable blade.",
        )
    )

    register_item(
        ItemDef(
            id="oak_staff",
            name="Oak Staff",
            kind="weapon",
            atk_bonus=0.0,
            mag_bonus=4.0,
            weapon_tags={"staff"},
            description="A focus for budding mages.",
        )
    )
