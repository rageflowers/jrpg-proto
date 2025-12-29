# engine/battle/enemy_layout.py
from __future__ import annotations
from typing import List, Tuple


def compute_enemy_slots(
    count: int,
    bg_width: int,
    ground_y: int,
    height: int,
) -> List[Tuple[int, int]]:
    """
    Compute (x, y) slots for a pack of enemies in the battle scene.

    This is extracted from BattleArena._layout_enemies so it can be reused
    by other arena variants or scenes.
    """

    if count <= 0:
        return []

    n = min(count, 6)
    w = bg_width

    cx = int(w * 0.80)
    y_front = ground_y
    row_offset = int(height * 0.08)

    x_small = int(w * 0.07)
    x_big = int(w * 0.11)

    slots: List[Tuple[int, int]] = []

    if n == 1:
        slots = [(cx, y_front)]
    elif n == 2:
        slots = [
            (cx - 4, y_front - row_offset),
            (cx + 4, y_front),
        ]
    elif n == 3:
        slots = [
            (cx, y_front - row_offset),
            (cx - x_small, y_front),
            (cx + x_small, y_front),
        ]
    elif n == 4:
        y_back = y_front - row_offset
        slots = [
            (cx - x_small, y_back),
            (cx + x_small, y_back),
            (cx - x_small, y_front),
            (cx + x_small, y_front),
        ]
    elif n == 5:
        y_top = y_front - 2 * row_offset
        y_mid = y_front - row_offset
        y_bot = y_front
        slots = [
            (cx, y_top),
            (cx - x_small, y_mid),
            (cx + x_small, y_mid),
            (cx - x_big, y_bot),
            (cx + x_big, y_bot),
        ]
    else:
        y_back = y_front - row_offset
        y_front_row = y_front
        slots = [
            (cx - x_big, y_back),
            (cx, y_back - 3),
            (cx + x_big, y_back),
            (cx - x_big, y_front_row + 3),
            (cx, y_front_row),
            (cx + x_big, y_front_row + 3),
        ]

    return slots
