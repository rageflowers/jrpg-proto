import random

from engine.battle.status.manager import StatusManager


def _format_status_debug(owner) -> str:
    """Return a best-effort textual summary of a combatant's active statuses."""
    name = getattr(owner, "name", "<?>")
    mgr = getattr(owner, "status", None)

    if mgr is None:
        return f"{name}: [no status manager]"

    # Common patterns: .effects (preferred) or older containers.
    raw = getattr(mgr, "effects", None)
    if raw is None:
        raw = getattr(mgr, "statuses", None)
    if raw is None:
        raw = getattr(mgr, "active_statuses", None)

    entries: list[str] = []
    if isinstance(raw, dict):
        iterable = raw.values()
    elif isinstance(raw, (list, tuple, set)):
        iterable = raw
    else:
        iterable = []

    for st in iterable:
        sid = (
            getattr(st, "icon_id", None)
            or getattr(st, "id", None)
            or getattr(st, "name", None)
            or st.__class__.__name__
        )
        remaining = (
            getattr(st, "remaining_turns", None)
            or getattr(st, "duration", None)
            or getattr(st, "turns", None)
        )
        if remaining is not None:
            entries.append(f"{sid}({remaining})")
        else:
            entries.append(str(sid))

    if not entries:
        return f"{name}: [no statuses]"

    return f"{name}: " + ", ".join(entries)


def _get_status_icons_from_effects(owner) -> list[dict]:
    """
    Build HUD icon descriptors for a combatant's active status effects.

    Each descriptor is a tiny dict:
        {
            "type": "buff" | "debuff" | "dot",
            "status_id": <asset_id>,
            "stacks": int (optional, only if > 1),
        }

    Reads from StatusManager.effects. If not present, returns [] (HUD stays safe).
    """
    status_mgr = getattr(owner, "status", None)
    if status_mgr is None:
        return []

    effects = getattr(status_mgr, "effects", None) or []
    counts: dict[tuple[str, str], int] = {}

    for eff in effects:
        icon_type = getattr(eff, "icon_type", None)
        icon_id = getattr(eff, "icon_id", None)
        if not icon_type or not icon_id:
            continue
        key = (str(icon_type), str(icon_id))
        counts[key] = counts.get(key, 0) + 1

    icons: list[dict] = []
    for (icon_type, icon_id) in sorted(counts.keys()):
        count = counts[(icon_type, icon_id)]
        entry: dict = {"type": icon_type, "status_id": icon_id}
        if count > 1:
            entry["stacks"] = count
        icons.append(entry)

    return icons


class PlayerCombatant:
    def __init__(
        self,
        name: str,
        max_hp: int,
        sprite,
        max_mp: int = 0,
        *,
        level: int = 1,
        stats: dict | None = None,
    ):
        self.name = name
        self.max_hp = int(max_hp)
        self.hp = int(max_hp)

        self.max_mp = int(max_mp)
        self.mp = int(max_mp)

        self.level = int(level)
        self.stats = stats or {}

        self.sprite = sprite
        self.status = StatusManager(self)

        # Optional: hit flash timer (used if sprite doesn't handle it)
        self.hit_flash = 0.0

        def _get(key: str, default: int) -> int:
            val = self.stats.get(key, default)
            try:
                return int(val)
            except Exception:
                return int(default)

        self.atk = _get("atk", 10)
        self.mag = _get("mag", 10)
        self.defense = _get("def", 8)
        self.res = _get("res", 8)
        self.spd = _get("spd", 10)

    def debug_status_string(self) -> str:
        return _format_status_debug(self)

    def get_status_icons(self) -> list[dict]:
        return _get_status_icons_from_effects(self)

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def set_hp(self, new_hp: int) -> None:
        """Set HP with clamping. (No death FX for players yet.)"""
        self.hp = max(0, min(int(self.max_hp), int(new_hp)))

    def take_damage(self, amount: int) -> None:
        amount = max(0, int(amount))
        self.set_hp(self.hp - amount)

    def heal(self, amount: int) -> None:
        amount = max(0, int(amount))
        self.set_hp(self.hp + amount)


class EnemyCombatant:
    def __init__(self, name: str, max_hp: int, sprite, max_mp: int = 0):
        self.name = name
        self.max_hp = int(max_hp)
        self.hp = int(max_hp)

        self.max_mp = int(max_mp)
        self.mp = int(max_mp)

        self.sprite = sprite
        self.status = StatusManager(self)

        # For hit flash (used by apply_hit_fx if sprite doesn't handle its own)
        self.hit_flash = 0.0

        # For dissolve-on-death
        self.dissolve_time = 0.0            # counts down from dissolve_duration
        self.dissolve_duration = 0.6        # seconds for full fade-out

    def debug_status_string(self) -> str:
        return _format_status_debug(self)

    def get_status_icons(self) -> list[dict]:
        return _get_status_icons_from_effects(self)

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def set_hp(self, new_hp: int) -> None:
        """
        Set HP with clamping.

        Enemy-specific side effect:
            - If HP crosses from alive -> dead, start dissolve.
        """
        was_alive = self.alive
        self.hp = max(0, min(int(self.max_hp), int(new_hp)))
        if was_alive and not self.alive:
            self.dissolve_time = float(self.dissolve_duration)

    def take_damage(self, amount: int) -> None:
        amount = max(0, int(amount))
        self.set_hp(self.hp - amount)

    def attack(self, target, damage_range: tuple[int, int] = (6, 12)) -> int:
        """
        Basic physical attack used by simple enemy AI.

        Returns: raw damage dealt (pre-mitigation is handled elsewhere in the engine).
        """
        base_damage = random.randint(damage_range[0], damage_range[1])

        # Local import to avoid any circular refs with battle systems.
        from engine.battle.damage import compute_damage  # type: ignore

        raw, _breakdown = compute_damage(
            attacker=self,
            defender=target,
            element="physical",
            base_damage=base_damage,
            damage_type="physical",
        )
        return raw


def debug_print_all_statuses(party, enemies) -> None:
    """
    Print status summaries for all party members and enemies.
    Useful from a test harness or debug hotkey.
    """
    print("\n=== DEBUG: Party Statuses ===")
    for i, c in enumerate(party):
        if hasattr(c, "debug_status_string"):
            print(f"[P{i}] {c.debug_status_string()}")
        else:
            print(f"[P{i}] {getattr(c, 'name', '<?>')}: [no debug_status_string]")
    print("=== DEBUG: Enemy Statuses ===")
    for i, e in enumerate(enemies):
        if hasattr(e, "debug_status_string"):
            print(f"[E{i}] {e.debug_status_string()}")
        else:
            print(f"[E{i}] {getattr(e, 'name', '<?>')}: [no debug_status_string]")
    print("=== END STATUS DEBUG ===\n")
