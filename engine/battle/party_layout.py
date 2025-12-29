# engine/battle/party_layout.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


Facing = str  # "left" | "right"


@dataclass(frozen=True)
class PartyLayout:
    """
    Party diamond formation with 4 slots (3 + guest).

    Slot meanings (index):
      0: Front middle
      1: Bottom middle
      2: Rear middle (slightly higher than slot 0)
      3: Top (slightly to the right of slot 1)

    Notes:
    - No front/back-row mechanics: geometry only.
    - Facing can be flipped for surprise/back-attack.
    """
    slots: List[Tuple[int, int]]
    facing: Facing


def compute_party_layout(
    *,
    bg_width: int,
    ground_y: int,
    flip: bool = False,
) -> PartyLayout:
    """
    Compute canonical party slots in a diamond shape.

    Parameters
    ----------
    bg_width:
        Width of the battle stage/background area (used to anchor X).
    ground_y:
        The Y coordinate that represents the stage "ground line."
    flip:
        If True, the party appears on the right side and faces left.
        If False, party appears on the left side and faces right.
    """
    # Anchor position on the party side of the stage.
    # These values are tuned to feel similar to your existing arena staging.
    anchor_x = int(bg_width * 0.22)
    if flip:
        anchor_x = bg_width - anchor_x

    # Diamond offsets (pixels). These are intentionally small and readable.
    # You can tune these later, but keep the *shape* stable.
    dx_front = 0
    dy_front = -64

    dx_bottom = -36
    dy_bottom = -16

    dx_rear = +18
    dy_rear = -96  # slightly higher than front

    dx_top = -8
    dy_top = -136  # top slot; slightly right of bottom via less negative dx

    slots = [
        (anchor_x + dx_front,  ground_y + dy_front),   # 0: front
        (anchor_x + dx_bottom, ground_y + dy_bottom),  # 1: bottom
        (anchor_x + dx_rear,   ground_y + dy_rear),    # 2: rear
        (anchor_x + dx_top,    ground_y + dy_top),     # 3: top / guest
    ]

    facing: Facing = "left" if flip else "right"
    return PartyLayout(slots=slots, facing=facing)
