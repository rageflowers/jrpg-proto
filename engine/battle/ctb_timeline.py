from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Iterable, Any


# --------------------------------------------------------------------------- #
#  ReadyBatch: a simple, clean container for "who is ready this tick?"
# --------------------------------------------------------------------------- #

@dataclass
class ReadyBatch:
    def __init__(self, combatant_ids):
        # Store the CTB-ready combatant IDs as a list of strings
        self.combatant_ids = list(combatant_ids)

    def __bool__(self):
        # So `if batch:` works as expected
        return bool(self.combatant_ids)

    # XVII.2 — compatibility shim for legacy controller
    def __iter__(self):
        """
        Iterate over combatant objects so legacy
        controller.begin_player_turn() can treat
        this like the old ready list.
        """
        return iter(self.combatant_ids)

# --------------------------------------------------------------------------- #
#  CTBTimeline: owns all gauges, nothing else
# --------------------------------------------------------------------------- #

class CTBTimeline:
    """
    CTBTimeline is responsible for:
        - owning the CTB gauge for each combatant
        - incrementing gauges each tick
        - detecting who reaches readiness (>= 100)
        - producing a ReadyBatch when actors are ready

    It does NOT:
        - resolve commands
        - apply damage
        - mutate the BattleSession
        - run turn flow
    """

    READY_THRESHOLD = 100.0

    def __init__(self, session):
        self.session = session

        # Mapping: combatant_id -> gauge value (0 to 100+)
        self.gauges: Dict[str, float] = {}

        # Build initial gauges for alive combatants
        for obj in session.iter_all_combatants(alive_only=True):
            cid = getattr(obj, "id", None)
            if cid is None:
                raise ValueError(
                    f"Combatant object {obj!r} must have an 'id' attribute for CTB."
                )
            self.gauges[cid] = 0.0

        # Timeline active flag (ActionMapper will freeze/unfreeze)
        self.paused: bool = False

    # ------------------------------------------------------------------ #
    #  Control methods
    # ------------------------------------------------------------------ #

    def pause(self) -> None:
        """Freeze CTB advancement until explicitly resumed."""
        self.paused = True

    def resume(self) -> None:
        """Allow gauges to increment again."""
        self.paused = False

    # ------------------------------------------------------------------ #
    #  Main update / tick
    # ------------------------------------------------------------------ #

    def update(self, dt: float) -> Optional[ReadyBatch]:
        """
        Advance CTB gauges by dt (seconds or ms—your game loop defines scale).
        If paused, gauges do not advance.

        Returns:
            ReadyBatch if >=1 actor hits readiness,
            else None.
        """
        if self.paused:
            return None

        ready_list: List[str] = []

        # Increment gauges
        for cid, gauge in self.gauges.items():
            # Skip KO'd actors (their gauges stay frozen)
            obj = self.session.get_combatant(cid)
            if self.session._is_ko(obj):
                continue

            # For now: placeholder flat increment
            # Later, speed-based increments will plug in here.
            gauge += dt * 20.0  # arbitrary placeholder rate
            max_gauge = self.READY_THRESHOLD * 2.0
            if gauge >= self.READY_THRESHOLD:
                gauge = self.READY_THRESHOLD
            self.gauges[cid] = gauge

            # Check readiness
            if gauge >= self.READY_THRESHOLD:
                ready_list.append(cid)

        if ready_list:
            return ReadyBatch(combatant_ids=ready_list)

        return None

    # ------------------------------------------------------------------ #
    #  Reset helpers
    # ------------------------------------------------------------------ #

    def reset_gauge(self, combatant_id: str) -> None:
        """Called by ActionMapper after an actor takes their turn."""
        if combatant_id in self.gauges:
            self.gauges[combatant_id] = 0.0

    # ------------------------------------------------------------------ #
    #  Maintenance (when someone dies, leaves, or gets revived)
    # ------------------------------------------------------------------ #

    def remove_combatant(self, combatant_id: str) -> None:
        """
        Called when an actor permanently leaves the field
        (e.g., unsummon, phase swap out, etc.).
        """
        self.gauges.pop(combatant_id, None)

    def add_combatant(self, combatant_id: str) -> None:
        """
        Called when a new actor joins the field.
        (Summon, phase swap in, etc.)
        """
        if combatant_id not in self.gauges:
            self.gauges[combatant_id] = 0.0

    def remove_node(self, cid: str) -> None:
        """
        KO-focused helper used by BattleRuntime.
        Removes the combatant from CTB so their gauge no longer advances.
        """
        self.remove_combatant(cid)

    def revive_node(self, cid: str) -> None:
        """
        Re-insert a combatant into CTB after a Raise / revive.
        Their gauge starts at 0 so they re-enter turn order cleanly.
        """
        self.add_combatant(cid)
    # ------------------------------------------------------------------ #
    #  HUD helpers for CTB gauges
    # ------------------------------------------------------------------ #

    def get_gauge_ratio(self, combatant_id: str) -> float:
        """
        Return this actor's gauge as a 0.0–1.0 ratio for HUD purposes.
        """
        if combatant_id not in self.gauges:
            return 0.0

        raw = float(self.gauges.get(combatant_id, 0.0))
        ratio = raw / float(self.READY_THRESHOLD)
        # clamp into [0, 1]
        return max(0.0, min(1.0, ratio))

    def get_commit_threshold(self) -> float:
        """
        Return the commit threshold as a HUD ratio.
        For now, simply 50% of the READY_THRESHOLD.
        """
        return 0.5
