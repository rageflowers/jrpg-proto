# engine/battle/ui/status_pips.py
from __future__ import annotations

import pygame
from typing import Any

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

def render_status_pips(
    ui,  # BattleUI instance
    *,
    surface: pygame.Surface,
    actor: Any,
    buff_x: int,
    debuff_x: int,
    row_center_y: int,
    mode: str,  # keep same semantics as current code
) -> None:
    """
    Render-only status pips.
    Must match BattleUI._render_status_pips exactly.
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
            text = ui.font_small.render(buff_str, True, (180, 255, 190))
            surface.blit(
                text,
                (buff_x, row_center_y - text.get_height() // 2),
            )

        if debuff_str:
            text = ui.font_small.render(debuff_str, True, (255, 160, 190))
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
    base_line_h = ui.font_small.get_height()
    line_h = int(base_line_h * scale)

    def _blit_scaled(text: str, color: tuple[int, int, int], x: int, y: int) -> None:
        if not text:
            return
        surf = ui.font_small.render(text, True, color)
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
