# ======================================================================
# FORGE XVII — BATTLEUI: RENDERING ONLY (HUD + LAYOUT)
#
# BattleUI draws the battle HUD, menus, highlights, and popups.
# It is a *pure view* over state owned by UIFlow / Controller / Arena.
#
# CORE LAW (XVII.25, binding):
#   UIFlow decides what happens.
#   BattleUI draws what it looks like.
#   BattleArena wires who talks to whom.
#
# BattleUI OWNS:
#   - Layout and visual hierarchy (rects, spacing, fonts)
#   - Rendering HUD: party, enemies, CTB gauges, status pips, message box
#   - Rendering menus and overlays (including tactical popup)
#   - Lightweight view-model helpers for rendering (grouping, labels)
#   - Visual reset hooks (reset_menu) when requested by Arena/UIFlow
#
# BattleUI MUST NOT:
#   - Interpret keys or route input (no intent, no mode transitions)
#   - Emit BattleCommand, mutate battle state, or call controller actions
#   - Contain selection rules beyond "draw what's currently selected"
#
# TRANSITION NOTE:
#   handle_key() is intentionally a stub.
#   If you feel tempted to add logic there, STOP and put it in UIFlow.
#
# QUICK SMELL TEST:
#   If it changes what happens (not what it looks like), it is not BattleUI.
# ======================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Any
from engine.battle.ui.layout import layout_rects
from engine.battle.ui.message_box import draw_message_box
from engine.battle.ui.menu_tactical import draw_tactical_popup
from engine.battle.ui.menu_weapons import draw_weapons_menu
from engine.battle.ui.bars import draw_bar, draw_ctb_gauge
from engine.battle.ui.status_pips import render_status_pips
from engine.battle.ui.hud import draw_hud
from engine.battle.ui.menu_skill import get_root_menu_options, draw_skill_menu

import pygame

