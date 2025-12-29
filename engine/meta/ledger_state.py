# engine/meta/ledger_state.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any

from engine.actors.character_sheet import CharacterInstance, new_default_party

SAVE_VERSION = 1


@dataclass
class WorldState:
    # Current location / continuity
    region_id: str = "velastra_highlands"
    spawn_id: str = "default"

    # Optional: if you want precise re-entry (later)
    x: float = 0.0
    y: float = 0.0
    angle: float = 0.0

    # Story / gating flags (authoritative)
    flags: Set[str] = field(default_factory=set)


@dataclass
class PartyState:
    """
    Roster + active selection. Roster entries are CharacterInstance
    (which is already designed to eventually live in save data).
    """
    roster: Dict[str, CharacterInstance] = field(default_factory=dict)
    active_ids: List[str] = field(default_factory=list)

    def get_active_party(self) -> Dict[str, CharacterInstance]:
        return {cid: self.roster[cid] for cid in self.active_ids if cid in self.roster}

@dataclass
class InventoryState:
    # v0 stub: stackables only
    stacks: Dict[str, int] = field(default_factory=dict)

    def add(self, item_id: str, qty: int = 1) -> None:
        if qty <= 0:
            return
        self.stacks[item_id] = int(self.stacks.get(item_id, 0)) + int(qty)

    def remove(self, item_id: str, qty: int = 1) -> bool:
        if qty <= 0:
            return True
        cur = int(self.stacks.get(item_id, 0))
        if cur < qty:
            return False
        newv = cur - int(qty)
        if newv <= 0:
            self.stacks.pop(item_id, None)
        else:
            self.stacks[item_id] = newv
        return True


@dataclass
class WalletState:
    # v0 stub: single currency
    gild: int = 0

    def add(self, amt: int) -> None:
        if amt <= 0:
            return
        self.gild += int(amt)

    def spend(self, amt: int) -> bool:
        amt = int(amt)
        if amt <= 0:
            return True
        if self.gild < amt:
            return False
        self.gild -= amt
        return True


@dataclass
class LedgerState:
    """
    Forge XIX: persistent run/save truth.
    - BattleSession is battle truth.
    - LedgerState is meta truth.
    """
    save_version: int = SAVE_VERSION

    world: WorldState = field(default_factory=WorldState)
    party: PartyState = field(default_factory=PartyState)

    inventory: InventoryState = field(default_factory=InventoryState)
    wallet: WalletState = field(default_factory=WalletState)

    # Optional metadata
    playtime_s: float = 0.0

    # -----------------------------
    # Construction helpers
    # -----------------------------
    @classmethod
    def new_game_default(cls) -> "LedgerState":
        ledg = cls()

        # new_default_party already returns instances keyed by id
        starters = new_default_party(level=1)  # Dict[str, CharacterInstance]

        for cid, inst in starters.items():
            cid = str(cid)

            # optional: if you add an id field later, keep it stable
            try:
                inst.id = cid
            except Exception:
                pass

            ledg.party.roster[cid] = inst
            ledg.party.active_ids.append(cid)

        return ledg

    # -----------------------------
    # Persistence (v0 JSON-ish)
    # -----------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "save_version": int(self.save_version),
            "playtime_s": float(self.playtime_s),
            "world": {
                "region_id": self.world.region_id,
                "spawn_id": self.world.spawn_id,
                "x": float(self.world.x),
                "y": float(self.world.y),
                "angle": float(self.world.angle),
                "flags": sorted(self.world.flags),
            },
            "party": {
                "active_ids": list(self.party.active_ids),
                "roster": {
                    cid: inst.to_dict() if hasattr(inst, "to_dict") else {}
                    for cid, inst in self.party.roster.items()
                },
            },
            "inventory": {"stacks": dict(self.inventory.stacks)},
            "wallet": {"gild": int(self.wallet.gild)},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LedgerState":
        ledg = cls()
        ledg.save_version = int(data.get("save_version", SAVE_VERSION))
        ledg.playtime_s = float(data.get("playtime_s", 0.0))

        w = data.get("world", {}) or {}
        ledg.world.region_id = str(w.get("region_id", ledg.world.region_id))
        ledg.world.spawn_id = str(w.get("spawn_id", ledg.world.spawn_id))
        ledg.world.x = float(w.get("x", 0.0))
        ledg.world.y = float(w.get("y", 0.0))
        ledg.world.angle = float(w.get("angle", 0.0))
        ledg.world.flags = set(w.get("flags", []) or [])

        p = data.get("party", {}) or {}
        ledg.party.active_ids = [str(x) for x in (p.get("active_ids", []) or [])]

        # Rebuild roster from CharacterInstance.from_dict if available
        roster_in = p.get("roster", {}) or {}
        for cid, inst_data in roster_in.items():
            cid = str(cid)
            if hasattr(CharacterInstance, "from_dict"):
                try:
                    inst = CharacterInstance.from_dict(inst_data)
                except Exception:
                    continue
            else:
                continue

            # Ensure stable id field
            try:
                setattr(inst, "id", cid)
            except Exception:
                pass

            ledg.party.roster[cid] = inst

        inv = data.get("inventory", {}) or {}
        ledg.inventory.stacks = {str(k): int(v) for k, v in (inv.get("stacks", {}) or {}).items()}

        wal = data.get("wallet", {}) or {}
        ledg.wallet.gild = int(wal.get("gild", 0))

        return ledg
