"""
engine/battle/skills/registry.py

Central registry for all skills in the battle system.

This module:
  - Holds a global registry of SkillDefinition objects.
  - Provides helpers to register and fetch skills.
  - Provides builder functions to define character and shared skills.

It is purely logical: no pygame, no visual FX logic.
"""

from __future__ import annotations
from typing import Any, Dict, List
from .base import SkillMeta, SkillDefinition

from .setia import register_setia_skills
from .nyra import register_nyra_skills
from .kaira import register_kaira_skills
from .shared import register_shared_skills
from .elemental import register_elemental_skills   # NEW: elemental spell book
from . import enemy_skills  # add this near the top of registry.py
from .effects import DamageEffect  # add this near the top with other imports

# ---------------------------------------------------------------------------
# Global registry
# ---------------------------------------------------------------------------

_SKILLS: Dict[str, SkillDefinition] = {}
_INITIALIZED: bool = False


def register(skill_def: SkillDefinition) -> None:
    """Register a skill in the global registry."""
    skill_id = skill_def.meta.id
    if skill_id in _SKILLS:
        # Overwrite for now (you can tighten this later if desired).
        pass
    _SKILLS[skill_id] = skill_def


def get(skill_id: str) -> SkillDefinition:
    """Retrieve a skill definition by id."""
    return _SKILLS[skill_id]


def get_for_user(user_name: str) -> List[SkillDefinition]:
    """
    Return all skills available to a given battler.

    - For player characters (Setia, Nyra, Kaira):
        return all skills registered for that user + shared skills.
    - For enemies (everyone else):
        return only skills registered explicitly for that user.

    This ensures enemies never gain access to 'shared' skills
    like Items / Defend, and only use what is defined in
    enemy_skills.py (or other enemy-specific modules).
    """
    uname = user_name.lower()
    result: List[SkillDefinition] = []

    # Hard-coded for now; can later be driven by a config or Combatant flag.
    PLAYER_USERS = {"setia", "nyra", "kaira"}

    if uname in PLAYER_USERS:
        # Player characters: personal + shared
        for s in _SKILLS.values():
            u = s.meta.user.lower()
            if u == uname or u == "shared":
                result.append(s)
    else:
        # Enemies (and any non-player): personal only, no shared skills
        for s in _SKILLS.values():
            if s.meta.user.lower() == uname:
                result.append(s)
    
    return result


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def initialize_defaults() -> None:
    """
    Populate the registry with all known skills.

    Call this once at game startup (before entering any battles).
    Subsequent calls are ignored unless you explicitly want to rebuild
    the registry.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return

    # Local adapter so our per-character modules don't need to know
    # about the global _SKILLS dict.
    def _reg(skill_def: SkillDefinition) -> None:
        register(skill_def)

    # Order:
    #   1) Shared skills (Items, Defend, etc.)
    #   2) Elemental spells for trio
    #   3) Character-specific kits
    register_shared_skills(_reg)
    register_elemental_skills(_reg)
    register_setia_skills(_reg)
    register_nyra_skills(_reg)
    register_kaira_skills(_reg)
    # Enemy skills
    enemy_skills.register_enemy_basic_skills(_reg)

    _INITIALIZED = True


# ---------------------------------------------------------------------------
# Debug Helpers – Forge XIII.6
# ---------------------------------------------------------------------------

def debug_dump_skills() -> None:
    """
    Print a detailed summary of every registered SkillDefinition.
    Non-invasive, safe to call anytime. Purely informational.
    """
    if not _SKILLS:
        print("[debug] No skills registered.")
        return

    print("\n=== DEBUG: Skill Registry Dump ===")
    for skill_id, skill_def in _SKILLS.items():
        meta: SkillMeta = skill_def.meta  # ← your line, exactly

        # Try to introspect base_damage / damage_type from the first DamageEffect
        base_damage = None
        damage_type = None
        element = getattr(meta, "element", None)

        for eff in getattr(skill_def, "effects", []) or []:
            if isinstance(eff, DamageEffect):
                base_damage = getattr(eff, "base_damage", None)
                damage_type = getattr(eff, "damage_type", None)
                break

        print(f"- id: {meta.id}")
        print(f"  name: {getattr(meta, 'name', None)}")
        print(f"  user: {getattr(meta, 'user', None)}")
        print(f"  category: {getattr(meta, 'category', None)}")
        print(f"  target_type: {getattr(meta, 'target_type', None)}")
        print(f"  element: {element}")
        print(f"  damage_type: {damage_type}")
        print(f"  base_damage: {base_damage}")
        print(f"  mp_cost: {getattr(meta, 'mp_cost', None)}")
        print(f"  tier: {getattr(meta, 'tier', None)}")
        print(f"  tags: {getattr(meta, 'tags', None)}")
        print("")
    print("=== END DEBUG DUMP ===\n")