@dataclass
class BattleUI:
    """
    Handles all battle HUD / menus / message box rendering.

    BattleArena owns one instance and passes itself during draw(),
    so this class can read whatever state it needs.

    BattleUI — Battle UI Rendering & Layout

    Responsibilities:
    - Draw menus, popups, gauges, highlights, and text
    - Define layout, spacing, fonts, and visual hierarchy
    - Build menu/view models (root options, grouped skills)
    - Reset visual state when requested

    Non-Responsibilities:
    - Input handling or key interpretation
    - UI mode transitions
    - Emitting BattleCommand or altering battle state

    Design Contract:
    - BattleUI visualizes state provided by UIFlow / Controller.
    - BattleUI never decides intent.
    """

    ui_rect: pygame.Rect
    font_small: pygame.font.Font
    font_med: pygame.font.Font
    font_large: pygame.font.Font

    # Menu state
    menu_layer: str = "root"        # "root" or "skills"
    root_index: int = 0             # which root option is selected
    skills_index: int = 0           # which skill in the current group is selected
    current_group: str | None = None  # "attack", "arts", "elemental", "item" (for submenu)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, arena: "BattleArena") -> None:
        """
        Draw the entire bottom UI panel:
        - semi-transparent panel background
        - party/enemy HUD (center + right)
        - skill menu (left)
        - dialog strip (center top)
        """

        # --- Truth sources ---
        runtime = arena.runtime
        session = runtime.session
        mapper = runtime.action_mapper

        phase = mapper.phase
        ui_mode = getattr(arena.ui_flow.state, "mode", "menu")
        hover_id = getattr(arena.ui_flow.state, "hover_id", None)
        message = arena.message

        # Combatant lists (truth)
        party = getattr(session, "party", []) or []
        enemies = getattr(session, "enemies", []) or []

        # Active actor (truth)
        active_actor = None
        active_index = 0
        if getattr(mapper, "current_actor_id", None):
            try:
                active_actor = session.get_combatant(mapper.current_actor_id)
            except Exception:
                active_actor = None

        # Compute active_index for HUD highlighting (best-effort)
        if active_actor is not None and party:
            active_id = str(getattr(active_actor, "id", getattr(active_actor, "name", "")))
            for i, a in enumerate(party):
                a_id = str(getattr(a, "id", getattr(a, "name", "")))
                if a_id == active_id:
                    active_index = i
                    break

        # Transitional seam: skills still come from controller for now
        controller = getattr(arena, "controller", None)
        skills = controller.skills if controller is not None else []

        # --- UI panel background ---
        ui_surf = pygame.Surface(self.ui_rect.size, pygame.SRCALPHA)
        ui_surf.fill((10, 10, 20, 200))  # RGBA darker overlay
        surface.blit(ui_surf, self.ui_rect.topleft)
        pygame.draw.rect(surface, (80, 80, 130), self.ui_rect, width=2)

        # Layout pieces
        dialog_rect, menu_rect, party_rect, enemy_rect = self._layout_rects()

        # --- Center party HUD + right enemy HUD ---
        self._draw_hud(
            surface,
            arena,
            party=party,
            enemies=enemies,
            phase=phase,
            ui_mode=ui_mode,
            active_index=active_index,
            hover_id=hover_id,
            party_rect=party_rect,
            enemy_rect=enemy_rect,
        )

        # --- Left menu panel ---
        if party and active_actor is not None:
            # If weapons popup is open, don't draw the skills submenu underneath.
            if getattr(arena.ui, "menu_layer", "root") != "weapons":
                self._draw_skill_menu(
                    surface,
                    arena=arena,
                    phase=phase,
                    ui_mode=ui_mode,
                    actor=active_actor,
                    skills=skills,
                    menu_index=0,
                    rect=menu_rect,
                )

            # Weapons popup overlay
            if getattr(arena.ui, "menu_layer", "root") == "weapons":
                self._draw_weapons_menu(
                    surface,
                    rect=menu_rect,
                    arena=arena,
                    actor=active_actor,
                )

            # Tactical popup overlay (unchanged)
            if getattr(arena, "ui_flow", None) is not None:
                if arena.ui_flow.state.mode == "tactical":
                    self._draw_tactical_popup(
                        surface,
                        rect=menu_rect,
                        tactical_index=arena.ui_flow.state.tactical_index,
                        flee_allowed=True,
                        can_swap=arena.ui_flow._can_weapon_swap(active_actor),
                    )

        # --- Middle dialog / narration strip ---
        self._draw_message_box(surface, message=message, rect=dialog_rect)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _layout_rects(self):
        return layout_rects(self.ui_rect)

    def _draw_bar(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        width: int,
        height: int,
        ratio: float,
        fill_color: tuple[int, int, int],
        bg_color: tuple[int, int, int] = (25, 22, 34),
        border_color: tuple[int, int, int] = (0, 0, 0),
        border_radius: int = 4,
    ) -> None:
        return draw_bar(
            self,
            surface=surface,
            x=x,
            y=y,
            width=width,
            height=height,
            ratio=ratio,
            fill_color=fill_color,
            bg_color=bg_color,
            border_color=border_color,
            border_radius=border_radius,
        )

    def _draw_ctb_gauge(
        self,
        surface: pygame.Surface,
        arena,
        actor,
        x: int,
        y: int,
        width: int,
        *,
        show_commit_tick: bool,
    ) -> None:
        return draw_ctb_gauge(
            self,
            surface=surface,
            arena=arena,
            actor=actor,
            x=x,
            y=y,
            width=width,
            show_commit_tick=show_commit_tick,
        )

    def _draw_hud(
        self,
        surface: pygame.Surface,
        arena,
        party: Sequence,
        enemies: Sequence,
        phase,
        ui_mode,
        active_index: int,
        hover_id: str | None,
        party_rect: pygame.Rect,
        enemy_rect: pygame.Rect,
    ) -> None:
        return draw_hud(
            self,
            surface=surface,
            arena=arena,
            party=party,
            enemies=enemies,
            phase=phase,
            ui_mode=ui_mode,
            active_index=active_index,
            hover_id=hover_id,
            party_rect=party_rect,
            enemy_rect=enemy_rect,
        )

    def _render_status_pips(
        self,
        surface: pygame.Surface,
        actor: Any,
        buff_x: int,
        debuff_x: int,
        row_center_y: int,
        mode: str,
    ) -> None:
        return render_status_pips(
            self,
            surface=surface,
            actor=actor,
            buff_x=buff_x,
            debuff_x=debuff_x,
            row_center_y=row_center_y,
            mode=mode,
        )

    # ------------------------------------------------------------------
    # Root menu options
    # ------------------------------------------------------------------
    def _get_root_menu_options(self, actor, skills):
        return get_root_menu_options(actor, skills)

    def _draw_tactical_popup(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        tactical_index: int,
        flee_allowed: bool,
        can_swap: bool,
    ) -> None:
        return draw_tactical_popup(
            self,
            surface=surface,
            rect=rect,
            tactical_index=tactical_index,
            flee_allowed=flee_allowed,
            can_swap=can_swap,
        )

    def _draw_skill_menu(
        self,
        surface: pygame.Surface,
        arena,
        phase,
        ui_mode: str,
        actor,
        skills,
        menu_index: int,
        rect: pygame.Rect,
    ) -> None:
        return draw_skill_menu(
            self,
            surface=surface,
            arena=arena,
            phase=phase,
            ui_mode=ui_mode,
            actor=actor,
            skills=skills,
            menu_index=menu_index,
            rect=rect,
        )

    def _draw_weapons_menu(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        arena: "BattleArena",
        actor: object,
    ) -> None:
        return draw_weapons_menu(self, surface=surface, rect=rect, arena=arena, actor=actor)

    def _draw_message_box(self, surface, message, rect):
        return draw_message_box(self, surface=surface, message=message, rect=rect)

    # ------------------------------------------------------------------
    # Input handling (menu navigation)
    # ------------------------------------------------------------------
    def handle_key(self, key, controller, actor, skills):
        # Transitional: input has moved to UIFlow.
        return False, None
