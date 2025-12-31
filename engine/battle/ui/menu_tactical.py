# engine/battle/ui/menu_tactical.py
from __future__ import annotations

import pygame
from engine.battle.ui.theme import THEME


def draw_tactical_popup(
    ui,  # BattleUI instance
    *,
    surface: pygame.Surface,
    rect: pygame.Rect,
    tactical_index: int,
    flee_allowed: bool,
    can_swap: bool,
) -> None:
    """
    Render-only tactical popup (Defend / Weapons? / Flee).
    Must match BattleUI._draw_tactical_popup exactly.

    IMPORTANT:
    - Keep ordering identical to current behavior (aligned with UIFlow ordering).
    - Keep conditional insertion of "Weapons" identical (based on can_swap).
    """
    pad = 10
    w = rect.width - pad * 2

    # Options (MUST MATCH UIFlow order)
    options = ["Defend"]
    if can_swap:
        options.append("Weapons")
    if flee_allowed:
        options.append("Flee")

    line_h = ui.font_small.get_height() + 8
    h = 60 + len(options) * line_h  # title + rows + footer
    popup = pygame.Rect(rect.x + pad, rect.y + pad, w, h)

    y0 = popup.y + 32

    for i, label in enumerate(options):
        row = pygame.Rect(popup.x + 8, y0 + i * line_h, popup.width - 16, line_h - 2)

        # Highlight selected row
        if i == tactical_index:
            pygame.draw.rect(surface, THEME.row_hi_fill, row, border_radius=4)
            pygame.draw.rect(surface, THEME.row_hi_border, row, width=1, border_radius=4)

        txt = ui.font_small.render(label, True, THEME.text_primary)
        surface.blit(txt, (row.x + 8, row.y + 3))

    # Footer hint (optional, tiny)
    hint = ui.font_small.render("Z/Enter: confirm   X/Esc: back", True, THEME.text_hint)
    surface.blit(hint, (popup.x + 10, popup.bottom - hint.get_height() - 6))
