# engine/items/weapons.py
from engine.items.defs import ItemDef, register_item


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
            description="A focus for budding mages.",
        )
    )
