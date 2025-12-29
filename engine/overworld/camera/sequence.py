from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


class Step(Protocol):
    def start(self, ctx: "CameraSequenceContext") -> None: ...
    def update(self, ctx: "CameraSequenceContext", dt: float) -> bool: ...
    # return True when step is complete


@dataclass
class CameraSequenceContext:
    camera_ctl: object  # CameraController (kept generic to avoid import tangles)
    flags: set[str]     # world-state bag for gating

@dataclass
class TakeoverStep:
    def start(self, ctx: CameraSequenceContext) -> None:
        ctx.camera_ctl.takeover()

    def update(self, ctx: CameraSequenceContext, dt: float) -> bool:
        return True


@dataclass
class PanToStep:
    x: float
    y: float
    angle: Optional[float] = None
    duration_s: float = 1.0

    def start(self, ctx: CameraSequenceContext) -> None:
        # CameraController.pan_to supports angle=None
        ctx.camera_ctl.pan_to(x=self.x, y=self.y, angle=self.angle, duration_s=self.duration_s)

    def update(self, ctx: CameraSequenceContext, dt: float) -> bool:
        # Pan completion is internal; we just wait duration_s.
        # (Simple + robust for MVP; later we can expose "is_panning".)
        self._t += dt
        return self._t >= self.duration_s

    def __post_init__(self) -> None:
        self._t = 0.0


@dataclass
class HoldStep:
    seconds: float

    def start(self, ctx: CameraSequenceContext) -> None:
        self._t = 0.0

    def update(self, ctx: CameraSequenceContext, dt: float) -> bool:
        self._t += dt
        return self._t >= self.seconds


@dataclass
class ReleaseStep:
    blend_s: float = 0.75

    def start(self, ctx: CameraSequenceContext) -> None:
        ctx.camera_ctl.release(blend_s=self.blend_s)

    def update(self, ctx: CameraSequenceContext, dt: float) -> bool:
        # Release blends inside controller; step completes immediately.
        return True

@dataclass
class SetFlagStep:
    flag: str

    def start(self, ctx: CameraSequenceContext) -> None:
        ctx.flags.add(self.flag)

    def update(self, ctx: CameraSequenceContext, dt: float) -> bool:
        return True


class CameraSequence:
    def __init__(self, steps: list[Step]) -> None:
        self._steps = steps
        self._i = 0
        self._started = False
        self._done = False

    @property
    def done(self) -> bool:
        return self._done

    def start(self, ctx: CameraSequenceContext) -> None:
        if self._started or self._done:
            return
        self._started = True
        if not self._steps:
            self._done = True
            return
        self._steps[0].start(ctx)

    def update(self, ctx: CameraSequenceContext, dt: float) -> None:
        if self._done:
            return
        if not self._started:
            self.start(ctx)

        while True:
            step = self._steps[self._i]
            finished = step.update(ctx, dt)
            if not finished:
                return

            self._i += 1
            if self._i >= len(self._steps):
                self._done = True
                return

            # start next step immediately
            self._steps[self._i].start(ctx)
