from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Tuple, Optional

from .actor import StageActor
from .tween import ease_linear, ease_out_quad, EaseFunc


class Action:
    """Base class for all time-based actions.

    update(dt) should return True when the action is finished.
    """

    def update(self, dt: float) -> bool:
        raise NotImplementedError


# ----------------------------------------------------------------------
# Simple building blocks
# ----------------------------------------------------------------------
@dataclass
class Wait(Action):
    duration: float
    elapsed: float = 0.0

    def update(self, dt: float) -> bool:
        self.elapsed += dt
        return self.elapsed >= self.duration


@dataclass
class MoveTo(Action):
    """Move an actor's pos to an absolute (x, y) over a duration."""

    actor: StageActor
    target_pos: Tuple[int, int]
    duration: float
    ease: EaseFunc = ease_out_quad

    # internal
    _start_pos: Optional[Tuple[int, int]] = None
    _elapsed: float = 0.0

    def update(self, dt: float) -> bool:
        if self._start_pos is None:
            self._start_pos = self.actor.pos

        self._elapsed += dt
        t = max(0.0, min(1.0, self._elapsed / self.duration))
        eased = self.ease(t)

        sx, sy = self._start_pos
        ex, ey = self.target_pos
        nx = int(sx + (ex - sx) * eased)
        ny = int(sy + (ey - sy) * eased)
        self.actor.pos = (nx, ny)

        return self._elapsed >= self.duration


@dataclass
class MoveBy(Action):
    """Move an actor by a relative (dx, dy) over a duration.

    This is useful for small nudges, recoils, hops, etc., where you don't
    care about the absolute final coordinate – just the offset.
    """

    actor: StageActor
    delta: Tuple[int, int]
    duration: float
    ease: EaseFunc = ease_out_quad

    # internal
    _start_pos: Optional[Tuple[int, int]] = None
    _elapsed: float = 0.0

    def update(self, dt: float) -> bool:
        if self._start_pos is None:
            self._start_pos = self.actor.pos

        self._elapsed += dt
        t = max(0.0, min(1.0, self._elapsed / self.duration))
        eased = self.ease(t)

        sx, sy = self._start_pos
        dx, dy = self.delta
        nx = int(sx + dx * eased)
        ny = int(sy + dy * eased)
        self.actor.pos = (nx, ny)

        return self._elapsed >= self.duration


# ----------------------------------------------------------------------
# Combinators
# ----------------------------------------------------------------------
@dataclass
class Sequence(Action):
    """Run actions one after another."""

    actions: List[Action]
    _index: int = 0

    def update(self, dt: float) -> bool:
        if self._index >= len(self.actions):
            return True

        current = self.actions[self._index]
        done = current.update(dt)
        if done:
            self._index += 1

        return self._index >= len(self.actions)


@dataclass
class Parallel(Action):
    """Run multiple actions at the same time.

    Completes when all child actions have finished.
    """

    actions: List[Action]

    def update(self, dt: float) -> bool:
        if not self.actions:
            return True

        remaining: List[Action] = []
        for a in self.actions:
            done = a.update(dt)
            if not done:
                remaining.append(a)

        self.actions = remaining
        return not self.actions


@dataclass
class Call(Action):
    """Invoke an arbitrary callback exactly once.

    Great for:
      - applying damage/heal at the impact frame
      - triggering sounds
      - starting/stopping camera shakes
      - spawning VFX that aren't themselves Actions
    """

    func: Callable[[], None]
    _done: bool = False

    def update(self, dt: float) -> bool:
        if not self._done:
            self.func()
            self._done = True
        return True


# ----------------------------------------------------------------------
# Timeline: runs many Actions in parallel at the scene level
# ----------------------------------------------------------------------
@dataclass
class Timeline:
    """Simple manager for many actions running in parallel."""

    actions: List[Action] = field(default_factory=list)

    def add(self, action: Action) -> None:
        self.actions.append(action)

    def update(self, dt: float) -> None:
        if not self.actions:
            return

        remaining: List[Action] = []
        for action in self.actions:
            done = action.update(dt)
            if not done:
                remaining.append(action)

        self.actions = remaining

    def is_busy(self) -> bool:
        return bool(self.actions)
