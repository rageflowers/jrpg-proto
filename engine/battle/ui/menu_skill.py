# engine/battle/ui/menu_skill.py
from __future__ import annotations

import pygame
from typing import Any


def get_root_menu_options(actor: Any, skills: list[Any]) -> list[str]:
    """
    Must match BattleUI._get_root_menu_options exactly.
    """
    name = getattr(actor, "name", "").lower()

    # 1) Attack is always present
    options: list[tuple[str, str]] = [("Attack", "attack")]

    # 2) Character-specific arts label
    if "setia" in name:
        arts_label = "Martial Arts"
    elif "nyra" in name:
        arts_label = "Holy Arts"
    elif "kaira" in name:
        arts_label = "Shadow Arts"
    else:
        arts_label = "Arts"

    options.append((arts_label, "arts"))

    # 3) Elemental — only if the actor actually has elemental skills
    has_elemental = any(
        getattr(s.meta, "menu_group", None) == "elemental" for s in skills
    )
    if has_elemental:
        options.append(("Elemental", "elemental"))

    # 4) Items — always shown for now (we can gate it later)
    options.append(("Items", "item"))

    return options

def draw_skill_menu(
    ui,  # BattleUI instance
    *,
    surface: pygame.Surface,
    arena: Any,
    phase: Any,
    ui_mode: str,
    actor: Any,
    skills: list[Any],
    menu_index: int,
    rect: pygame.Rect,
) -> None:
    """
    Render-only skill menu (root + grouped submenu + quantities).
    Must match BattleUI._draw_skill_menu exactly.
    """
    from engine.battle.action_phases import ActionPhase

    # Only show menu during player turns and end-of-battle states
    if phase != ActionPhase.PLAYER_COMMAND and phase != ActionPhase.BATTLE_END:
        return

    x, y = rect.x, rect.y

    # Semi-transparent menu panel
    menu_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
    menu_surf.fill((15, 10, 25, 210))  # slightly see-through
    surface.blit(menu_surf, rect.topleft)

    pygame.draw.rect(surface, (90, 60, 130), rect, width=2, border_radius=8)

    # Victory / defeat message
    if phase == ActionPhase.BATTLE_END:
        label = "Press any key to reset"
        text = ui.font_small.render(label, True, (230, 230, 240))
        surface.blit(
            text,
            (
                rect.centerx - text.get_width() // 2,
                rect.centery - text.get_height() // 2,
            ),
        )
        return

    # ------------------------------
    # Header
    # ------------------------------
    header = ui.font_small.render(f"{actor.name}'s Turn", True, (230, 230, 240))
    surface.blit(header, (x + 10, y + 8))

    list_y = y + 32
    line_h = 24

    # ------------------------------
    # Root menu vs skills submenu
    # ------------------------------
    if ui.menu_layer == "root":
        # ROOT MENU (Attack / Arts / Elemental / Items)
        options = ui._get_root_menu_options(actor, skills)
        for i, (label, _group) in enumerate(options):
            is_selected = (i == ui.root_index)
            color = (255, 255, 255) if is_selected else (200, 200, 210)
            text = ui.font_small.render(label, True, color)
            tx = x + 34
            ty = list_y + i * line_h
            surface.blit(text, (tx, ty))

            if is_selected:
                cursor = ui.font_small.render("▶", True, color)
                surface.blit(cursor, (x + 10, ty))
        return

    # SKILLS SUBMENU (Arts / Elemental / Items)
    group = ui.current_group or "arts"

    # Build list of (global_index, skill) for the current group
    from typing import Any  # safe due to __future__ annotations
    grouped: list[tuple[int, Any]] = []
    for global_idx, s in enumerate(skills):
        meta = getattr(s, "meta", None)
        if meta is None:
            continue
        if getattr(meta, "menu_group", None) == group:
            grouped.append((global_idx, s))

    if not grouped:
        text = ui.font_small.render("No abilities learned yet.", True, (200, 200, 210))
        surface.blit(text, (x + 34, list_y))
        return

    # Optional group header
    group_label_map = {
        "attack": "Attack",
        "arts": "Arts",
        "elemental": "Elemental",
        "item": "Items",
    }
    subtitle = group_label_map.get(group, group.title())
    subtitle_text = ui.font_small.render(subtitle, True, (210, 210, 230))
    surface.blit(subtitle_text, (x + 10, y + 8 + ui.font_small.get_height() + 2))

    # Shift list down a bit to leave room for subtitle
    list_y = y + 32 + ui.font_small.get_height() + 6

    # Scrolling window for long lists
    max_visible = 4  # number of entries to show at once
    total = len(grouped)

    # Clamp selection
    ui.skills_index = max(0, min(ui.skills_index, total - 1))

    # Choose a window such that the selected item is roughly centered
    if total <= max_visible:
        start_index = 0
    else:
        half = max_visible // 2
        start_index = max(0, ui.skills_index - half)
        if start_index + max_visible > total:
            start_index = total - max_visible

    visible = grouped[start_index:start_index + max_visible]

    # Draw up/down arrows if there are items above/below the window
    if start_index > 0:
        arrow_up = ui.font_small.render("▲", True, (200, 200, 210))
        surface.blit(arrow_up, (x + rect.width - 24, list_y - line_h // 2))

    if start_index + max_visible < total:
        arrow_down = ui.font_small.render("▼", True, (200, 200, 210))
        surface.blit(
            arrow_down,
            (x + rect.width - 24, list_y + max_visible * line_h - line_h // 2),
        )

    # Draw the visible slice
    for i, (global_idx, skill) in enumerate(visible):
        is_selected = (start_index + i == ui.skills_index)
        color = (255, 255, 255) if is_selected else (200, 200, 210)

        meta = skill.meta
        label = meta.name
        suffixes: list[str] = []
        # Forge XIV: show MP cost next to skills
        mp_cost = int(getattr(meta, "mp_cost", 0) or 0)
        if mp_cost > 0:
            suffixes.append(str(mp_cost))

        # Item-skill quantity: tags include "consumes:<item_id>"
        try:
            tags = getattr(meta, "tags", None) or set()
            consumes_item_id = None
            for t in tags:
                if isinstance(t, str) and t.startswith("consumes:"):
                    consumes_item_id = t.split(":", 1)[1].strip()
                    break

            if consumes_item_id and getattr(arena, "ui_flow", None) is not None:
                qty = int(arena.ui_flow.get_battle_available_item_qty(arena, consumes_item_id))
                suffixes.append(f"x{qty}")
        except Exception:
            pass

        # Apply suffixes in the same style as MP cost uses
        if suffixes:
            # Examples:
            #   "Potion  (x1)"
            #   "Fireball  (5)"
            #   "Potion  (0 x1)" (if you ever had both; normally items have mp_cost=0)
            label = f"{label}  ({' '.join(suffixes)})"

        text = ui.font_small.render(label, True, color)

        tx = x + 34
        ty = list_y + i * line_h
        surface.blit(text, (tx, ty))

        if is_selected:
            cursor = ui.font_small.render("▶", True, color)
            surface.blit(cursor, (x + 10, ty))
