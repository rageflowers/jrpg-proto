from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EffectiveCombatant:
    """
    Lightweight proxy that overrides base stats while delegating everything
    else to the wrapped entity.

    Works with engine.battle.damage._get_effective_stats() because that code
    only uses getattr(entity, "atk"/"mag"/"defense"/"mres"/"spd") and then
    reads entity.status for modifiers.
    """
    base: Any
    atk_bonus: float = 0.0
    mag_bonus: float = 0.0
    def_bonus: float = 0.0
    mres_bonus: float = 0.0
    spd_bonus: float = 0.0

    @property
    def atk(self) -> float:
        return float(getattr(self.base, "atk", 0)) + float(self.atk_bonus)

    @property
    def mag(self) -> float:
        return float(getattr(self.base, "mag", 0)) + float(self.mag_bonus)

    @property
    def defense(self) -> float:
        return float(getattr(self.base, "defense", 0)) + float(self.def_bonus)

    @property
    def mres(self) -> float:
        return float(getattr(self.base, "mres", 0)) + float(self.mres_bonus)

    @property
    def spd(self) -> float:
        return float(getattr(self.base, "spd", 0)) + float(self.spd_bonus)

    @property
    def status(self):
        # preserve status modifiers from the real entity
        return getattr(self.base, "status", None)

    def __getattr__(self, name: str):
        # delegate everything else (id, name, is_enemy, etc.)
        return getattr(self.base, name)
