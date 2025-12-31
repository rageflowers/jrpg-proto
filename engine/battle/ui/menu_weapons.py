# engine/battle/ui/menu_weapons.py
from __future__ import annotations

from typing import Any
import pygame
from engine.battle.ui.theme import THEME


def draw_weapons_menu(
    ui,  # BattleUI instance
    *,
    surface: pygame.Surface,
    rect: pygame.Rect,
    arena: Any,   # BattleArena (kept Any to avoid import cycles)
    actor: Any,   # Actor/Combatant (kept Any for same reason)
) -> None:
    """
    Render-only weapons overlay.
    Must match BattleUI._draw_weapons_menu exactly.

    Notes:
    - weapon list is sourced from arena.ui_flow._list_compatible_weapons(actor)
    - cursor uses ui_flow.state.skills_index
    - equipped comes from runtime.equipment.get(actor_id)
    - draws paging, cursor highlight, checkmark, empty state text, and ATK/MAG bonuses
    """
    state = arena.ui_flow.state
    runtime = arena.runtime

    # UIFlow reuses skills_index as cursor for popup lists
    cursor = int(getattr(state, "skills_index", 0))

    # Weapons available to this actor (UIFlow already has the rules)
    try:
        weapons = arena.ui_flow._list_compatible_weapons(actor)
    except Exception:
        weapons = []

    # Resolve actor id + currently equipped weapon id
    actor_id = str(getattr(actor, "id", getattr(actor, "name", "unknown_actor")))
    equipped_id = None
    try:
        equipped_id = runtime.equipment.get(actor_id)
    except Exception:
        equipped_id = None

    # Popup frame
    pad = THEME.popup_pad
    w = rect.width - pad * 2
    line_h = ui.font_small.get_height() + 8
    visible_rows = min(6, max(3, len(weapons)))  # keep sane
    h = 60 + (visible_rows * line_h) + 22
    popup = pygame.Rect(rect.x + pad, rect.y + pad, w, h)

    panel = pygame.Surface(popup.size, pygame.SRCALPHA)
    panel.fill(THEME.panel_fill)
    surface.blit(panel, popup.topleft)
    pygame.draw.rect(surface, THEME.panel_border, popup, width=2, border_radius=THEME.border_radius)

    # Title
    title = ui.font_small.render("Weapons", True, THEME.text_primary)
    surface.blit(title, (popup.x + 10, popup.y + 8))

    # Empty state
    if not weapons:
        msg = ui.font_small.render("No weapons available.", True, THEME.text_primary)
        surface.blit(msg, (popup.x + 10, popup.y + 40))
        hint = ui.font_small.render("X/Esc: back", True, THEME.text_hint)
        surface.blit(hint, (popup.x + 10, popup.bottom - hint.get_height() - 6))
        return

    # Clamp cursor
    cursor = max(0, min(cursor, len(weapons) - 1))

    # Simple paging if list longer than visible_rows
    start = 0
    if len(weapons) > visible_rows:
        # keep cursor centered-ish
        start = max(0, min(cursor - visible_rows // 2, len(weapons) - visible_rows))
    view = weapons[start:start + visible_rows]

    y0 = popup.y + 32

    for i, wdef in enumerate(view):
        idx = start + i
        wid = str(getattr(wdef, "id", ""))
        name = str(getattr(wdef, "name", wid or "<?>"))

        atk = float(getattr(wdef, "atk_bonus", 0.0) or 0.0)
        mag = float(getattr(wdef, "mag_bonus", 0.0) or 0.0)

        row = pygame.Rect(popup.x + 8, y0 + i * line_h, popup.width - 16, line_h - 2)

        # Highlight selected row
        if idx == cursor:
            pygame.draw.rect(surface, THEME.row_hi_fill, row, border_radius=4)
            pygame.draw.rect(surface, THEME.row_hi_border, row, width=1, border_radius=4)

        # Mark equipped
        eq_mark = "✓ " if (equipped_id is not None and str(equipped_id) == wid) else "  "

        # Text
        left = f"{eq_mark}{name}"
        right = []
        if atk:
            right.append(f"ATK+{int(atk)}")
        if mag:
            right.append(f"MAG+{int(mag)}")
        right_txt = "  ".join(right) if right else ""

        txt_l = ui.font_small.render(left, True, THEME.text_primary)
        surface.blit(txt_l, (row.x + 8, row.y + 3))

        if right_txt:
            txt_r = ui.font_small.render(right_txt, True, THEME.text_secondary)
            surface.blit(txt_r, (row.right - txt_r.get_width() - 10, row.y + 3))

    hint = ui.font_small.render("Z/Enter: equip   X/Esc: back", True, THEME.text_hint)
    surface.blit(hint, (popup.x + 10, popup.bottom - hint.get_height() - 6))
