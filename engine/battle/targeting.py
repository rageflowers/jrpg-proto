# engine/battle/targeting.py (new unified cursor section)

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Literal, Tuple
import math

Direction = Literal["up", "down", "left", "right"]


@dataclass(frozen=True)
class TargetCandidate:
    combatant_id: str
    side: Literal["party", "enemy"]
    pos: Tuple[int, int]  # (x, y) anchor for cursor movement
    alive: bool = True

@dataclass
class UnifiedTargetCursor:
    candidates: List[TargetCandidate]
    current_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.candidates:
            self.current_id = None
            return
        if self.current_id is None or not any(c.combatant_id == self.current_id for c in self.candidates):
            # Default to first alive, else first
            alive = next((c for c in self.candidates if c.alive), None)
            self.current_id = (alive.combatant_id if alive else self.candidates[0].combatant_id)

    def current(self) -> Optional[TargetCandidate]:
        if self.current_id is None:
            return None
        return next((c for c in self.candidates if c.combatant_id == self.current_id), None)

    def move(self, direction: Direction) -> Optional[str]:
        cur = self.current()
        if cur is None:
            return None

        cx, cy = cur.pos
        best_id: Optional[str] = None
        best_score = float("inf")

        # Small deadzone to prevent jitter when x/y is nearly equal
        dead = 2

        for cand in self.candidates:
            if cand.combatant_id == cur.combatant_id:
                continue
            if not cand.alive:
                continue

            x, y = cand.pos
            dx = x - cx
            dy = y - cy

            # Directional filter
            if direction == "right" and dx <= dead:
                continue
            if direction == "left" and dx >= -dead:
                continue
            if direction == "down" and dy <= dead:
                continue
            if direction == "up" and dy >= -dead:
                continue

            dist = math.hypot(dx, dy)

            # Penalize off-axis movement (so Right prefers mostly-horizontal moves)
            if direction in ("left", "right"):
                off_axis = abs(dy) * 1.25
            else:
                off_axis = abs(dx) * 1.25

            score = dist + off_axis

            if score < best_score:
                best_score = score
                best_id = cand.combatant_id

        if best_id is not None:
            self.current_id = best_id
        return self.current_id

def build_candidates_from_combatants(party, enemies) -> List[TargetCandidate]:
    """
    Build a unified candidate list for cursor targeting using combatant sprite anchors.

    Assumes combatants have:
      - .id (preferred) or .name fallback
      - .sprite with .x/.y
      - .alive (optional; defaults True)
    """
    candidates: List[TargetCandidate] = []

    for c in party:
        cid = getattr(c, "id", getattr(c, "name", "unknown_party"))
        spr = getattr(c, "sprite", None)
        if spr is None:
            continue
        alive = bool(getattr(c, "alive", True))
        candidates.append(
            TargetCandidate(
                combatant_id=str(cid),
                side="party",
                pos=(int(spr.x), int(spr.y)),
                alive=alive,
            )
        )

    for c in enemies:
        cid = getattr(c, "id", getattr(c, "name", "unknown_enemy"))
        spr = getattr(c, "sprite", None)
        if spr is None:
            continue
        alive = bool(getattr(c, "alive", True))
        candidates.append(
            TargetCandidate(
                combatant_id=str(cid),
                side="enemy",
                pos=(int(spr.x), int(spr.y)),
                alive=alive,
            )
        )

    return candidates
