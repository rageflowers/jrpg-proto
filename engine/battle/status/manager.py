from __future__ import annotations

from typing import Any, List, Tuple
from game.debug.debug_logger import log as battle_log
from engine.battle.status.effects import DotStatus
from engine.battle.status.status_events import StatusEvent, ApplyStatusEvent

class StatusManager:
    """
    Holds and manages all StatusEffect objects applied to a single combatant.

    This manager is aligned with engine.battle.status.effects.StatusEffect,
    where the hooks all receive (owner, context, ...) rather than inferring
    the owner internally.
    """

    def __init__(self, owner: Any):
        self.owner = owner
        self.effects: List[Any] = []   # List[StatusEffect]

    # --------------------------------------------------------------
    # Basic add/remove
    # --------------------------------------------------------------
    def add(self, effect: Any, context: Any | None = None) -> None:
        """
        Attach a new StatusEffect to the owner.

        If the incoming effect is marked non-stackable (has stackable=False),
        any existing effects with the same .id will be removed first.

        Additionally:
          - elemental shield statuses (those tagged 'elemental_shield')
            are mutually exclusive: applying a new one will remove any
            existing elemental shields on this owner, regardless of id.
          - statuses that define a .max_stacks attribute will be capped
            so that at most .max_stacks instances with the same .id
            are present at any time.
        """
        effect_id = getattr(effect, "id", None)
        stackable = getattr(effect, "stackable", False)
        new_tags = getattr(effect, "tags", None) or set()
        max_stacks = getattr(effect, "max_stacks", 0)

        # ----------------------------------------------------------
        # Elemental shields: only one at a time
        # ----------------------------------------------------------
        if "elemental_shield" in new_tags:
            remaining: list[Any] = []
            for existing in self.effects:
                existing_tags = getattr(existing, "tags", None) or set()
                if "elemental_shield" in existing_tags:
                    # Replacing an existing shield – fire its expire hook
                    existing.on_expire(self.owner, context)
                else:
                    remaining.append(existing)
            self.effects = remaining

        # ----------------------------------------------------------
        # Generic stacking limits for statuses that declare max_stacks
        # (Bleed/Burn DoTs, etc.)
        # ----------------------------------------------------------
        if effect_id is not None and max_stacks > 0:
            same_id: list[Any] = []
            others: list[Any] = []
            for existing in self.effects:
                if getattr(existing, "id", None) == effect_id:
                    same_id.append(existing)
                else:
                    others.append(existing)

            if len(same_id) >= max_stacks:
                # We need to free space for this new instance.
                # Remove as many oldest instances as necessary so we keep
                # at most (max_stacks - 1) existing, plus this new one.
                to_remove_count = len(same_id) - (max_stacks - 1)
                if to_remove_count < 1:
                    to_remove_count = 1

                to_remove = same_id[:to_remove_count]
                to_keep = same_id[to_remove_count:]

                for eff in to_remove:
                    eff.on_expire(self.owner, context)

                self.effects = others + to_keep

        # ----------------------------------------------------------
        # Non-stackable by id: replace same-id effects
        # (e.g. Poison, or other explicit non-stack statuses)
        # ----------------------------------------------------------
        if effect_id is not None and not stackable:
            remaining = []
            for existing in self.effects:
                if getattr(existing, "id", None) == effect_id:
                    existing.on_expire(self.owner, context)
                else:
                    remaining.append(existing)
            self.effects = remaining

        # ----------------------------------------------------------
        # Attach the new effect
        # ----------------------------------------------------------
        effect._skip_next_turn_end_decrement = True
        self.effects.append(effect)
        dbg = getattr(context, "debug", None)
        if dbg is not None and hasattr(dbg, "runtime"):
            dbg.runtime(
                f"[ADD] {getattr(effect,'id','?')} skip={getattr(effect,'_skip_next_turn_end_decrement',None)} "
                f"dur={getattr(effect,'duration_turns',None)}"
            )
        effect.on_apply(self.owner, context)

    def remove(self, effect: Any, context: Any | None = None) -> None:
        """
        Remove a specific StatusEffect instance.

        StatusEffect API:
            on_expire(owner, context)
        """
        if effect in self.effects:
            self.effects.remove(effect)
            effect.on_expire(self.owner, context)

    def remove_by_id(self, effect_id: str, context: Any | None = None) -> None:
        """Remove every status whose .id matches effect_id."""
        remaining = []
        for eff in self.effects:
            if eff.id == effect_id:
                eff.on_expire(self.owner, context)
            else:
                remaining.append(eff)
        self.effects = remaining
    # --------------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------------
    def _log_dot_observe(self, eff: Any, context: Any | None = None) -> None:
        """
        Lightweight DoT observer.

        Called right before a status's on_turn_end() hook. If the effect looks
        like a DoT, we emit one structured line so you can see whether it is
        ABOUT to tick: who, what, how much, how long.
        """
        owner = self.owner
        owner_name = getattr(owner, "name", "<??>")
        eff_id = getattr(eff, "id", "<no-id>")
        tags = getattr(eff, "tags", None) or set()

        # Heuristic: tagged "dot" or with a per-tick field.
        is_dot_tag = "dot" in tags
        has_tick_field = any(
            hasattr(eff, attr)
            for attr in ("per_tick", "tick_amount", "damage_per_turn")
        )

        if not (is_dot_tag or has_tick_field):
            return

        # Extract best-effort tick amount
        tick_amount = None
        if hasattr(eff, "per_tick"):
            tick_amount = getattr(eff, "per_tick", None)
        elif hasattr(eff, "tick_amount"):
            tick_amount = getattr(eff, "tick_amount", None)
        elif hasattr(eff, "damage_per_turn"):
            tick_amount = getattr(eff, "damage_per_turn", None)

        # Guess what kind of DoT it is (burn/poison/bleed/etc)
        tick_kind = getattr(eff, "dot_element", None) or getattr(eff, "element", None)
        if tick_kind is None:
            for key in ("poison", "bleed", "burn", "fire", "shadow"):
                if key in tags:
                    tick_kind = key
                    break

        remaining = getattr(eff, "duration_turns", None)

        msg = (
            f"[DOT OBSERVE] owner={owner_name}, status_id={eff_id}, "
            f"kind={tick_kind}, tick={tick_amount}, remaining_turns={remaining}"
        )

        # 🔌 Preferred path: standardized BattleDebug routing
        dbg = getattr(context, "debug", None)
        if dbg is not None and hasattr(dbg, "runtime"):
            dbg.runtime(msg)
        else:
            # Fallback for non-battle contexts, still using the same logger core.
            battle_log("status", msg)

    # --------------------------------------------------------------
    # Turn-based hooks
    # --------------------------------------------------------------
    def on_turn_start(self, context: Any | None = None) -> None:
        """
        Called at the *start* of the owner's turn.

        StatusEffect API:
            on_turn_start(owner, context)
        """
        for eff in list(self.effects):
            eff.on_turn_start(self.owner, context)

        # Clean up any that expired inside on_turn_start
        self._cleanup_expired(context=context)

    def on_turn_end(self, context: Any | None = None) -> list[Any]:
        """
        Called at the *end* of the owner's turn.

        StatusEffect API:
            on_turn_end(owner, context)

        XVII.18 – Status Sanctum step B:
        - We now collect any events returned by each status's on_turn_end.
        - Legacy behavior (direct HP/MP mutation inside statuses) remains
          unchanged for now; callers still *implicitly* rely on it.
        """
        events: list[Any] = []

        for eff in list(self.effects):
            
            # DOT observer
            self._log_dot_observe(eff, context=context)

            # Call the status hook as before (this still mutates HP/MP etc.).
            result = eff.on_turn_end(self.owner, context)

            # ----------------------------------------------------------
            # Collect any events the status chooses to emit
            # ----------------------------------------------------------
            if result:
                if isinstance(result, (list, tuple)):
                    events.extend(result)
                else:
                    events.append(result)

            # ----------------------------------------------------------
            # Duration countdown (owned by the manager)
            # ----------------------------------------------------------
            skip = getattr(eff, "_skip_next_turn_end_decrement", False)

            if skip:
                # Consume the one-time protection; do NOT decrement
                eff._skip_next_turn_end_decrement = False
            else:
                eff.duration_turns -= 1

        # Clean up anything that expired during this tick.
        self._cleanup_expired(context=context)

        # XVII.18: optional debug of the collected status events.
        if events and context is not None:
            dbg = getattr(context, "debug", None)
            if dbg is not None and hasattr(dbg, "runtime"):
                owner_name = getattr(self.owner, "name", "<??>")
                dbg.runtime(
                    f"[STATUS EVENTS] on_turn_end collected {len(events)} event(s) "
                    f"for {owner_name}"
                )

        # Caller can start reading these events later.
        return events

    # --------------------------------------------------------------
    # Damage modification pipeline
    # --------------------------------------------------------------
    def apply_incoming_damage_modifiers(
        self,
        amount: int,
        *,
        element: str,
        damage_type: str,
        context: Any | None = None,
    ) -> tuple[int, int, list[StatusEvent]]:
        """
        Let all active statuses modify incoming damage.

        Returns:
            (final_amount, total_bonus_heal, retaliation_events)

        New doctrine:
            - retaliation_events must be StatusEvent objects
            - dict-shaped legacy retaliation is ignored (and logged once per event)
        """
        owner = self.owner
        bonus_heal_total = 0
        all_retaliation: list[StatusEvent] = []

        for eff in getattr(self, "effects", []):
            hook = getattr(eff, "on_before_owner_takes_damage", None)
            if hook is None:
                continue

            try:
                amount, bonus_heal, retaliation = hook(
                    owner,
                    amount,
                    element,
                    damage_type,
                    context,
                )
            except TypeError as e:
                battle_log(
                    "status",
                    f"[STATUS ERROR] {getattr(eff, 'id', '<no id>')} "
                    f"on_before_owner_takes_damage TypeError: {e}",
                )
                continue

            if bonus_heal:
                bonus_heal_total += int(bonus_heal)

            if retaliation:
                for ev in retaliation:
                    if isinstance(ev, StatusEvent):
                        all_retaliation.append(ev)
                    else:
                        # Legacy safety net: don't crash, but don't interpret here.
                        battle_log(
                            "status",
                            f"[STATUS WARN] legacy retaliation event ignored: {ev!r}",
                        )

        return amount, bonus_heal_total, all_retaliation

    # --------------------------------------------------------------
    # Housekeeping
    # --------------------------------------------------------------
    def _cleanup_expired(self, context: Any | None = None) -> None:
        remaining = []
        for eff in self.effects:
            if eff.duration_turns <= 0:
                eff.on_expire(self.owner, context)
            else:
                remaining.append(eff)
        self.effects = remaining

    # --------------------------------------------------------------
    # Aggregated stat modifiers
    # --------------------------------------------------------------
    def get_stat_modifiers(self) -> dict[str, float]:
        """
        Aggregate all stat modifiers contributed by active statuses.

        Returns a dict with keys like:
          - atk_mult, def_mult, mag_mult, mres_mult, spd_mult
          - atk_add,  def_add,  mag_add,  mres_add,  spd_add

        Multipliers default to 1.0, additive bonuses default to 0.0.
        StatusEffect.modify_stat_modifiers() can adjust these in place.
        """
        mods: dict[str, float] = {
            "atk_mult": 1.0,
            "def_mult": 1.0,
            "mag_mult": 1.0,
            "mres_mult": 1.0,
            "spd_mult": 1.0,
            "atk_add": 0.0,
            "def_add": 0.0,
            "mag_add": 0.0,
            "mres_add": 0.0,
            "spd_add": 0.0,
        }

        for eff in self.effects:
            # Only statuses that care about stats need to implement this.
            if hasattr(eff, "modify_stat_modifiers"):
                eff.modify_stat_modifiers(mods)

        return mods

    # --------------------------------------------------------------
    # Utility for debugging / HUD
    # --------------------------------------------------------------
    def get_active_ids(self) -> list[str]:
        """Return only the status IDs for debug/status-window use."""
        return [eff.id for eff in self.effects]

    def get_effects(self):
        """Direct access for iteration (for debug / HUD helpers)."""
        return list(self.effects)
