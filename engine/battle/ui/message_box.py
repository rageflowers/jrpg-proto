# engine/battle/ui/message_box.py
from __future__ import annotations

import pygame
from engine.battle.ui.theme import THEME


def draw_message_box(
    ui,  # BattleUI instance; intentionally untyped to avoid circular imports
    *,
    surface: pygame.Surface,
    message: str,
    rect: pygame.Rect,
) -> None:
    """
    Render-only message box.

    NOTE: This must match BattleUI._draw_message_box behavior exactly.
    Paste the body of BattleUI._draw_message_box into here without refactors.
    """
    # Create an alpha panel and blit it (per-pixel alpha respected)
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, THEME.dialog_fill, panel.get_rect(), border_radius=8)
    surface.blit(panel, rect.topleft)

    # Border on the main surface
    pygame.draw.rect(surface, THEME.panel_border, rect, width=2, border_radius=8)

    msg = message or ""
    words = msg.split(" ")
    lines = []
    current = ""

    for w in words:
        test = (current + " " + w).strip()
        test_surf = ui.font_small.render(test, True, THEME.text_primary)
        if test_surf.get_width() > rect.width - 20 and current:
            lines.append(current)
            current = w
        else:
            current = test
    if current:
        lines.append(current)

    max_lines = 2
    lines = lines[:max_lines]

    for i, line in enumerate(lines):
        text = ui.font_small.render(line, True, THEME.text_primary)
        surface.blit(
            text,
            (rect.x + 10, rect.y + 8 + i * (ui.font_small.get_height() + 4)),
        )