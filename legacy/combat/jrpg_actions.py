# jrpg_actions.py

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Dict, Tuple
import random
import math

from legacy.entities.jrpg_entities import Actor, add_status, has_status

# ===========================
# Elements
# ===========================

class Element(Enum):
    NONE = auto()
    HOLY = auto()
    SHADOW = auto()
    FIRE = auto()
    WATER = auto()

# ===========================
# Hit & Damage Helpers
# ===========================

def roll_hit(attacker: Actor, defender: Actor, attack_type: str) -> bool:
    """
    Unified hit check for phys & magic.
    - Uses base chance
    - Adjusts by tempo
    - Lightly by speed difference
    """
    if attack_type == "phys":
        base = 0.92
    else:
        base = 0.97

    # tempo: attacker sharp, defender evasive when high
    tempo_mod = 0.02 * attacker.tempo - 0.02 * max(0, defender.tempo)

    # speed difference: every 5 points = +/-1%
    spd_diff = attacker.stats.speed - defender.stats.speed
    speed_mod = 0.01 * (spd_diff // 5)

    hit_chance = base + tempo_mod + speed_mod
    hit_chance = max(0.60, min(0.99, hit_chance))

    return random.random() <= hit_chance

def get_element_multiplier(attacker: Actor, defender: Actor, element: Element) -> float:
    """
    Elemental resonance hooks:
    - Simple mark-based buffs. Easy to expand later.
    """
    mult = 1.0

    if element == Element.HOLY and has_status(defender, "Holy Mark"):
        mult *= 1.25
    if element == Element.SHADOW and has_status(defender, "Shadow Mark"):
        mult *= 1.25
    if element == Element.FIRE and has_status(defender, "Burning Brand"):
        mult *= 1.25
    if element == Element.WATER and has_status(defender, "Drenched"):
        mult *= 1.25

    return mult

def _calc_damage(attacker: Actor, defender: Actor,
                 power: float, attack_type: str,
                 element: Element) -> int:
    if attack_type == "phys":
        base = attacker.stats.phys_attack + (attacker.weapon.phys_damage if attacker.weapon else 0)
        defense = defender.stats.phys_defense
    else:
        base = attacker.stats.mag_attack + (attacker.weapon.mag_damage if attacker.weapon else 0)
        defense = defender.stats.mag_defense

    eff = max(1, int(base * power) - defense)
    eff = max(1, int(eff * get_element_multiplier(attacker, defender, element)))
    return eff

def _roll_damage(attacker: Actor, defender: Actor,
                 power: float, attack_type: str,
                 element: Element,
                 var_low: float = 0.9, var_high: float = 1.1,
                 min_floor: int = 1) -> Tuple[int, str]:
    base = _calc_damage(attacker, defender, power, attack_type, element)
    min_roll = max(min_floor, int(base * var_low))
    max_roll = max(min_floor, int(base * var_high))
    variance = random.uniform(var_low, var_high)
    dmg = max(min_floor, int(base * variance))

    tag = ""
    if dmg >= max_roll:
        tag = "CRITICAL"
    elif dmg <= min_roll:
        tag = "GLANCE" if attack_type == "phys" else "DIFFUSED"
    return dmg, tag

# ===========================
# Action Model
# ===========================

@dataclass
class Action:
    name: str
    perform: Callable[[Actor, Actor], str]
    mp_cost: int = 0
    target_allies: bool = False

# ===========================
# Concrete Actions
# ===========================

def weapon_attack(attacker: Actor, defender: Actor) -> str:
    if not roll_hit(attacker, defender, "phys"):
        attacker.adjust_tempo(-1)
        return f"{attacker.name} attacks, but MISSES!"
    dmg, tag = _roll_damage(attacker, defender, base_damage=1.0,
                            attack_type="phys", element=Element.NONE)
    dealt = defender.take_damage(dmg)
    weap = attacker.weapon.name if attacker.weapon else "fists"
    if tag == "CRITICAL":
        attacker.adjust_tempo(+2)
    elif tag in ("GLANCE", "DIFFUSED"):
        attacker.adjust_tempo(-1)
    else:
        attacker.adjust_tempo(+1)
    suffix = f" ({tag}!)" if tag else ""
    return f"{attacker.name} attacks with {weap}! {defender.name} takes {dealt} damage{suffix}."

def palm_of_aether(attacker: Actor, defender: Actor) -> str:
    if not roll_hit(attacker, defender, "phys"):
        attacker.adjust_tempo(-1)
        return f"{attacker.name} channels the Palm of Aether... but MISSES!"
    dmg, tag = _roll_damage(attacker, defender, base_damage=1.3,
                            attack_type="phys", element=Element.NONE,
                            var_low=0.95, var_high=1.05)
    dealt = defender.take_damage(dmg)
    if tag == "CRITICAL":
        attacker.adjust_tempo(+2)
    elif tag in ("GLANCE", "DIFFUSED"):
        attacker.adjust_tempo(-1)
    else:
        attacker.adjust_tempo(+1)
    suffix = f" ({tag}!)" if tag else ""
    return f"{attacker.name} channels the Palm of Aether! {defender.name} takes {dealt} damage{suffix}."

def divine_ray(attacker: Actor, defender: Actor) -> str:
    if not roll_hit(attacker, defender, "mag"):
        attacker.adjust_tempo(-1)
        return f"{attacker.name} calls down Divine Ray, but it fizzles wide!"
    dmg, tag = _roll_damage(attacker, defender, base_damage=1.1,
                            attack_type="mag", element=Element.HOLY,
                            var_low=0.95, var_high=1.05, min_floor=3)
    if defender.is_undead:
        dmg *= 2
    dealt = defender.take_damage(dmg)
    if tag == "CRITICAL":
        attacker.adjust_tempo(+2)
        add_status(defender, "Holy Mark", duration=2)
    elif tag in ("GLANCE", "DIFFUSED"):
        attacker.adjust_tempo(-1)
    else:
        attacker.adjust_tempo(+1)
        # small holy mark chance
        if random.random() < 0.25:
            add_status(defender, "Holy Mark", duration=2)
    suffix = f" ({tag}!)" if tag else ""
    undead_txt = " It burns the Undead!" if defender.is_undead else ""
    return f"{attacker.name} calls down Divine Ray! {defender.name} takes {dealt} holy damage{suffix}.{undead_txt}"

def lunar_grace(attacker: Actor, ally: Actor) -> str:
    # support skills don't miss in this version
    base = max(3, attacker.stats.mag_attack + 4)
    healed = ally.heal(base)
    attacker.adjust_tempo(+1)
    return f"{attacker.name}'s Lunar Grace restores {healed} HP to {ally.name}."

def shadow_flare(attacker: Actor, defender: Actor) -> str:
    if not roll_hit(attacker, defender, "mag"):
        attacker.adjust_tempo(-1)
        return f"{attacker.name} unleashes Shadow Flare, but it dissipates harmlessly!"
    dmg, tag = _roll_damage(attacker, defender, base_damage=1.5,
                            attack_type="mag", element=Element.SHADOW,
                            var_low=0.5, var_high=1.5)
    dealt = defender.take_damage(dmg)
    # Tempo reaction
    if tag == "CRITICAL":
        attacker.adjust_tempo(+2)
    elif tag == "DIFFUSED":
        attacker.adjust_tempo(-1)
    else:
        attacker.adjust_tempo(+1)

    # On-hit procs: Shadow Mark & Burning Brand chance
    if dealt > 0:
        if random.random() < 0.40:
            add_status(defender, "Shadow Mark", duration=2)
        if random.random() < 0.20:
            add_status(defender, "Burning Brand", duration=2)

    suffix = f" ({tag}!)" if tag else ""
    return f"{attacker.name} unleashes Shadow Flare! {defender.name} takes {dealt} damage{suffix}."

# Placeholder: Slow Hand (non-elemental control)
def slow_hand(attacker: Actor, defender: Actor) -> str:
    if not roll_hit(attacker, defender, "phys"):
        attacker.adjust_tempo(-1)
        return f"{attacker.name} reaches with a Slow Hand, but MISSES!"
    dmg, tag = _roll_damage(attacker, defender, base_damage=0.8,
                            attack_type="phys", element=Element.NONE)
    dealt = defender.take_damage(dmg)
    # Always apply Slow (simple SPD debuff status)
    def restore_spd(v: Actor):
        v.stats.speed += 1
    # apply -1 SPD for 2 turns
    defender.stats.speed = max(1, defender.stats.speed - 1)
    add_status(defender, "Slow", duration=2, on_turn_end=restore_spd)
    attacker.adjust_tempo(+1 if tag != "GLANCE" else -1)
    suffix = f" ({tag}!)" if tag else ""
    return f"{attacker.name}'s Slow Hand hinders {defender.name}! {dealt} damage{suffix}, speed reduced."

# Placeholder: Serpent Slash (Water-flavored, DoT + tempo shred)
def serpent_slash(attacker: Actor, defender: Actor) -> str:
    if not roll_hit(attacker, defender, "phys"):
        attacker.adjust_tempo(-1)
        return f"{attacker.name} strikes with Serpent Slash, but MISSES!"
    dmg, tag = _roll_damage(attacker, defender, base_damage=1.0,
                            attack_type="phys", element=Element.WATER)
    dealt = defender.take_damage(dmg)
    # Apply Drenched mark for water resonance
    if dealt > 0:
        add_status(defender, "Drenched", duration=3)
        # simple DoT for 3 turns
        def serpent_dot(v: Actor):
            if v.alive:
                v.take_damage(2)
        add_status(defender, "Serpent Venom", duration=3, on_turn_end=serpent_dot)
        # tempo shred
        defender.tempo = max(-4, defender.tempo - 1)
    if tag == "CRITICAL":
        attacker.adjust_tempo(+2)
    elif tag == "GLANCE":
        attacker.adjust_tempo(-1)
    else:
        attacker.adjust_tempo(+1)
    suffix = f" ({tag}!)" if tag else ""
    return f"{attacker.name}'s Serpent Slash drenches {defender.name}! {dealt} damage{suffix}, Tempo and tide turned."

# ===========================
# Registry
# ===========================

ACTIONS: Dict[str, Action] = {
    "Weapon Attack": Action("Weapon Attack", weapon_attack, mp_cost=0, target_allies=False),
    "Palm of Aether": Action("Palm of Aether", palm_of_aether, mp_cost=2, target_allies=False),
    "Divine Ray": Action("Divine Ray", divine_ray, mp_cost=5, target_allies=False),
    "Lunar Grace": Action("Lunar Grace", lunar_grace, mp_cost=4, target_allies=True),
    "Shadow Flare": Action("Shadow Flare", shadow_flare, mp_cost=3, target_allies=False),
    # Optional: hook in new moves when you're ready
    "Slow Hand": Action("Slow Hand", slow_hand, mp_cost=2, target_allies=False),
    "Serpent Slash": Action("Serpent Slash", serpent_slash, mp_cost=3, target_allies=False),
}
