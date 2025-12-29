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
from typing import Sequence

import pygame

# ------------------------------------------------------------------
# Temporary Forge XIV ASCII pips for buffs/debuffs
# (Later we'll swap these for tiny pixel icons.)
# ------------------------------------------------------------------
BUFF_PIPS = {
    "regen": "+",
    "regeneration": "+",
    "haste": ">",
    "speed_up": ">",
    "flow": ">",
    "shield": "□",
    "shield_fire": "~",
    "shield_ice": "=",
    "barrier": "~",
}

DEBUFF_PIPS = {
    "poison": "†",
    "bleed": "†",
    "burn": "ȉ",
    "frostbite": "ȩ",
    "slow": "<",
    "vuln": "x",
    "vulnerable": "x",
}

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
            self._draw_skill_menu(
                surface,
                arena=arena,
                phase=phase,
                ui_mode=ui_mode,
                actor=active_actor,
                skills=skills,
                menu_index=0,  # legacy param (ignored by _draw_skill_menu)
                rect=menu_rect,
            )

            # Tactical popup overlay (draw-only; UIFlow owns logic)
            if getattr(arena, "ui_flow", None) is not None:
                if arena.ui_flow.state.mode == "tactical":
                    self._draw_tactical_popup(
                        surface,
                        rect=menu_rect,
                        tactical_index=arena.ui_flow.state.tactical_index,
                        flee_allowed=True,  # keep simple for now (spec)
                    )

        # --- Middle dialog / narration strip ---
        self._draw_message_box(surface, message=message, rect=dialog_rect)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _layout_rects(self) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        """
        Compute the layout of the UI panel:

            [ dialog strip ]
            [ menu | party | enemies ]
        """
        outer = self.ui_rect
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

    def _draw_bar(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        width: int,
        height: int,
        ratio: float,
        fill_color: tuple,
        border_color: tuple,
        bg_color: tuple = (25, 15, 35),
        border_radius: int = 5,
    ) -> None:
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
        """
        Draw a thin CTB gauge underline at (x, y) with the given width.

        - Fills left → right according to actor's CTB gauge (0.0–1.0).
        - Optional small commit tick (e.g. at 50%) for player characters.
        """
        # Query CTB ratio from the authoritative owner:
        # BattleArena.runtime.timeline (CTBTimeline).
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

            # Slightly taller and with a little top cap so it pops visually
            top_y = y - 1
            bottom_y = y + gauge_height

            # Vertical stroke
            pygame.draw.line(
                surface,
                (245, 240, 255),
                (tick_x, top_y),
                (tick_x, bottom_y),
                width=1,
            )
            # Tiny horizontal cap
            pygame.draw.line(
                surface,
                (245, 240, 255),
                (tick_x - 2, top_y),
                (tick_x + 2, top_y),
                width=1,
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
        from engine.battle.action_phases import ActionPhase

        """
        Center: party window (up to 4 rows)
        Right:  enemy grid (2 columns × 3 rows).
        """

        # --------------------------------------------------
        # PARTY WINDOW (center column)
        # --------------------------------------------------
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
            name_text = self.font_small.render(actor.name, True, (230, 230, 240))
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

            self._draw_ctb_gauge(
                surface,
                arena,
                actor,
                gauge_x,
                gauge_y,
                gauge_width,
                show_commit_tick=True,   # players: show 50% mark
            )

            # buff / debuff pip columns between name and bars
            self._render_status_pips(
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
            self._draw_bar(
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
            hp_text = self.font_small.render(hp_label, True, (250, 240, 250))
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

            self._draw_bar(
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
            mp_text = self.font_small.render(mp_label, True, (220, 235, 255))
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
            name_text = self.font_small.render(enemy.name, True, (230, 220, 240))
            name_x = cell_x + 4
            name_y = cell_y + 3
            surface.blit(name_text, (name_x, name_y))

            # Enemy CTB gauge underline under the name (no commit tick)
            gauge_margin = 1
            gauge_x = name_x
            gauge_width = cell_rect.width - 8  # inset a bit from the cell border
            gauge_y = name_y + name_text.get_height() + gauge_margin

            self._draw_ctb_gauge(
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
            self._render_status_pips(
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

            self._draw_bar(
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
            hp_text = self.font_small.render(hp_label, True, (245, 230, 245))
            surface.blit(
                hp_text,
                (
                    cell_x + bar_margin_x + (bar_width_e - hp_text.get_width()) // 2,
                    hp_y + (hp_height - hp_text.get_height()) // 2,
                ),
            )


    def _render_status_pips(
        self,
        surface: pygame.Surface,
        actor,
        buff_x: int,
        debuff_x: int,
        row_center_y: int,
        *,
        mode: str = "party",  # "party" or "enemy"
    ) -> None:
        """
        Draw tiny ASCII pips for buffs / debuffs.

        mode="party":
            - buff_str and debuff_str share a single horizontal row
              (buff_col / debuff_col).

        mode="enemy":
            - Row 1: buffs (small in number)
            - Rows 2 & 3: debuffs, split across up to 2 lines so late-game
              enemies can stack lots of ailments without spilling into the HP bar.
            - All enemy pips are rendered at ~2/3 of font_small size.
        """
        icons = []
        if hasattr(actor, "get_status_icons"):
            try:
                icons = actor.get_status_icons() or []
            except Exception:
                icons = []

        buff_tokens: list[str] = []
        debuff_tokens: list[str] = []

        for icon in icons:
            t = str(icon.get("type", "unknown")).lower()
            sid = str(icon.get("status_id", "")).lower()

            # Optional stack count supplied by combatants.get_status_icons().
            stacks = icon.get("stacks", 1)
            try:
                stacks_int = int(stacks)
            except (TypeError, ValueError):
                stacks_int = 1
            if stacks_int < 1:
                stacks_int = 1

            if t == "buff":
                base = BUFF_PIPS.get(sid, "+")
                token = f"{base}{stacks_int}" if stacks_int > 1 else base
                buff_tokens.append(token)
            elif t == "debuff":
                base = DEBUFF_PIPS.get(sid, "x")
                token = f"{base}{stacks_int}" if stacks_int > 1 else base
                debuff_tokens.append(token)
            elif t == "dot":
                base = "†"
                token = f"{base}{stacks_int}" if stacks_int > 1 else base
                debuff_tokens.append(token)

        # Allow more pips for enemies, but cap so we don't go wild.
        max_pips = 8
        buff_tokens = buff_tokens[:max_pips]
        debuff_tokens = debuff_tokens[:max_pips]

        # ----------------------------
        # PARTY MODE: original layout
        # ----------------------------
        if mode == "party":
            buff_str = "".join(buff_tokens)
            debuff_str = "".join(debuff_tokens)

            if buff_str:
                text = self.font_small.render(buff_str, True, (180, 255, 190))
                surface.blit(
                    text,
                    (buff_x, row_center_y - text.get_height() // 2),
                )

            if debuff_str:
                text = self.font_small.render(debuff_str, True, (255, 160, 190))
                surface.blit(
                    text,
                    (debuff_x, row_center_y - text.get_height() // 2),
                )
            return

        # ----------------------------
        # ENEMY MODE: 3-row, 2/3 scale
        # ----------------------------
        import pygame  # ensure local alias

        scale = 2.0 / 3.0
        base_line_h = self.font_small.get_height()
        line_h = int(base_line_h * scale)

        def _blit_scaled(text: str, color: tuple[int, int, int], x: int, y: int) -> None:
            if not text:
                return
            surf = self.font_small.render(text, True, color)
            w, h = surf.get_size()
            scaled = pygame.transform.smoothscale(
                surf,
                (int(w * scale), int(h * scale)),
            )
            surface.blit(scaled, (x, y))

        # Row 1: buffs (typically small count)
        if buff_tokens:
            buff_str = "".join(buff_tokens)
            # a bit above center
            buff_y = row_center_y - int(1.5 * line_h)
            _blit_scaled(buff_str, (180, 255, 190), buff_x, buff_y)

        # Rows 2 & 3: debuffs, split.
        if debuff_tokens:
            row_width = 6  # up to 6 tokens per line
            row1_tokens = debuff_tokens[:row_width]
            row2_tokens = debuff_tokens[row_width:row_width * 2]

            if row1_tokens:
                debuff_str1 = "".join(row1_tokens)
                # around center
                debuff1_y = row_center_y - int(0.1 * line_h)
                _blit_scaled(debuff_str1, (255, 160, 190), buff_x, debuff1_y)

            if row2_tokens:
                debuff_str2 = "".join(row2_tokens)
                # below center
                debuff2_y = row_center_y + int(0.9 * line_h)
                _blit_scaled(debuff_str2, (255, 160, 190), buff_x, debuff2_y)

    # ------------------------------------------------------------------
    # Root menu options
    # ------------------------------------------------------------------
    def _get_root_menu_options(self, actor, skills: Sequence) -> list[tuple[str, str]]:
        """
        Build the list of (label, group_code) for the root menu.

        group_code values:
          - "attack"     → direct basic attack
          - "arts"       → character-specific Martial/Holy/Shadow arts
          - "elemental"  → fire/ice/other elemental spells
          - "item"       → items submenu (stub for now)
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

    def _draw_tactical_popup(
        self,
        surface: pygame.Surface,
        *,
        rect: pygame.Rect,
        tactical_index: int,
        flee_allowed: bool,
    ) -> None:
        """
        Draw the tactical popup (Defend / Flee).

        Rendering only — UIFlow owns the state & selection.
        """
        # Popup size/position: small overlay inside the menu column
        pad = 10
        w = rect.width - pad * 2
        h = 92
        popup = pygame.Rect(rect.x + pad, rect.y + pad, w, h)

        # Backplate
        panel = pygame.Surface(popup.size, pygame.SRCALPHA)
        panel.fill((20, 18, 28, 235))
        surface.blit(panel, popup.topleft)
        pygame.draw.rect(surface, (150, 120, 190), popup, width=2, border_radius=6)

        # Title
        title = self.font_small.render("Tactical", True, (235, 235, 245))
        surface.blit(title, (popup.x + 10, popup.y + 8))

        # Options
        options = ["Defend"]
        if flee_allowed:
            options.append("Flee")

        y0 = popup.y + 32
        line_h = self.font_small.get_height() + 8

        for i, label in enumerate(options):
            row = pygame.Rect(popup.x + 8, y0 + i * line_h, popup.width - 16, line_h - 2)

            # Highlight selected row
            if i == tactical_index:
                pygame.draw.rect(surface, (90, 70, 130), row, border_radius=4)
                pygame.draw.rect(surface, (200, 170, 240), row, width=1, border_radius=4)

            txt = self.font_small.render(label, True, (240, 240, 250))
            surface.blit(txt, (row.x + 8, row.y + 3))

        # Footer hint (optional, tiny)
        hint = self.font_small.render("Z/Enter: confirm   X/Esc: back", True, (180, 180, 200))
        surface.blit(hint, (popup.x + 10, popup.bottom - hint.get_height() - 6))

    def _draw_skill_menu(
        self,
        surface: pygame.Surface,
        *,
        arena,
        phase,
        ui_mode,
        actor,
        skills: Sequence,
        menu_index: int,
        rect: pygame.Rect,
    ) -> None:
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
            text = self.font_small.render(label, True, (230, 230, 240))
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
        header = self.font_small.render(f"{actor.name}'s Turn", True, (230, 230, 240))
        surface.blit(header, (x + 10, y + 8))

        list_y = y + 32
        line_h = 24

        # ------------------------------
        # Root menu vs skills submenu
        # ------------------------------
        if self.menu_layer == "root":
            # ROOT MENU (Attack / Arts / Elemental / Items)
            options = self._get_root_menu_options(actor, skills)
            for i, (label, _group) in enumerate(options):
                is_selected = (i == self.root_index)
                color = (255, 255, 255) if is_selected else (200, 200, 210)
                text = self.font_small.render(label, True, color)
                tx = x + 34
                ty = list_y + i * line_h
                surface.blit(text, (tx, ty))

                if is_selected:
                    cursor = self.font_small.render("▶", True, color)
                    surface.blit(cursor, (x + 10, ty))
            return

        # SKILLS SUBMENU (Arts / Elemental / Items)
        group = self.current_group or "arts"

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
            text = self.font_small.render("No abilities learned yet.", True, (200, 200, 210))
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
        subtitle_text = self.font_small.render(subtitle, True, (210, 210, 230))
        surface.blit(subtitle_text, (x + 10, y + 8 + self.font_small.get_height() + 2))

        # Shift list down a bit to leave room for subtitle
        list_y = y + 32 + self.font_small.get_height() + 6

        # Scrolling window for long lists
        max_visible = 4  # number of entries to show at once
        total = len(grouped)

        # Clamp selection
        self.skills_index = max(0, min(self.skills_index, total - 1))

        # Choose a window such that the selected item is roughly centered
        if total <= max_visible:
            start_index = 0
        else:
            half = max_visible // 2
            start_index = max(0, self.skills_index - half)
            if start_index + max_visible > total:
                start_index = total - max_visible

        visible = grouped[start_index:start_index + max_visible]

        # Draw up/down arrows if there are items above/below the window
        if start_index > 0:
            arrow_up = self.font_small.render("▲", True, (200, 200, 210))
            surface.blit(arrow_up, (x + rect.width - 24, list_y - line_h // 2))

        if start_index + max_visible < total:
            arrow_down = self.font_small.render("▼", True, (200, 200, 210))
            surface.blit(
                arrow_down,
                (x + rect.width - 24, list_y + max_visible * line_h - line_h // 2),
            )

        # Draw the visible slice
        for i, (global_idx, skill) in enumerate(visible):
            is_selected = (start_index + i == self.skills_index)
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

            text = self.font_small.render(label, True, color)

            tx = x + 34
            ty = list_y + i * line_h
            surface.blit(text, (tx, ty))

            if is_selected:
                cursor = self.font_small.render("▶", True, color)
                surface.blit(cursor, (x + 10, ty))

    def _draw_message_box(self, surface: pygame.Surface, message: str, rect: pygame.Rect) -> None:
        """
        Draw the dialog / narration strip in the center band above the HUD.
        """
        pygame.draw.rect(surface, (20, 12, 26), rect, border_radius=8)
        pygame.draw.rect(surface, (110, 80, 150), rect, width=2, border_radius=8)

        msg = message or ""
        words = msg.split(" ")
        lines = []
        current = ""

        for w in words:
            test = (current + " " + w).strip()
            test_surf = self.font_small.render(test, True, (230, 230, 240))
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
            text = self.font_small.render(line, True, (230, 230, 240))
            surface.blit(
                text,
                (rect.x + 10, rect.y + 8 + i * (self.font_small.get_height() + 4)),
            )

    # ------------------------------------------------------------------
    # Input handling (menu navigation)
    # ------------------------------------------------------------------
    def handle_key(self, key, controller, actor, skills):
        # Transitional: input has moved to UIFlow.
        return False, None
