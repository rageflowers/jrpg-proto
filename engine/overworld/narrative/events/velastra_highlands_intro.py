from __future__ import annotations

from engine.overworld.camera.sequence import (
    CameraSequence,
    TakeoverStep,
    PanToStep,
    HoldStep,
    ReleaseStep,
    SetFlagStep,
)

def build_velastra_highlands_intro(*, x: float, y: float, angle: float) -> CameraSequence:
    return CameraSequence([
        TakeoverStep(),
        PanToStep(
            x=x + 300.0,
            y=y,
            angle=angle + 0.5,
            duration_s=2.0,
        ),
        HoldStep(0.4),
        ReleaseStep(blend_s=0.75),
        SetFlagStep("vh_intro_done"),
    ])
