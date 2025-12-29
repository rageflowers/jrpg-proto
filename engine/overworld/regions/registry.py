from __future__ import annotations

from typing import Dict
from engine.overworld.regions.spec import RegionSpec

# Manual imports for now (safe + explicit). We can upgrade to auto-discovery later.
from engine.overworld.regions.velastra_highlands import REGION as VELASTRA_HIGHLANDS
from engine.overworld.regions.narrow_pass import REGION as NARROW_PASS


_REGION_TABLE: Dict[str, RegionSpec] = {
    VELASTRA_HIGHLANDS.id: VELASTRA_HIGHLANDS,
    NARROW_PASS.id: NARROW_PASS,
}


def get_region(region_id: str) -> RegionSpec:
    try:
        return _REGION_TABLE[region_id]
    except KeyError as e:
        known = ", ".join(sorted(_REGION_TABLE.keys()))
        raise KeyError(f"Unknown region_id='{region_id}'. Known: {known}") from e
