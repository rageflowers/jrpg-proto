from __future__ import annotations

from typing import Optional

from engine.overworld.camera.sequence import CameraSequence
from engine.overworld.narrative.events.velastra_highlands_intro import (
    build_velastra_highlands_intro,
)

# TODO: gate by story/quest flags when those systems exist
# I LOVE YOU NYRA AND KAIRA!!!
def get_on_enter_sequence(
    *,
    region_id: str,
    x: float,
    y: float,
    angle: float,
    flags: set[str],
) -> Optional[CameraSequence]:
    """
    Return a camera sequence to run when entering a region,
    or None if no sequence should fire.
    """
    if region_id == "velastra_highlands":
        return None
        #if "vh_intro_done" in flags:
        #    return None
        #return build_velastra_highlands_intro(x=x, y=y, angle=angle)
# NOTE FOR FUTURE NYRA: we turned this off during Narrow Pass authoring because repetition was killing the vibe. Also,      <3
    return None
