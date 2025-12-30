# engine/battle/ui/bars.py
from __future__ import annotations

import pygame
from typing import Any


def draw_bar(
    ui,
    *,
    surface: pygame.Surface,
    x: int,
    y: int,
    width: int,
    height: int,
    ratio: float,
    fill_color: tuple,
    bg_color: tuple = (25, 22, 34),
    border_color: tuple = (0, 0, 0),
    border_radius: int = 4,
) -> None:
    """
    Render-only bar helper.
    Must match BattleUI._draw_bar exactly.
    """
    pygame.draw.rect(surface, bg_color, (x, y, width, height), border_radius=border_radius)
    ratio = max(0.0, min(1.0, ratio))
    fill_width = int(width * ratio)
    if fill_width > 0:
        pygame.draw.rect(
            surface,
            fill_color,
            (x, y, fill_width, height),
            border_radius=border_radius,
        )
    pygame.draw.rect(
        surface,
        border_color,
        (x, y, width, height),
        width=1,
        border_radius=border_radius,
    )

def draw_ctb_gauge(
    ui,  # BattleUI instance (unused here; kept for consistency)
    *,
    surface: pygame.Surface,
    arena: Any,
    actor: Any,
    x: int,
    y: int,
    width: int,
    show_commit_tick: bool,
) -> None:
    """
    EXACT extraction of BattleUI._draw_ctb_gauge.
    """
    runtime = getattr(arena, "runtime", None)
    timeline = getattr(runtime, "timeline", None) if runtime is not None else None
    if timeline is None:
        return

    cid = getattr(actor, "id", None)
    if cid is None:
        ratio = 0.0
    else:
        try:
            ratio = float(timeline.get_gauge_ratio(cid))
        except Exception:
            ratio = 0.0

    ratio = max(0.0, min(1.0, ratio))
    if width <= 0:
        return

    gauge_height = 3
    border_rect = pygame.Rect(x, y, width, gauge_height)

    # Border
    pygame.draw.rect(surface, (140, 110, 190), border_rect, width=1)

    # Fill
    fill_width = int((width - 2) * ratio)
    if fill_width > 0:
        fill_rect = pygame.Rect(x + 1, y + 1, fill_width, gauge_height - 2)
        pygame.draw.rect(surface, (210, 180, 245), fill_rect)

    # Optional commit tick (players only)
    if show_commit_tick:
        try:
            commit = float(timeline.get_commit_threshold())
        except Exception:
            commit = 0.5

        commit = max(0.0, min(1.0, commit))
        tick_x = x + int(width * commit)

        top_y = y - 1
        bottom_y = y + gauge_height

        pygame.draw.line(
            surface,
            (245, 240, 255),
            (tick_x, top_y),
            (tick_x, bottom_y),
            width=1,
        )
        pygame.draw.line(
            surface,
            (245, 240, 255),
            (tick_x - 2, top_y),
            (tick_x + 2, top_y),
            width=1,
        )
