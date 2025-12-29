from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional


@dataclass
class BattleGains:
    """
    Battle-local progression buffer.

    Rules:
    - NO ledger mutation here.
    - Tracks deltas acquired/consumed during battle.
    - Commit happens only at true battle end (BattleOutcome consumption layer).
    """

    # --------------------------------------------
    # XP / currency
    # --------------------------------------------
    xp_gained: Dict[str, int] = field(default_factory=dict)   # actor_id -> xp
    gold_gained: int = 0

    # --------------------------------------------
    # Items (earned and consumed during battle)
    # --------------------------------------------
    items_gained: List[Tuple[str, int]] = field(default_factory=list)    # (item_id, qty)
    items_consumed: List[Tuple[str, int]] = field(default_factory=list)  # (item_id, qty)

    # --------------------------------------------
    # Battle facts used for policy decisions
    # --------------------------------------------
    enemies_defeated: Set[str] = field(default_factory=set)   # enemy_id (or combatant id)
    defeated_count: int = 0

    # Optional: if you want to support narrative phase transitions later
    tags: Dict[str, object] = field(default_factory=dict)

    # -----------------------------
    # Helpers
    # -----------------------------
    def add_xp(self, actor_id: str, amount: int) -> None:
        if amount <= 0:
            return
        self.xp_gained[actor_id] = int(self.xp_gained.get(actor_id, 0)) + int(amount)

    def add_gold(self, amount: int) -> None:
        if amount <= 0:
            return
        self.gold_gained += int(amount)

    def add_item(self, item_id: str, qty: int = 1) -> None:
        if not item_id or qty <= 0:
            return
        self.items_gained.append((str(item_id), int(qty)))

    def consume_item(self, item_id: str, qty: int = 1) -> None:
        if not item_id or qty <= 0:
            return
        self.items_consumed.append((str(item_id), int(qty)))

    def mark_enemy_defeated(self, enemy_id: str) -> None:
        if not enemy_id:
            return
        if enemy_id not in self.enemies_defeated:
            self.enemies_defeated.add(str(enemy_id))
            self.defeated_count += 1

    # -----------------------------
    # Policy utilities
    # -----------------------------
    def apply_defeat_policy(self) -> "BattleGains":
        """
        For LOSS policy: keep XP only (per your doctrine).
        Returns a new gains snapshot with loot/currency removed.
        """
        return BattleGains(
            xp_gained=dict(self.xp_gained),
            gold_gained=0,
            items_gained=[],
            items_consumed=list(self.items_consumed),
            enemies_defeated=set(self.enemies_defeated),
            defeated_count=int(self.defeated_count),
            tags=dict(self.tags),
        )

    def apply_escape_policy(self, keep_only_defeated: Optional[Set[str]] = None) -> "BattleGains":
        """
        For FLEE policy: keep XP + spoils for defeated enemies only.
        For now, we keep all XP and *optionally* filter items later once loot attribution exists.
        """
        # In v0 we don't yet attribute loot to specific enemies, so we keep items_gained as-is.
        # Once loot attribution exists (enemy_id -> drops), we can filter here.
        return BattleGains(
            xp_gained=dict(self.xp_gained),
            gold_gained=int(self.gold_gained),
            items_gained=list(self.items_gained),
            items_consumed=list(self.items_consumed),
            enemies_defeated=set(self.enemies_defeated),
            defeated_count=int(self.defeated_count),
            tags=dict(self.tags),
        )
    def consumed_totals(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for item_id, qty in self.items_consumed:
            totals[item_id] = totals.get(item_id, 0) + int(qty)
        return totals

    def gained_totals(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for item_id, qty in self.items_gained:
            totals[item_id] = totals.get(item_id, 0) + int(qty)
        return totals
