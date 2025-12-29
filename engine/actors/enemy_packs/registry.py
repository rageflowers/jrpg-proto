# engine/actors/enemy_packs/registry.py
from __future__ import annotations

import importlib
from typing import Iterable

# Monotonic: once loaded, never unloaded in-process.
_LOADED: set[str] = set()

# Explicit mapping (safe + deterministic). Upgrade to auto-discovery later if desired.
_PACK_MODULES: dict[str, str] = {
    "merchant_trail": "engine.actors.enemy_packs.merchant_trail",
}
def known_enemy_packs() -> tuple[str, ...]:
    return tuple(sorted(_PACK_MODULES.keys()))


def load_enemy_packs(pack_ids: Iterable[str]) -> None:
    """
    Load enemy packs by id, idempotently.

    This performs the ONLY pack imports in the engine.
    Packs must expose a function:
        register(register_enemy_template) -> None
    """
    # Local import to avoid cycles and keep this module "content-only".
    from engine.actors.enemy_sheet import register_enemy_template

    for pid in pack_ids:
        if not isinstance(pid, str) or not pid.strip():
            raise ValueError(f"enemy pack id must be a non-empty string (got {pid!r})")

        if pid in _LOADED:
            continue

        mod_path = _PACK_MODULES.get(pid)
        if not mod_path:
            known = ", ".join(sorted(_PACK_MODULES.keys()))
            raise KeyError(f"Unknown enemy pack id {pid!r}. Known: {known}")

        mod = importlib.import_module(mod_path)

        register_fn = getattr(mod, "register", None)
        if not callable(register_fn):
            raise AttributeError(
                f"Enemy pack module {mod_path!r} must expose callable register(register_enemy_template)."
            )

        register_fn(register_enemy_template)
        _LOADED.add(pid)


def is_enemy_pack_loaded(pack_id: str) -> bool:
    return pack_id in _LOADED
