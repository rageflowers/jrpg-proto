from __future__ import annotations

from typing import List, Optional, Any


class BattleCommand:
    """
    Unified command intent object:
        - actor_id
        - command_type (attack, defend, escape, skill, item, etc.)
        - skill_id / item_id
        - target_ids
        - optional flags (multi-target, alt mode)
    """

    def __init__(
        self,
        *,
        actor_id: str,
        command_type: str,
        skill_id: Optional[str] = None,
        item_id: Optional[str] = None,
        target_ids: Optional[List[str]] = None,
        flags: Optional[dict] = None,
    ) -> None:
        self.actor_id = actor_id
        self.command_type = command_type
        self.skill_id = skill_id
        self.item_id = item_id
        self.target_ids = target_ids or []
        self.flags = flags or {}


class BattleInputHandler:
    """
    Handles all player-facing menus and targeting.

    Responsibilities (later phases):
        - main action menu (Attack / Skill / Item / Defend / Flee)
        - left-triggered popup (Defend / Flee)
        - left from Item menu -> weapon swap popup
        - free-movement target selection
        - backtracking logic
        - CTB freeze when menus are open

    Phase XVII.0.4:
        Only define structure and placeholders. No input or UI implemented.
    """

    STATE_IDLE = "idle"
    STATE_MENU = "menu"
    STATE_TARGETING = "targeting"
    STATE_POPUP = "popup"

    def __init__(self, session):
        self.session = session
        self.state = self.STATE_IDLE

        # The actor currently choosing a command
        self.active_actor_id: Optional[str] = None

    # ------------------------------------------------------------------ #
    #  High-level entry API (called by ActionMapper once actor is ready)
    # ------------------------------------------------------------------ #

    def request_player_command(self, actor_id: str) -> Optional[BattleCommand]:
        """
        Called by ActionMapper when a party actor enters their turn.

        Eventually:
            - open the main menu
            - freeze CTB
            - wait for input events
            - produce a BattleCommand

        For XVII.0.4:
            Return None as placeholder.
        """
        self.active_actor_id = actor_id
        self.state = self.STATE_MENU
        return None

    # ------------------------------------------------------------------ #
    #  Targeting, popups, backtracking will be added in later phases
    # ------------------------------------------------------------------ #

    def cancel(self) -> None:
        """
        Placeholder for backtracking.
        """
        self.state = self.STATE_MENU

    def clear(self) -> None:
        """Reset the handler for the next actor."""
        self.active_actor_id = None
        self.state = self.STATE_IDLE
