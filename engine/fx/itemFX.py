"""
Temporary item FX stub module for Forge XVI.0.

FXSystem expects this module to provide functions like `hit_fx`
to build FX profiles for item-based hits. We don't have item-based
FX implemented yet, so these are safe no-ops that return an empty
profile structure.
"""


def hit_fx(fx_tag: str | None, element: str | None, meta: dict | None):
    """
    Build an FX profile for an item-based hit.

    For Forge XVI.0, this just returns an empty dict. FXSystem will
    pass this to apply_hit_fx, which we've also stubbed out to do nothing.
    """
    return {}
