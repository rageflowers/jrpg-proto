# game/debug/debug_logger.py

from __future__ import annotations
from typing import Iterable, Any

# ----------------------------------------------------------------------
# Core debug toggles
# ----------------------------------------------------------------------

DEBUG_ENABLED: bool = True

ENABLED_CATEGORIES: set[str] = {
    "runtime",
    "ctb",
    "enemy_ai",
    "harness",
    "battle",   # new default battle-inspection channel
    "fx",       # for FX event tracing
    "resolver", # ActionResolver mirroring / invariants
}

def enable_categories(*cats: str) -> None:
    ENABLED_CATEGORIES.update(cats)

def disable_categories(*cats: str) -> None:
    for c in cats:
        ENABLED_CATEGORIES.discard(c)

def set_categories(cats: Iterable[str]) -> None:
    global ENABLED_CATEGORIES
    ENABLED_CATEGORIES = set(cats)

def log(category: str, message: str) -> None:
    if not DEBUG_ENABLED:
        return
    if category not in ENABLED_CATEGORIES:
        return
    print(f"[BATTLE {category.upper()}] {message}")


# ----------------------------------------------------------------------
# High-level Battle Debug Helper
# ----------------------------------------------------------------------

class BattleDebug:
    """
    Helper that formats structured debug messages for the battle engine.

    BattleController, BattleRuntime, StatusManager, EventRouter, FXSystem, etc.
    should call these helpers instead of hand-rolling debug strings.
    """

    def __init__(self):
        # No state needed yet; we route via category names.
        ...

    # --------------------------------------------------------------
    # Category shorthands
    # --------------------------------------------------------------
    def runtime(self, msg: str) -> None:
        log("runtime", msg)

    def ctb(self, msg: str) -> None:
        log("ctb", msg)

    def enemy_ai(self, msg: str) -> None:
        log("enemy_ai", msg)

    def fx_event(self, topic: str, payload: dict) -> None:
        log("fx", f"[FX EVENT] topic={topic} payload={payload}")

    # --------------------------------------------------------------
    # Snapshots
    # --------------------------------------------------------------
    def party_snapshot(self, party: Iterable[Any]) -> None:
        rows = []
        for i, c in enumerate(party):
            name = getattr(c, "name", f"P{i}")
            hp = getattr(c, "hp", None)
            max_hp = getattr(c, "max_hp", None)
            mp = getattr(c, "mp", None)
            max_mp = getattr(c, "max_mp", None)
            rows.append(
                f"  [P{i}] {name}: HP {hp}/{max_hp}  MP {mp}/{max_mp}"
            )
        body = "\n".join(rows)
        log("battle", "[PARTY]\n" + body)

    def enemy_snapshot(self, enemies: Iterable[Any]) -> None:
        rows = []
        for i, e in enumerate(enemies):
            name = getattr(e, "name", f"E{i}")
            hp = getattr(e, "hp", None)
            max_hp = getattr(e, "max_hp", None)
            mp = getattr(e, "mp", None)
            max_mp = getattr(e, "max_mp", None)
            rows.append(
                f"  [E{i}] {name}: HP {hp}/{max_hp}  MP {mp}/{max_mp}"
            )
        body = "\n".join(rows)
        log("battle", "[ENEMIES]\n" + body)

    # --------------------------------------------------------------
    # Full battle-state snapshot (formerly debug_print_targets)
    # --------------------------------------------------------------
    def targets_snapshot(self, controller: Any) -> None:
        """
        Port of BattleController.debug_print_targets, but living here so
        the controller file stays slimmer.
        """
        state = getattr(controller, "state", None)
        party = getattr(controller, "party", [])
        enemies = getattr(controller, "enemies", [])
        active_index = getattr(controller, "active_index", 0)
        target_index = getattr(controller, "target_index", 0)
        ally_target_index = getattr(controller, "ally_target_index", 0)

        # Active actor
        actor = None
        if 0 <= active_index < len(party):
            actor = party[active_index]
        actor_name = getattr(actor, "name", None) if actor is not None else None

        # Cursor info (unified cursor aware)
        hover_id = getattr(controller, "_target_hover_id", None)

        cursor_target = None
        if hasattr(controller, "get_cursor_target"):
            cursor_target = controller.get_cursor_target()
        cursor_target_name = getattr(cursor_target, "name", None) if cursor_target else None

        # Derive "side" from the hovered target, if any
        hover_side = None
        if cursor_target is not None:
            if cursor_target in getattr(controller, "enemies", []):
                hover_side = "enemy"
            elif cursor_target in getattr(controller, "party", []):
                hover_side = "party"

        # Enemy target
        enemy_target = None
        if enemies and 0 <= target_index < len(enemies):
            enemy_target = enemies[target_index]
        enemy_target_name = getattr(enemy_target, "name", None) if enemy_target else None

        # Ally target
        ally_target = None
        if party and 0 <= ally_target_index < len(party):
            ally_target = party[ally_target_index]
        ally_target_name = getattr(ally_target, "name", None) if ally_target else None

        # Build the big block
        lines: list[str] = []
        lines.append("=== DEBUG: Battle Targets & State ===")
        lines.append(f"state: {state!r}")
        lines.append(f"active_index: {active_index} / {len(party)}")
        lines.append(f"actor: {actor_name!r}")
        lines.append(
            f"cursor: hover_id={hover_id!r} side={hover_side!r} -> target={cursor_target_name!r}"
        )
        lines.append(
            f"enemy_target_index: {target_index} "
            f"-> target={enemy_target_name!r}"
        )
        lines.append(
            f"ally_target_index: {ally_target_index} "
            f"-> target={ally_target_name!r}"
        )
        lines.append("")
        lines.append("Party:")
        for i, c in enumerate(party):
            hp = getattr(c, "hp", None)
            max_hp = getattr(c, "max_hp", None)
            mp = getattr(c, "mp", None)
            max_mp = getattr(c, "max_mp", None)
            name = getattr(c, "name", f"P{i}")
            lines.append(
                f"  [P{i}] {name}: HP {hp}/{max_hp}  MP {mp}/{max_mp}"
            )

        lines.append("")
        lines.append("Enemies:")
        for i, e in enumerate(enemies):
            hp = getattr(e, "hp", None)
            max_hp = getattr(e, "max_hp", None)
            mp = getattr(e, "mp", None)
            max_mp = getattr(e, "max_mp", None)
            name = getattr(e, "name", f"E{i}")
            lines.append(
                f"  [E{i}] {name}: HP {hp}/{max_hp}  MP {mp}/{max_mp}"
            )

        lines.append("=== END BATTLE DEBUG ===")
        body = "\n".join(lines)
        log("battle", body)
