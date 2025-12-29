from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


# --- Core flag container -----------------------------------------------------


@dataclass
class BattleFlags:
    """
    High-level battle flags that describe the scenario, NOT the flow.

    - is_boss:        whether this encounter is a boss fight
    - can_escape:     whether the party is allowed to flee
    - phase_index:    current multi-phase boss stage (0-based)
    - aura:           optional ambient aura tag (e.g. "nether", "solar")
    - weather:        optional weather tag (e.g. "storm", "ashfall")
    - extras:         arbitrary script keys (used by story/boss logic)
    """

    is_boss: bool = False
    can_escape: bool = True
    phase_index: int = 0
    aura: Optional[str] = None
    weather: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CombatantRef:
    """
    Lightweight reference wrapper tying an ID string to a concrete combatant
    object, plus which side they belong to ("party" or "enemy").
    """

    id: str
    side: str  # "party" | "enemy"
    obj: Any


# --- Core session object -----------------------------------------------------


class BattleSession:
    """
    BattleSession is the keeper of battle truth.

    It owns:
        - party & enemy combatants
        - HP/MP, stats, equipment (via the combatant objects)
        - KO state (derived from combatants)
        - statuses (once we wire them in)
        - XP & loot logs (battle-local)
        - high-level battle flags

    It does NOT:
        - run CTB or turn flow
        - decide skill math
        - read player input
        - trigger FX
        - manage phase transitions logic (only stores flags)

    Think of it as: the board and all its pieces, frozen in their current state.
    """

    # --------------------------------------------------------------------- #
    # Construction
    # --------------------------------------------------------------------- #

    def __init__(
        self,
        party: Iterable[Any],
        enemies: Iterable[Any],
        flags: Optional[BattleFlags | Dict[str, Any]] = None,
    ) -> None:
        # Real objects
        self.party: List[Any] = list(party)
        self.enemies: List[Any] = list(enemies)

        # Flags
        if flags is None:
            self.flags = BattleFlags()
        elif isinstance(flags, BattleFlags):
            self.flags = flags
        else:
            # Allow partial dicts like {"is_boss": True}
            self.flags = BattleFlags(**flags)

        # Lookup tables
        self._id_to_ref: Dict[str, CombatantRef] = {}
        self._build_id_map()

        # Battle-local logs (consumed at BattleOutcome time)
        self.loot_log: List[Dict[str, Any]] = []  # e.g. {"enemy_id": "...", "item_id": "...", "qty": 1}
        self.xp_log: List[Dict[str, Any]] = []    # e.g. {"source_enemy_id": "...", "amount": 32}

        # Counters & snapshot-ish fields
        self.turn_count: int = 0
        self.elapsed_time_ms: int = 0  # optional; can be advanced by the main loop

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _build_id_map(self) -> None:
        """
        Builds a stable ID -> CombatantRef mapping.

        Strategy:
            - If an object has .id, we use that.
            - Else, we synthesize IDs like "party_0", "enemy_1".
        """
        self._id_to_ref.clear()

        # Party
        for idx, obj in enumerate(self.party):
            cid = getattr(obj, "id", None)
            if cid is None:
                cid = f"party_{idx}"
            self._id_to_ref[cid] = CombatantRef(id=cid, side="party", obj=obj)

        # Enemies
        for idx, obj in enumerate(self.enemies):
            cid = getattr(obj, "id", None)
            if cid is None:
                cid = f"enemy_{idx}"
            self._id_to_ref[cid] = CombatantRef(id=cid, side="enemy", obj=obj)

    # --------------------------------------------------------------------- #
    # Public accessors
    # --------------------------------------------------------------------- #
    def get_id_for_obj(self, obj: Any) -> str:
        """
        Given a combatant object, return its stable combatant_id as
        tracked by this session. Raises KeyError if not found.
        """
        for cid, ref in self._id_to_ref.items():
            if ref.obj is obj:
                return cid
        raise KeyError(f"Object {obj!r} is not registered in this BattleSession.")

    def get_combatant(self, combatant_id: str) -> Any:
        """Return the underlying combatant object for a given ID."""
        ref = self._id_to_ref.get(combatant_id)
        if ref is None:
            raise KeyError(f"Unknown combatant_id: {combatant_id!r}")
        return ref.obj

    def get_side(self, combatant_id: str) -> str:
        """Return which side ('party' or 'enemy') a combatant belongs to."""
        ref = self._id_to_ref.get(combatant_id)
        if ref is None:
            raise KeyError(f"Unknown combatant_id: {combatant_id!r}")
        return ref.side

    def iter_all_combatants(self, *, alive_only: bool = False):
        """
        Iterate over all combatant objects.
        If alive_only=True, filters out KOs.
        """
        for ref in self._id_to_ref.values():
            obj = ref.obj
            if not alive_only or not self._is_ko(obj):
                yield obj

    def iter_party(self, *, alive_only: bool = False):
        for obj in self.party:
            if not alive_only or not self._is_ko(obj):
                yield obj

    def iter_enemies(self, *, alive_only: bool = False):
        for obj in self.enemies:
            if not alive_only or not self._is_ko(obj):
                yield obj

    # --------------------------------------------------------------------- #
    # KO / victory / defeat helpers
    # --------------------------------------------------------------------- #

    def _is_ko(self, combatant: Any) -> bool:
        if hasattr(combatant, "is_ko"):
            return bool(getattr(combatant, "is_ko"))
        if hasattr(combatant, "hp"):
            return getattr(combatant, "hp") <= 0
        return False

    def is_party_defeated(self) -> bool:
        """True if all party members are KO."""
        return all(self._is_ko(c) for c in self.party)

    def is_enemy_defeated(self) -> bool:
        """True if all enemies are KO."""
        # An empty enemy list can be treated as 'defeated' as well.
        return len(self.enemies) == 0 or all(self._is_ko(c) for c in self.enemies)

    def is_battle_over(self) -> bool:
        """Simple victory/defeat check. More nuance will live in ActionMapper."""
        return self.is_party_defeated() or self.is_enemy_defeated()

    def check_battle_outcome(self) -> str:
        """
        Return a simple outcome string:

            - "ongoing"
            - "victory"  (enemies defeated)
            - "defeat"   (party defeated)

        More nuanced logic (phases, scripted fails, etc.) can layer
        on top of this in ActionMapper / Runtime.
        """
        party_defeated = self.is_party_defeated()
        enemy_defeated = self.is_enemy_defeated()

        if party_defeated and not enemy_defeated:
            return "defeat"
        if enemy_defeated and not party_defeated:
            return "victory"
        if enemy_defeated and party_defeated:
            # Edge-case: mutual destruction – owner can interpret.
            return "victory"

        return "ongoing"

    # --------------------------------------------------------------------- #
    # Action application helpers (ActionResult → world state)
    # --------------------------------------------------------------------- #

    def apply_action_result(self, result: "ActionResult") -> None:
        """
        Apply an ActionResult to the underlying combatant objects.

        This does NOT trigger FX; it only mutates HP/MP/status/etc.
        In Forge XVII.13, this will be used in limited, test-scoped
        paths; the legacy controller remains authoritative for now.
        """
        # Local import to avoid circular import at module load time
        from engine.battle.action_resolver import TargetResult  # type: ignore

        # HP / MP deltas per target
        for t in result.targets:
            if not isinstance(t, TargetResult):
                continue

            try:
                combatant = self.get_combatant(t.target_id)
            except KeyError:
                # If we can't find the target, skip silently – this is a
                # data issue, not a runtime crash.
                continue

            # Apply HP delta (clamped) — use combatant mutation hook if available
            if hasattr(combatant, "hp"):
                cur_hp = int(getattr(combatant, "hp", 0))
                pre_hp = cur_hp  # <-- ADD THIS
                new_hp = cur_hp + int(t.hp_delta)

                max_hp = getattr(combatant, "max_hp", None)
                if max_hp is not None:
                    new_hp = max(0, min(int(max_hp), new_hp))
                else:
                    new_hp = max(0, new_hp)

                if hasattr(combatant, "set_hp"):
                    combatant.set_hp(new_hp)
                else:
                    combatant.hp = new_hp
                # -----------------------------
                # BattleGains: enemy defeat (alive -> dead)
                # -----------------------------
                try:
                    gains = getattr(self, "gains", None)
                    if gains is not None:
                        was_alive = pre_hp > 0
                        is_dead = new_hp <= 0

                        # Prefer explicit marker if present; otherwise fall back to membership check.
                        is_enemy = bool(getattr(combatant, "is_enemy", False))
                        if not is_enemy:
                            # If your session stores enemies list, this is safe and simple:
                            is_enemy = combatant in self.enemies

                        if was_alive and is_dead and is_enemy:
                            gains.mark_enemy_defeated(getattr(combatant, "id", None) or str(getattr(combatant, "name", "enemy")))
                except Exception:
                    pass

            # Apply MP delta (clamped)
            if hasattr(combatant, "mp"):
                new_mp = getattr(combatant, "mp", 0) + int(t.mp_delta)
                max_mp = getattr(combatant, "max_mp", None)
                if max_mp is not None:
                    new_mp = max(0, min(int(max_mp), new_mp))
                combatant.mp = new_mp
            # Apply status changes (status_applied)
            status_mgr = getattr(combatant, "status", None)
            applied = getattr(t, "status_applied", None) or []
            if status_mgr is not None and applied:
                from engine.battle.skills.statuses import make_frostbite_basic, make_defend_basic

                for sid in applied:
                    if sid == "frostbite_1":
                        # Minimal viable context:
                        # - target is the combatant receiving the status
                        # - user: fall back to target for now (we'll improve source later)
                        # - battle_state: use the session as the context object
                        effect = make_frostbite_basic(combatant, combatant, self)
                        status_mgr.add(effect)
                    elif sid == "defend_1":
                        effect = make_defend_basic(combatant, combatant, self)
                        status_mgr.add(effect)
            # Apply status removals (status_removed)
            removed = getattr(t, "status_removed", None) or []
            if status_mgr is not None and removed:
                # Try common containers on the status manager
                for sid in removed:
                    # If the manager has a dedicated remover, prefer it
                    if hasattr(status_mgr, "remove_by_id"):
                        status_mgr.remove_by_id(sid)
                        continue

                    # Otherwise, search known effect containers
                    for attr in ("effects", "_effects", "active", "_active"):
                        effs = getattr(status_mgr, attr, None)
                        if not effs:
                            continue

                        # list-like
                        if isinstance(effs, list):
                            for i in range(len(effs) - 1, -1, -1):
                                eff = effs[i]
                                if getattr(eff, "id", None) == sid:
                                    effs.pop(i)

                        # set-like
                        elif isinstance(effs, set):
                            to_remove = None
                            for eff in effs:
                                if getattr(eff, "id", None) == sid:
                                    to_remove = eff
                                    break
                            if to_remove is not None:
                                effs.discard(to_remove)
        # -----------------------------
        # BattleGains: item consumption (explicit only; once per resolved action)
        # -----------------------------
        gains = getattr(self, "gains", None)
        if gains is not None:
            try:
                consumed_items = getattr(result, "consumed_items", None) or []
                if consumed_items and getattr(result, "success", True):
                    for item_id, qty in consumed_items:
                        gains.consume_item(str(item_id), int(qty))
            except Exception:
                pass

        # Later we can also use result.xp_events / loot_events to fill
        # self.xp_log / self.loot_log, but that lives in a future forge.

    # --------------------------------------------------------------------- #
    # Logging helpers (XP & loot)
    # --------------------------------------------------------------------- #

    def log_loot(self, *, enemy_id: str, item_id: str, qty: int = 1) -> None:
        """
        Record a loot event. This does NOT touch global inventory;
        OutcomeBuilder (meta outcome) + Ledger commit step (later).
        """
        self.loot_log.append(
            {
                "enemy_id": enemy_id,
                "item_id": item_id,
                "qty": qty,
            }
        )

    def log_xp(self, *, source_enemy_id: str, amount: int) -> None:
        """
        Record an XP gain event generated by a kill.
        The actual distribution to party members happens during POST_RESOLVE.
        """
        self.xp_log.append(
            {
                "source_enemy_id": source_enemy_id,
                "amount": amount,
            }
        )
