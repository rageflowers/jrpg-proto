# engine/battle/ui/hud.py
from __future__ import annotations

import pygame
from typing import Any, Sequence


def draw_hud(
    ui,  # BattleUI instance
    *,
    surface: pygame.Surface,
    arena,
    party: Sequence,
    enemies: Sequence,
    phase,
    ui_mode: str,
    active_index: int,
    hover_id: str | None,
    party_rect: pygame.Rect,
    enemy_rect: pygame.Rect,
) -> None:
    """
    Render-only HUD (party + enemies + CTB + status pips, etc.).
    Must match BattleUI._draw_hud exactly.

    NOTE:
    - Do NOT mutate anything.
    - Do NOT change layout or colors.
    - Keep local imports (like ActionPhase) if the original method had them.
    """
    from engine.battle.action_phases import ActionPhase
    max_rows = 4
    if not party:
        return

    # one slot per potential party member (fixed 4 rows)
    row_height = party_rect.height // max_rows
    name_x = party_rect.x + 4

    # Reserve space on the right for HP / MP bars
    bar_width = max(80, int(party_rect.width * 0.40))
    bar_x = party_rect.right - bar_width - 6

    # narrow columns for buff / debuff pips
    debuff_col_x = bar_x - 40
    buff_col_x = debuff_col_x - 40

    cursor = getattr(arena.controller, "cursor", None)

    for i, actor in enumerate(party[:max_rows]):
        row_top = party_rect.y + i * row_height
        row_center_y = row_top + row_height // 2

        # --- Name (ALWAYS computed) ---
        name_text = ui.font_small.render(actor.name, True, (230, 230, 240))
        name_y = row_center_y - name_text.get_height() // 2

        # --- Hover highlight (id-truth) ---
        actor_id = str(getattr(actor, "id", getattr(actor, "name", "")))
        is_hovered = (ui_mode == "targeting" and hover_id is not None and actor_id == hover_id)
        if is_hovered:
            highlight_rect = pygame.Rect(
                name_x - 4,
                row_top + 1,
                (bar_x + bar_width) - (name_x - 4),
                row_height - 2,
            )
            pygame.draw.rect(surface, (255, 255, 0), highlight_rect, width=2)

        # draw name
        surface.blit(name_text, (name_x, name_y))

        # --- CTB gauge underline under the name (players only) ---
        gauge_margin = 2
        gauge_x = name_x
        gauge_width = max(40, buff_col_x - gauge_x - 6)
        gauge_y = name_y + name_text.get_height() + gauge_margin

        ui._draw_ctb_gauge(
            surface,
            arena,
            actor,
            gauge_x,
            gauge_y,
            gauge_width,
            show_commit_tick=True,   # players: show 50% mark
        )

        # buff / debuff pip columns between name and bars
        ui._render_status_pips(
            surface,
            actor,
            buff_x=buff_col_x,
            debuff_x=debuff_col_x,
            row_center_y=row_center_y,
            mode="party",
        )

        # HP / MP bars stacked vertically on the right
        hp_height = 14
        mp_height = 14
        spacing = 4

        hp_y = row_center_y - (hp_height + spacing // 2)
        mp_y = hp_y + hp_height + spacing

        # HP bar
        hp_ratio = (actor.hp / actor.max_hp) if actor.max_hp > 0 else 0.0
        ui._draw_bar(
            surface,
            bar_x,
            hp_y,
            bar_width,
            hp_height,
            hp_ratio,
            fill_color=(200, 90, 140)
            if (phase == ActionPhase.PLAYER_COMMAND and i == active_index)
            else (150, 80, 150),
            border_color=(210, 190, 230),
        )
        # HP text overlay centered on the bar
        hp_label = f"{actor.hp}/{actor.max_hp}"
        hp_text = ui.font_small.render(hp_label, True, (250, 240, 250))
        surface.blit(
            hp_text,
            (
                bar_x + (bar_width - hp_text.get_width()) // 2,
                hp_y + (hp_height - hp_text.get_height()) // 2,
            ),
        )

        # MP bar
        mp_ratio = 0.0
        if getattr(actor, "max_mp", 0) > 0:
            mp_ratio = actor.mp / actor.max_mp

        ui._draw_bar(
            surface,
            bar_x,
            mp_y,
            bar_width,
            mp_height,
            mp_ratio,
            fill_color=(90, 130, 220),
            border_color=(180, 200, 240),
        )
        # MP text overlay centered on the MP bar
        mp_label = f"{actor.mp}/{actor.max_mp}"
        mp_text = ui.font_small.render(mp_label, True, (220, 235, 255))
        surface.blit(
            mp_text,
            (
                bar_x + (bar_width - mp_text.get_width()) // 2,
                mp_y + (mp_height - mp_text.get_height()) // 2,
            ),
        )

    # --------------------------------------------------
    # ENEMY GRID (right column) – 2 columns × 3 rows
    # --------------------------------------------------
    # We keep the original enemy list for indexing, but only *display*
    # those that are alive.
    original_enemies = list(enemies)
    living_indices = [
        i for i, e in enumerate(original_enemies)
        if getattr(e, "alive", True)
    ]
    visible_indices = living_indices[:6]

    cols = 2
    rows = 3
    cell_width = enemy_rect.width // cols
    cell_height = enemy_rect.height // rows if rows > 0 else 0

    for grid_pos, enemy_index in enumerate(visible_indices):
        col = grid_pos % cols
        row = grid_pos // cols
        if row >= rows:
            break

        enemy = original_enemies[enemy_index]

        cell_x = enemy_rect.x + col * cell_width
        cell_y = enemy_rect.y + row * cell_height
        cell_rect = pygame.Rect(
            cell_x,
            cell_y,
            cell_width - 4,
            cell_height - 4,
        )

        enemy_id = str(getattr(enemy, "id", getattr(enemy, "name", "")))
        is_hovered = (ui_mode == "targeting" and hover_id is not None and enemy_id == hover_id)
        if is_hovered:
            bg_col = (45, 25, 60)
            border_col = (255, 220, 240)
        else:
            bg_col = (30, 18, 40)
            border_col = (215, 190, 230)

        pygame.draw.rect(surface, bg_col, cell_rect)
        pygame.draw.rect(surface, border_col, cell_rect, width=1)

        # Upper strip: name
        name_text = ui.font_small.render(enemy.name, True, (230, 220, 240))
        name_x = cell_x + 4
        name_y = cell_y + 3
        surface.blit(name_text, (name_x, name_y))

        # Enemy CTB gauge underline under the name (no commit tick)
        gauge_margin = 1
        gauge_x = name_x
        gauge_width = cell_rect.width - 8  # inset a bit from the cell border
        gauge_y = name_y + name_text.get_height() + gauge_margin

        ui._draw_ctb_gauge(
            surface,
            arena,
            enemy,
            gauge_x,
            gauge_y,
            gauge_width,
            show_commit_tick=False,   # enemies act immediately at 100%
        )

        # Status pips (buff/debuff) for enemies
        row_center_y = cell_y + cell_height // 2
        buff_x = cell_x + 6
        debuff_x = buff_x  # same left edge; mode="enemy" handles vertical stacking
        ui._render_status_pips(
            surface,
            enemy,
            buff_x=buff_x,
            debuff_x=debuff_x,
            row_center_y=row_center_y,
            mode="enemy",
        )

        # Lower strip: HP bar with overlay
        hp_height = 14  # matches your thicker bars
        hp_ratio = (enemy.hp / enemy.max_hp) if enemy.max_hp > 0 else 0.0
        bar_margin_x = 4
        bar_width_e = cell_rect.width - bar_margin_x * 2
        hp_y = cell_y + cell_height - hp_height - 6

        ui._draw_bar(
            surface,
            cell_x + bar_margin_x,
            hp_y,
            bar_width_e,
            hp_height,
            hp_ratio,
            fill_color=(190, 70, 130),
            border_color=(215, 190, 230),
        )

        hp_label = f"{enemy.hp}/{enemy.max_hp}"
        hp_text = ui.font_small.render(hp_label, True, (245, 230, 245))
        surface.blit(
            hp_text,
            (
                cell_x + bar_margin_x + (bar_width_e - hp_text.get_width()) // 2,
                hp_y + (hp_height - hp_text.get_height()) // 2,
            ),
        )