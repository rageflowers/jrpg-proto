# engine/items/bootstrap.py
from __future__ import annotations

def initialize_items() -> None:
    from engine.items.defs import initialize_default_items
    from engine.items.effects.registry import initialize_default_effects

    initialize_default_items()
    initialize_default_effects()
