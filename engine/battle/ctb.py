# engine/battle/ctb.py
#
# Forge XVI.7 — CTB Battle Clock System
#
# This system manages:
#   - A single battle clock T
#   - Per-actor turn slots (last_turn_time, next_turn_time)
#   - Gauge ratio = (T - last) / (next - last)
#   - Optional "ready batch" when actors reach next_turn_time
#
# Gauges DO NOT move when CTB is paused (controller calls pause/resume).
# The 50% midpoint is purely visual (HUD only).

from __future__ import annotations
from typing import Any, List, Dict, Optional
import math


# purely visual midpoint marker (HUD can read this)
CTB_COMMIT_THRESHOLD = 0.5


class ActorTurnState:
    """Tracks timing info for one actor in the CTB system."""

    def __init__(self, actor: Any, start_time: float):
        self.actor = actor
        self.last_turn_time = start_time
        self.next_turn_time = start_time  # will be scheduled immediately


class CTBSystem:
    """
    CTB battle-clock manager.

    Responsibilities:
      - Maintain a global time T that advances only when running == True.
      - Maintain per-actor turn times.
      - Compute gauge ratios for HUD.
      - Optionally expose "ready batches" when actors reach next_turn_time.
      - Allow controller to pause/resume CTB progression.
    """

    def __init__(self, party: List[Any], enemies: List[Any], *, base_delay: float = 3.0):
        """
        base_delay:
            The base "turn cost" before dividing by effective SPD.
            Higher SPD => shorter Δturn_time.
        """
        self.party = list(party)
        self.enemies = list(enemies)
        self.actors = self.party + self.enemies

        self.time: float = 0.0          # battle clock
        self.running: bool = True       # if False, gauges freeze
        self.base_delay = float(base_delay)

        # Per-actor timing records
        self.states: Dict[Any, ActorTurnState] = {}
        for actor in self.actors:
            st = ActorTurnState(actor, self.time)
            self.states[actor] = st

        # Initial scheduling: everyone gets a first "next turn"
        for actor in self.actors:
            self.schedule_next_turn(actor)

    # ------------------------------------------------------------
    # Time & scheduling
    # ------------------------------------------------------------
    def schedule_next_turn(self, actor: Any):
        """
        Schedule this actor's next turn based on:
            next_turn_time = last_turn_time + (base_delay / SPD)
        """
        st = self.states.get(actor)
        if st is None:
            return

        # Pull effective SPD (includes status modifiers)
        spd = float(getattr(actor, "spd", 0.0))
        status_mgr = getattr(actor, "status", None)
        spd_mult = 1.0
        spd_add = 0.0

        if status_mgr and hasattr(status_mgr, "get_stat_modifiers"):
            mods = status_mgr.get_stat_modifiers()
            spd_mult = float(mods.get("spd_mult", 1.0))
            spd_add = float(mods.get("spd_add", 0.0))

        eff_spd = max(0.0, spd * spd_mult + spd_add)

        # Prevent division by zero — immobile characters have a huge delay.
        if eff_spd <= 0:
            eff_spd = 0.000001

        delay = self.base_delay / eff_spd
        st.last_turn_time = st.next_turn_time
        st.next_turn_time = st.last_turn_time + delay

    # ------------------------------------------------------------
    # Gauge ratio: purely visual
    # ------------------------------------------------------------
    def get_gauge(self, actor: Any) -> float:
        """
        Returns a normalized 0.0–1.0 progress toward the actor's next turn.
        """
        st = self.states.get(actor)
        if not st:
            return 0.0

        last_t = st.last_turn_time
        next_t = st.next_turn_time

        if next_t <= last_t:
            return 1.0

        ratio = (self.time - last_t) / (next_t - last_t)
        return max(0.0, min(1.0, ratio))

    def get_commit_threshold(self) -> float:
        """HUD convenience (visual midpoint)."""
        return CTB_COMMIT_THRESHOLD

    # ------------------------------------------------------------
    # CTB UPDATE LOOP
    # ------------------------------------------------------------
    def update(self, dt: float) -> Optional[List[Any]]:
        """
        Advance the battle clock T if running is True.

        Returns:
            ready_batch  -> list of actors whose turn arrives this tick
            OR
            None         -> no batch yet (time still advancing)

        For now, the battle controller may ignore ready_batch until we
        fully migrate turn flow to CTB.
        """
        if not self.running or dt <= 0.0:
            return None

        # Identify the next moment when ANY living actor gets a turn.
        next_times: List[float] = []
        for st in self.states.values():
            actor = st.actor
            if getattr(actor, "alive", True):
                next_times.append(st.next_turn_time)

        if not next_times:
            return None  # no living actors?

        t_min = min(next_times)

        # If T + dt doesn't reach the next turn moment, simply advance time.
        if self.time + dt < t_min:
            self.time += dt
            return None

        # Otherwise, we cross a turn boundary:
        #   1) Advance T exactly to t_min
        #   2) Collect all actors whose next_turn_time == t_min
        self.time = t_min

        ready_batch: List[Any] = []
        for actor, st in self.states.items():
            if not getattr(actor, "alive", True):
                continue

            # tiny epsilon to avoid float friction
            if math.isclose(st.next_turn_time, t_min, abs_tol=1e-6):
                ready_batch.append(actor)

        # NOTE: We do NOT auto-pause here; the controller decides
        # when to pause()/resume() based on its own state.
        return ready_batch

    # ------------------------------------------------------------
    # Controller-facing controls
    # ------------------------------------------------------------
    def pause(self):
        """Freeze CTB progression (called when waiting for player input)."""
        self.running = False

    def resume(self):
        """Unfreeze CTB progression (called after actions are resolved)."""
        self.running = True

    def reset_gauge(self, actor: Any):
        """
        Reset this actor's gauge as if they have just acted *now*.

        This:
          - sets last_turn_time and next_turn_time to the current battle time
          - then schedules their next turn forward from now.

        Used by the controller after an actor finishes an action.
        """
        st = self.states.get(actor)
        if st is None:
            return

        st.last_turn_time = self.time
        st.next_turn_time = self.time
        self.schedule_next_turn(actor)
