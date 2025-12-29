# engine/actors/enemy_sheet.py
#
# Canonical enemy stat sheet, aligned with Character StatBlock:
#
#   max_hp, max_mp
#   atk, mag, defense, mres, spd
#   luck, xp_reward
#
# This replaces the older "strength / vitality / agility" naming to avoid
# confusion and keep heroes + enemies on the same conceptual stat model.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set, Any
from engine.battle.combatants import EnemyCombatant


# ------------------------------------------------------------
# Enemy Stats & Templates
# ------------------------------------------------------------

@dataclass
class EnemyStats:
    max_hp: int
    max_mp: int
    atk: int
    mag: int
    defense: int
    mres: int
    spd: int
    luck: int
    xp_reward: int = 0


@dataclass
class EnemyTemplate:
    id: str
    name: str
    stats: EnemyStats
    max_number: int = 6
    element: str = "none"
    tags: Set[str] = field(default_factory=set)

# ------------------------------------------------------------
# Global enemy template registry
# ------------------------------------------------------------

ENEMY_TEMPLATES: Dict[str, EnemyTemplate] = {}


def register_enemy_template(tpl: EnemyTemplate) -> None:
    """
    Register an EnemyTemplate by id.

    Idempotent: if the id already exists, we keep the first registration.
    (This prevents double-registration spam when packs are loaded multiple times.)
    """
    tid = getattr(tpl, "id", None)
    if not tid:
        raise ValueError("EnemyTemplate missing required field: id")

    if tid in ENEMY_TEMPLATES:
        return

    ENEMY_TEMPLATES[tid] = tpl

def initialize_enemy_templates() -> None:
    # Deprecated: pack loading is region-driven now.
    # Kept for compatibility, but does nothing.
    return

# ------------------------------------------------------------
# Factory: build EnemyCombatant from template
# ------------------------------------------------------------

def spawn_enemy_from_template(
    template: EnemyTemplate,
    *,
    sprite: Any,
    name_suffix: str | None = None,
):
    ...
    s = template.stats
    base_name = template.name
    if name_suffix:
        name = f"{base_name} {name_suffix}"
    else:
        name = base_name

    enemy = EnemyCombatant(
        name=name,
        max_hp=s.max_hp,
        sprite=sprite,
        max_mp=s.max_mp,
    )

    # Core combat stats
    enemy.atk = int(s.atk)
    enemy.mag = int(s.mag)
    enemy.defense = int(s.defense)
    enemy.mres = int(s.mres)
    enemy.spd = int(s.spd)

    # Luck & XP
    enemy.luck = int(s.luck)
    enemy.xp_reward = int(s.xp_reward)

    # Metadata
    enemy.template_id = template.id
    enemy.element = template.element
    enemy.tags = set(template.tags)

    # 🔑 NEW: canonical name for skill lookup ("Shade", "Shade Brute", "Shade Adept")
    enemy.skill_user_key = base_name

    return enemy

