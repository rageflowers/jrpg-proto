from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from engine.overworld.encounters.spec import EncounterProfile, EncounterEntry


@dataclass(frozen=True)
class BattleRequest:
    """Minimal, future-proof battle request emitted by the overworld."""
    region_id: str
    encounter_id: str
    enemy_party_id: str
    seed: int
    backdrop_id: str | None = None


class EncounterController:
    """Tiny deterministic encounter controller.

    Distance-based model:
      - accumulate moved pixels while moving
      - every time meter crosses step_px, roll against chance
      - on trigger: choose a weighted entry from profile.table

    All randomness comes from the provided rng (usually RegionRuntime.rng).
    """

    def __init__(self, *, profile: EncounterProfile, rng) -> None:
        self.profile = profile
        self._rng = rng
        self._meter_px: float = 0.0
        self._cooldown_left_px: float = 0.0
        self._telegraph: float = 0.0
        self._threat: float = 0.0

    @property
    def meter_px(self) -> float:
        return self._meter_px

    @property
    def cooldown_left_px(self) -> float:
        return self._cooldown_left_px

    @property
    def telegraph(self) -> float:
        threshold = max(0.01, float(getattr(self.profile.rules, "threat_threshold", 1.0)))
        return min(1.0, self._threat / threshold)

    def reset(self) -> None:
        self._meter_px = 0.0
        self._cooldown_left_px = 0.0
        self._threat = 0.0
        self._frozen = False

    def freeze(self) -> None:
        """Freeze encounter meter at max until reset()."""
        self._frozen = True
        # Pin threat high so UI telegraph stays at 1.0
        threshold = float(getattr(self.profile.rules, "threat_threshold", 1.0))
        threshold = max(0.01, threshold)
        self._threat = max(self._threat, threshold)
        self._meter_px = 0.0

    def _gating_allows(self, flags: set[str]) -> bool:
        g = self.profile.gating
        if g.requires_flags_all:
            for f in g.requires_flags_all:
                if f not in flags:
                    return False
        if g.forbids_flags_any:
            for f in g.forbids_flags_any:
                if f in flags:
                    return False
        return True

    def _choose_weighted(self, entries: Sequence[EncounterEntry]) -> EncounterEntry:
        total = 0
        for e in entries:
            w = int(getattr(e, "weight", 1) or 1)
            if w > 0:
                total += w

        # Fail-soft: if the table is empty or all weights invalid, just pick first.
        if total <= 0:
            return entries[0]

        roll = self._rng.randrange(total)
        acc = 0
        for e in entries:
            w = int(getattr(e, "weight", 1) or 1)
            if w <= 0:
                continue
            acc += w
            if roll < acc:
                return e

        return entries[-1]

    def update(
        self,
        *,
        region_id: str,
        moved_px: float,
        flags: set[str],
        debug: bool = False,
    ) -> Optional[BattleRequest]:
        """Step-based stochastic threat accumulation.

        Every `step_px` of travel:
        - add a random increment to `_threat` (always increases)
        - if `_threat` >= threshold, trigger encounter

        Deterministic: uses self._rng only.
        """
        if getattr(self, "_frozen", False):
            return None
        if moved_px <= 0.0:
            return None

        if not self._gating_allows(flags):
            return None

        rules = self.profile.rules
        step_px = max(1.0, float(rules.step_px))
        cooldown_px = float(getattr(rules, "cooldown_px", 0.0) or 0.0)

        # Cooldown consumes movement first.
        if self._cooldown_left_px > 0.0:
            self._cooldown_left_px = max(0.0, self._cooldown_left_px - moved_px)
            return None

        self._meter_px += moved_px

        # Threat model parameters (authorable later; good defaults now)
        threshold = float(getattr(rules, "threat_threshold", 1.0))
        threshold = max(0.01, threshold)

        # Base increment per step (small drip)
        base_add = float(getattr(rules, "threat_base_add", 0.10))
        base_add = max(0.0, base_add)

        # Random add range per step (spiky potential)
        # e.g. 0.00..0.35 means most steps add a little, sometimes a lot.
        rand_lo = float(getattr(rules, "threat_rand_lo", 0.00))
        rand_hi = float(getattr(rules, "threat_rand_hi", 0.35))
        if rand_hi < rand_lo:
            rand_lo, rand_hi = rand_hi, rand_lo

        # Optional: rare spike chance that adds an extra chunk
        spike_chance = float(getattr(rules, "threat_spike_chance", 0.08))
        spike_add_lo = float(getattr(rules, "threat_spike_add_lo", 0.20))
        spike_add_hi = float(getattr(rules, "threat_spike_add_hi", 0.60))
        if spike_add_hi < spike_add_lo:
            spike_add_lo, spike_add_hi = spike_add_hi, spike_add_lo

        # Process one or more steps (rare multiple steps in one frame).
        while self._meter_px >= step_px:
            self._meter_px -= step_px

            # Stochastic accumulation: always increases.
            add = base_add + float(self._rng.uniform(rand_lo, rand_hi))

            # Occasional spike
            if spike_chance > 0.0 and float(self._rng.random()) < spike_chance:
                add += float(self._rng.uniform(spike_add_lo, spike_add_hi))

            self._threat += add

            if debug:
                tele = min(1.0, self._threat / threshold)
                print(
                    f"[ENCOUNTER] profile={self.profile.id!r} add={add:.3f} threat={self._threat:.3f}/{threshold:.3f} tele={tele:.3f}"
                )

            if self._threat < threshold:
                continue

            # Trigger!
            if not self.profile.table:
                if debug:
                    print(f"[ENCOUNTER] profile {self.profile.id!r} has empty table; ignoring trigger")
                # If table is empty, don't keep threat pinned forever.
                self._threat = 0.0
                return None

            entry = self._choose_weighted(self.profile.table)

            seed = int(self._rng.randrange(1_000_000_000))
            self._cooldown_left_px = max(0.0, cooldown_px)

            # Reset threat for the next cycle (keep HUD at max via pending_battle if you want dire display)
            self.freeze()

            return BattleRequest(
                region_id=region_id,
                encounter_id=self.profile.id,
                enemy_party_id=entry.enemy_party_id,
                seed=seed,
                backdrop_id=getattr(self.profile, "backdrop_id", None),
            )

        return None

