# engine/battle/ui/layout.py
from __future__ import annotations

import pygame


def layout_rects(ui_rect: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
    """
    Given the full UI rect, return:
      (dialog_rect, menu_rect, party_rect, enemy_rect)

    NOTE: This must match BattleUI._layout_rects behavior exactly.
    Paste the body of BattleUI._layout_rects into here without refactors.
    """
    outer = ui_rect
    margin = 10
    v_gap = 6
    dialog_height = 40

    # Inner width shared by all sub-panels
    inner_x = outer.x + margin
    inner_w = outer.width - 2 * margin

    # Top dialog / narration strip
    dialog_rect = pygame.Rect(inner_x, outer.y + v_gap, inner_w, dialog_height)

    # Bottom band (menu + party + enemies)
    bottom_y = dialog_rect.bottom + v_gap
    bottom_h = outer.bottom - bottom_y - v_gap
    bottom_rect = pygame.Rect(inner_x, bottom_y, inner_w, bottom_h)

    # Split bottom band into 3 vertical columns
    menu_w = int(bottom_rect.width * 0.27)   # left
    enemy_w = int(bottom_rect.width * 0.30)  # right
    party_w = bottom_rect.width - menu_w - enemy_w - 2 * v_gap  # center

    menu_rect = pygame.Rect(bottom_rect.x, bottom_y, menu_w, bottom_h)
    party_rect = pygame.Rect(menu_rect.right + v_gap, bottom_y, party_w, bottom_h)
    enemy_rect = pygame.Rect(party_rect.right + v_gap, bottom_y, enemy_w, bottom_h)
    
    return dialog_rect, menu_rect, party_rect, enemy_rect
