from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

import pygame


@dataclass
class CameraStep:
    """
    A single camera tween step.

    Moves the camera from (start_offset, start_zoom) to
    (target_offset, target_zoom) over `duration` seconds.
    """

    target_offset: pygame.math.Vector2
    target_zoom: float
    duration: float

    elapsed: float = 0.0
    start_offset: Optional[pygame.math.Vector2] = None
    start_zoom: Optional[float] = None

    def normalized_time(self) -> float:
        """Return progress in [0, 1] based on elapsed / duration."""
        if self.duration <= 0.0:
            return 1.0
        return max(0.0, min(1.0, self.elapsed / self.duration))


@dataclass
class CameraRig:
    """
    Smooth pan/zoom controller for cinematic camera movement.

    Responsibilities:
      - Maintain a base camera offset and zoom factor.
      - Play queued tweens (CameraStep) one after another.
      - Provide a simple helper for "basic skill cinematic" punch-ins.

    This class is presentation-only and does not know anything about
    battle logic or FX internals. FXSystem (or similar) should own an
    instance of CameraRig and consult its `offset` and `zoom` when
    drawing the scene.
    """

    offset: pygame.math.Vector2 = field(
        default_factory=lambda: pygame.math.Vector2(0, 0)
    )
    zoom: float = 1.0

    _queue: List[CameraStep] = field(default_factory=list, init=False, repr=False)
    _current: Optional[CameraStep] = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------
    def clear(self) -> None:
        """
        Reset to neutral and clear any queued animation.

        Use this when you want to snap back to default camera state and
        discard any pending cinematics.
        """
        self._queue.clear()
        self._current = None
        self.offset.update(0, 0)
        self.zoom = 1.0

    def is_idle(self) -> bool:
        """Return True if no tween is currently playing or queued."""
        return self._current is None and not self._queue

    def queue_tween(
        self,
        target_offset: tuple[float, float] | pygame.math.Vector2,
        target_zoom: float,
        duration: float,
    ) -> None:
        """
        Queue a tween to (target_offset, target_zoom) over `duration` seconds.

        Tweens are played in FIFO order. Calling code should regularly
        call `update(dt)` to advance the current step.
        """
        target_vec = pygame.math.Vector2(target_offset)
        step = CameraStep(
            target_offset=target_vec,
            target_zoom=float(target_zoom),
            duration=max(float(duration), 1e-6),
        )
        self._queue.append(step)

    def jump_to(
        self,
        offset: tuple[float, float] | pygame.math.Vector2,
        zoom: float = 1.0,
        clear_queue: bool = True,
    ) -> None:
        """
        Immediately snap the camera to a new offset/zoom.

        Optionally clears any queued cinematics (default True).
        """
        if clear_queue:
            self._queue.clear()
            self._current = None
        self.offset.update(*pygame.math.Vector2(offset))
        self.zoom = float(zoom)

    def update(self, dt: float) -> None:
        """
        Advance the current tween, if any, and update offset/zoom.

        Call this once per frame with the frame's delta time in seconds.
        """
        # If nothing is active, pull the next step from the queue
        if self._current is None and self._queue:
            self._current = self._queue.pop(0)

        step = self._current
        if step is None:
            return

        # Lazily capture starting state on first update
        if step.start_offset is None:
            step.start_offset = self.offset.copy()
        if step.start_zoom is None:
            step.start_zoom = self.zoom

        step.elapsed += dt
        t = step.normalized_time()

        # Interpolate offset and zoom
        start_off: pygame.math.Vector2 = step.start_offset
        target_off: pygame.math.Vector2 = step.target_offset
        self.offset = start_off.lerp(target_off, t)

        start_zoom: float = step.start_zoom
        target_zoom: float = step.target_zoom
        self.zoom = start_zoom + (target_zoom - start_zoom) * t

        # If we've finished the step, snap to final values and move on
        if step.elapsed >= step.duration:
            self.offset = target_off
            self.zoom = target_zoom
            self._current = None

    # ------------------------------------------------------------------
    # Convenience: basic skill cinematic
    # ------------------------------------------------------------------
    def play_basic_skill_cinematic(
        self,
        zoom_amount: float = 0.12,
        vertical_lift: float = -16.0,
    ) -> None:
        """
        A quick "punch in" cinematic:

          1. Ease up and zoom in a bit
          2. Hold for a short beat
          3. Ease back to neutral

        Intended to be invoked when a flashy skill lands.
        """
        self.clear()

        base_off = pygame.math.Vector2(0, 0)
        focus_off = pygame.math.Vector2(0, vertical_lift)

        # In, hold, out
        self.queue_tween(focus_off, 1.0 + zoom_amount, duration=0.20)
        self.queue_tween(focus_off, 1.0 + zoom_amount, duration=0.15)
        self.queue_tween(base_off, 1.0, duration=0.25)
    # ------------------------------------------------------------------
    # Convenience: directional sweep
    # ------------------------------------------------------------------
    def play_sweep(
        self,
        direction: tuple[float, float],
        distance: float = 24.0,
        duration: float = 0.18,
        hold: float = 0.04,
        return_duration: Optional[float] = None,
        clear_existing: bool = False,
    ) -> None:
        """
        Small directional camera sweep around the current offset.

        Typical pattern:
          - pan in the given direction
          - optional hold at the extreme
          - pan back to the starting offset

        Args:
            direction: (dx, dy) vector. Does not need to be normalized.
            distance: how far to push the camera, in pixels.
            duration: time to move outwards.
            hold: optional hold time at max displacement.
            return_duration: time to move back (defaults to `duration`).
            clear_existing: if True, clear any queued tweens first.
        """
        if return_duration is None:
            return_duration = duration

        dir_vec = pygame.math.Vector2(direction)
        if dir_vec.length_squared() == 0:
            # Default to a gentle rightward shove if direction is zero.
            dir_vec.x = 1.0
        dir_vec = dir_vec.normalize() * float(distance)

        base_off = self.offset.copy()
        target_off = base_off + dir_vec

        if clear_existing:
            self._queue.clear()
            self._current = None

        # We generally don't want sweeps to change zoom; keep whatever
        # zoom is active when this is called.
        current_zoom = self.zoom

        # Out
        self.queue_tween(target_off, current_zoom, duration)
        # Optional hold
        if hold > 0.0:
            self.queue_tween(target_off, current_zoom, hold)
        # Back
        self.queue_tween(base_off, current_zoom, return_duration)
        