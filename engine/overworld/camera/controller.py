from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional
import math

from engine.overworld.mode7_renderer_px import Mode7Camera
from engine.overworld.camera.types import CameraPose


class CameraMode(Enum):
    FOLLOW = auto()
    SCRIPT = auto()


def _wrap_pi(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_angle(a: float, b: float, t: float) -> float:
    d = _wrap_pi(b - a)
    return _wrap_pi(a + d * t)


@dataclass
class FollowParams:
    turn_speed_rad_s: float = 1.25  # matches current feel (Q/E) :contentReference[oaicite:2]{index=2}


class CameraController:
    """
    Sole authority for camera pose.
    - FOLLOW: stays anchored to a follow target, accepts turn intent
    - SCRIPT: ignores player input; sequence commands set targets
    """

    def __init__(self, *, camera: Mode7Camera, follow_params: Optional[FollowParams] = None) -> None:
        self.camera = camera
        self.follow_params = follow_params or FollowParams()

        self.mode: CameraMode = CameraMode.FOLLOW

        # FOLLOW state
        self._follow_target: CameraPose = CameraPose(camera.x, camera.y, camera.angle)

        # SCRIPT state
        self._script_pose: CameraPose = CameraPose(camera.x, camera.y, camera.angle)
        self._pan_active: bool = False
        self._pan_from: CameraPose = CameraPose(camera.x, camera.y, camera.angle)
        self._pan_to: CameraPose = CameraPose(camera.x, camera.y, camera.angle)
        self._pan_t: float = 0.0
        self._pan_dur: float = 0.0

        # RELEASE/BLEND (future-ready, used minimally now)
        self._blend_active: bool = False
        self._blend_from: CameraPose = CameraPose(camera.x, camera.y, camera.angle)
        self._blend_t: float = 0.0
        self._blend_dur: float = 0.0

    # ----------------------------
    # FOLLOW API
    # ----------------------------

    def set_follow_target(self, *, x: float, y: float) -> None:
        # Angle stays whatever controller currently owns.
        self._follow_target = CameraPose(x, y, self._follow_target.angle)

    def add_turn_intent(self, *, dt: float, turn_dir: float) -> None:
        """
        turn_dir: -1.0 (left), +1.0 (right), 0.0 none
        """
        if self.mode != CameraMode.FOLLOW:
            return
        if turn_dir == 0.0:
            return
        a = self._follow_target.angle + (turn_dir * self.follow_params.turn_speed_rad_s * dt)
        self._follow_target = CameraPose(self._follow_target.x, self._follow_target.y, a)

    def snap_angle(self, angle: float) -> None:
        """Immediately set camera angle AND the controller's owned target angle."""
        a = float(angle)

        # Update whichever state is currently authoritative
        if self.mode == CameraMode.SCRIPT:
            self._script_pose = CameraPose(self._script_pose.x, self._script_pose.y, a)
            self._pan_active = False  # optional: cancel pan if you consider snap a hard override
        else:
            self._follow_target = CameraPose(self._follow_target.x, self._follow_target.y, a)

        # Apply immediately (so it takes effect this frame)
        self.camera.angle = a


    # ----------------------------
    # SCRIPT API
    # ----------------------------

    def takeover(self) -> None:
        """Borrow authority immediately. Hard switch for MVP."""
        if self.mode == CameraMode.SCRIPT:
            return
        # Seed script pose from current effective camera
        self._script_pose = CameraPose(self.camera.x, self.camera.y, self.camera.angle)
        self._pan_active = False
        self.mode = CameraMode.SCRIPT

    def release(self, *, blend_s: float = 0.0) -> None:
        """Return authority to FOLLOW. Hard switch now; blend later."""
        if self.mode != CameraMode.SCRIPT:
            return

        if blend_s <= 0.0:
            # Hard return: follow angle becomes current script angle
            self._follow_target = CameraPose(self._follow_target.x, self._follow_target.y, self.camera.angle)
            self.mode = CameraMode.FOLLOW
            self._pan_active = False
            self._blend_active = False
            return
        # Ensure follow target angle matches what we’re releasing from,
        # so the blend lands exactly where the camera is facing.
        self._follow_target = CameraPose(self._follow_target.x, self._follow_target.y, self.camera.angle)

        # Optional blend (works, even if we don’t use it much yet)
        self._blend_active = True
        self._blend_from = CameraPose(self.camera.x, self.camera.y, self.camera.angle)
        self._blend_t = 0.0
        self._blend_dur = float(blend_s)
        self.mode = CameraMode.FOLLOW
        self._pan_active = False

    def pan_to(
        self,
        *,
        x: float,
        y: float,
        angle: float | None = None,
        duration_s: float,
    ) -> None:
        """Position-only pan for MVP. Rotation second."""
        if self.mode != CameraMode.SCRIPT:
            # sequences must explicitly takeover first
            self.takeover()

        self._pan_active = True
        self._pan_from = CameraPose(self.camera.x, self.camera.y, self.camera.angle)
        target_angle = self.camera.angle if angle is None else float(angle)
        self._pan_to = CameraPose(float(x), float(y), target_angle)
        self._pan_t = 0.0
        self._pan_dur = max(0.0001, float(duration_s))

    # ----------------------------
    # TICK (single authority)
    # ----------------------------

    def update(self, dt: float) -> None:
        if self.mode == CameraMode.SCRIPT:
            self._update_script(dt)
        else:
            self._update_follow(dt)

        # Apply optional release blend on top (if active)
        if self._blend_active:
            self._blend_t += dt
            t = min(1.0, self._blend_t / max(self._blend_dur, 0.0001))

            tx, ty = self._follow_target.x, self._follow_target.y
            ta = self._follow_target.angle

            bx = _lerp(self._blend_from.x, tx, t)
            by = _lerp(self._blend_from.y, ty, t)
            ba = _lerp_angle(self._blend_from.angle, ta, t)

            self.camera.x = bx
            self.camera.y = by
            self.camera.angle = ba

            if t >= 1.0:
                self._blend_active = False
            return

        # Normal apply
        self.camera.x = self._effective_pose.x
        self.camera.y = self._effective_pose.y
        self.camera.angle = self._effective_pose.angle

    def _update_follow(self, dt: float) -> None:
        # MVP: hard follow (no smoothing yet)
        self._effective_pose = CameraPose(self._follow_target.x, self._follow_target.y, self._follow_target.angle)

    def _update_script(self, dt: float) -> None:
        if not self._pan_active:
            self._effective_pose = self._script_pose
            return

        self._pan_t += dt
        t = min(1.0, self._pan_t / self._pan_dur)

        x = _lerp(self._pan_from.x, self._pan_to.x, t)
        y = _lerp(self._pan_from.y, self._pan_to.y, t)
        a = _lerp_angle(self._pan_from.angle, self._pan_to.angle, t)

        self._script_pose = CameraPose(x, y, a)
        self._effective_pose = self._script_pose

        if t >= 1.0:
            self._pan_active = False
