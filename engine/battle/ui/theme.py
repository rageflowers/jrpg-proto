# engine/battle/ui/theme.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

RGB = Tuple[int, int, int]
RGBA = Tuple[int, int, int, int]


@dataclass(frozen=True)
class BattleUITheme:
    """
    Centralized UI constants for battle UI rendering.

    Forge XIX.4/XIX.5 rule:
    - This module is render-only.
    - No pygame imports required.
    - No references to BattleUI or Arena.
    - It should be safe to import from anywhere.
    """

    # ---------- Common panel styling ----------
    panel_fill: RGBA = (20, 18, 28, 235)
    panel_border: RGB = (150, 120, 190)
    dialog_fill: RGBA = (20, 18, 28, 110)

    # Row highlight (menus)
    row_hi_fill: RGB = (90, 70, 130)
    row_hi_border: RGB = (200, 170, 240)

    # Text colors
    text_primary: RGB = (235, 235, 245)
    text_secondary: RGB = (200, 200, 230)
    text_hint: RGB = (180, 180, 200)
    text_dim: RGB = (200, 200, 210)

    # Bars / CTB
    ctb_border: RGB = (140, 110, 190)
    ctb_fill: RGB = (210, 180, 245)
    ctb_tick: RGB = (245, 240, 255)

    # ---------- Geometry ----------
    popup_pad: int = 10
    border_radius: int = 6

    # Menu defaults
    menu_visible_rows_min: int = 3
    menu_visible_rows_max: int = 6


# Single shared theme instance (import and use directly if desired)
THEME = BattleUITheme()
