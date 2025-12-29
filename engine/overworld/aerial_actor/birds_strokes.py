# engine/overworld/aerial_actor/birds_strokes.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import random
import math
import pygame

from engine.overworld.regions.spec import AerialActorSpec


@dataclass
class BirdsStrokesActor:
    kind: str
    birds: List[dict]
    calm: float = 0.75
    x_pad: float = 80.0

    def draw(
        self,
        surf: pygame.Surface,
        *,
        cam_angle: float,
        horizon_y: int,
        dt: float,
        sky_t: float = 0.0,
    ) -> None:
        sw, sh = surf.get_size()
        bottom = max(10, horizon_y - 10)

        # global cloud-like drift (match old presenter feel)
        drift_time = float(sky_t) * 6.0
        drift_yaw = float(cam_angle) * (sw * 0.03)
        drift = (drift_time + drift_yaw) % (sw + 80)

        calm = float(self.calm)

        for b in self.birds:
            speed_mul = 0.6 + 0.8 * b["scale"]
            b["x"] = (b["x"] + b["vx"] * speed_mul * dt * 60.0 * calm) % (sw + 80)

            b["phase"] += dt * (2.0 * math.pi) * b["flap_hz"] * calm
            wob = 1.0 + (b["flap_amp"] * calm) * math.sin(b["phase"])
            s = b["scale"] * wob

            b["bob_phase"] += dt * (2.0 * math.pi) * b["bob_hz"] * calm
            bob = (b["bob_amp"] * calm) * math.sin(b["bob_phase"])

            x = int((b["x"] + drift) % (sw + 80)) - 40
            y = int(min(bottom - 6, max(12, b["y"] + bob)))

            span = max(3, int(10 * s * b["span_mul"]))
            rise = max(2, int(4 * s))

            color = (20, 20, 20)
            pygame.draw.line(surf, color, (x - span, y), (x, y + rise), 1)
            pygame.draw.line(surf, color, (x + span, y), (x, y + rise), 1)

def build_birds_strokes(
    spec: AerialActorSpec,
    *,
    internal_w: int,
    horizon_y: int,
    rng: Optional[random.Random] = None,
) -> BirdsStrokesActor:
    p: Dict[str, Any] = dict(spec.params or {})
    r = rng or random

    def fr(key: str, default: float) -> float:
        return float(p.get(key, default))

    def ir(key: str, default: int) -> int:
        return int(p.get(key, default))

    count = ir("count", 8)
    calm = fr("calm", 0.55)

    x_pad = fr("x_pad", 80.0)
    y_min = fr("y_min", 95.0)
    y_max = min(fr("y_max", 165.0), float(horizon_y - 12))

    scale_min = fr("scale_min", 0.50)
    scale_max = fr("scale_max", 0.90)

    vx_min = fr("vx_min", 0.15)
    vx_max = fr("vx_max", 1.60)

    span_mul_min = fr("span_mul_min", 0.90)
    span_mul_max = fr("span_mul_max", 1.20)

    flap_hz_min = fr("flap_hz_min", 0.70)
    flap_hz_max = fr("flap_hz_max", 1.80)
    flap_amp_min = fr("flap_amp_min", 0.04)
    flap_amp_max = fr("flap_amp_max", 0.10)

    bob_hz_min = fr("bob_hz_min", 0.08)
    bob_hz_max = fr("bob_hz_max", 0.25)
    bob_amp_min = fr("bob_amp_min", 0.20)
    bob_amp_max = fr("bob_amp_max", 0.80)

    birds: List[dict] = []
    for _ in range(count):
        base_scale = r.uniform(scale_min, scale_max)
        birds.append({
            "x": r.uniform(0, internal_w + x_pad),
            "y": r.uniform(y_min, y_max),
            "vx": r.uniform(vx_min, vx_max),

            "phase": r.uniform(0.0, 6.28318),
            "flap_hz": r.uniform(flap_hz_min, flap_hz_max),
            "flap_amp": r.uniform(flap_amp_min, flap_amp_max),

            "scale": base_scale,
            "span_mul": r.uniform(span_mul_min, span_mul_max),

            "bob_hz": r.uniform(bob_hz_min, bob_hz_max),
            "bob_amp": r.uniform(bob_amp_min, bob_amp_max),
            "bob_phase": r.uniform(0.0, 6.28318),
        })

    return BirdsStrokesActor(
        kind="birds",
        birds=birds,
        calm=calm,
        x_pad=x_pad,
    )
