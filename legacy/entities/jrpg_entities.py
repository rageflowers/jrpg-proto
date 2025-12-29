# jrpg_entities.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Sequence, Optional
import math

# ===========================
# Core Data Models
# ===========================

@dataclass
class Stats:
    max_hp: int
    phys_attack: int
    mag_attack: int
    phys_defense: int
    mag_defense: int
    speed: int
    max_mp: int = 0

    def clamp(self) -> None:
        self.max_hp = max(1, self.max_hp)
        self.phys_attack = max(1, self.phys_attack)
        self.mag_attack = max(0, self.mag_attack)
        self.phys_defense = max(0, self.phys_defense)
        self.mag_defense = max(0, self.mag_defense)
        self.speed = max(1, self.speed)
        self.max_mp = max(0, self.max_mp)

@dataclass
class Weapon:
    name: str
    phys_damage: int
    mag_damage: int
    modifiers: Dict[str, float] = field(default_factory=dict)
    flavor_text: str = ""

    def apply_modifiers(self, base_stats: Stats) -> Stats:
        s = Stats(**vars(base_stats))
        for key, mult in self.modifiers.items():
            if hasattr(s, key):
                setattr(s, key, int(getattr(s, key) * mult))
        s.clamp()
        return s

@dataclass
class Status:
    name: str
    duration: int
    on_turn_end: Optional[Callable[["Actor"], None]] = None

    def tick(self, actor: "Actor") -> None:
        if self.on_turn_end:
            self.on_turn_end(actor)
        self.duration -= 1

@dataclass
class Actor:
    name: str
    stats: Stats
    hp: int = field(init=False)
    mp: int = field(init=False)
    level: int = 1
    is_undead: bool = False
    statuses: List[Status] = field(default_factory=list)
    actions: Sequence[str] = field(default_factory=list)
    weapon: Optional[Weapon] = None
    tempo: int = 0  # NEW: -4 to +4 combat rhythm

    def __post_init__(self) -> None:
        self.stats.clamp()
        if self.weapon:
            self.stats = self.weapon.apply_modifiers(self.stats)
        self.hp = self.stats.max_hp
        self.mp = self.stats.max_mp

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        dmg = max(0, int(amount))
        self.hp = max(0, self.hp - dmg)
        return dmg

    def heal(self, amount: int) -> int:
        healed = max(0, int(amount))
        self.hp = min(self.stats.max_hp, self.hp + healed)
        return healed

    def cleanup_status(self) -> None:
        self.statuses = [s for s in self.statuses if s.duration > 0]

    # NEW: tempo helper
    def adjust_tempo(self, delta: int, cap: int = 4) -> None:
        self.tempo = max(-cap, min(cap, self.tempo + delta))

# optional tiny helpers if you want them later:
def add_status(actor: Actor, name: str, duration: int,
               on_turn_end: Optional[Callable[[Actor], None]] = None) -> None:
    actor.statuses.append(Status(name=name, duration=duration, on_turn_end=on_turn_end))

def has_status(actor: Actor, name: str) -> bool:
    return any(s.name == name for s in actor.statuses)

# ===========================
# Temporary stat mods (for later)
# ===========================

def apply_temp_mod(actor: Actor, field: str, delta: int, name: str, duration: int) -> None:
    if not hasattr(actor.stats, field):
        return

    setattr(actor.stats, field, max(0, getattr(actor.stats, field) + delta))

    def on_end(v: Actor) -> None:
        setattr(v.stats, field, max(0, getattr(v.stats, field) - delta))

    actor.statuses.append(Status(name=name, duration=duration, on_turn_end=on_end))

def apply_dual_mod(actor: Actor, mods: Dict[str, int], name: str, duration: int) -> None:
    for field, delta in mods.items():
        apply_temp_mod(actor, field, delta, name, duration)

# ===========================
# Party & Enemy Factory
# ===========================

def create_party() -> List[Actor]:
    """Initial player party: Setia, Nyra, Kaira."""
    rosary = Weapon(
        name="Rosary of Aether",
        phys_damage=3,
        mag_damage=2,
        modifiers={"phys_attack": 1.1, "mag_attack": 1.05},
    )
    celestial_staff = Weapon(
        name="Celestial Staff",
        phys_damage=1,
        mag_damage=4,
        modifiers={"mag_attack": 1.2},
    )
    eclipsed_fang = Weapon(
        name="Eclipsed Fang",
        phys_damage=4,
        mag_damage=2,
        modifiers={"phys_attack": 1.15, "mag_attack": 1.1},
    )

    setia = Actor(
        name="Setia",
        stats=Stats(max_hp=34, phys_attack=9, mag_attack=4,
                    phys_defense=4, mag_defense=3, speed=7, max_mp=6),
        weapon=rosary,
        actions=("Weapon Attack", "Palm of Aether"),
        level=3,
    )
    nyra = Actor(
        name="Nyra",
        stats=Stats(max_hp=26, phys_attack=4, mag_attack=7,
                    phys_defense=2, mag_defense=4, speed=6, max_mp=12),
        weapon=celestial_staff,
        actions=("Weapon Attack", "Lunar Grace", "Divine Ray"),
        level=3,
    )
    kaira = Actor(
        name="Kaira",
        stats=Stats(max_hp=22, phys_attack=6, mag_attack=7,
                    phys_defense=2, mag_defense=2, speed=9, max_mp=8),
        weapon=eclipsed_fang,
        actions=("Weapon Attack", "Shadow Flare"),
        level=3,
    )
    return [setia, nyra, kaira]


def create_enemy_group(encounter_id: str) -> List[Actor]:
    """Very simple enemy presets for now."""
    if encounter_id == "tutorial":
        return [
            Actor(
                name="Ash Wraith",
                stats=Stats(max_hp=18, phys_attack=6, mag_attack=3,
                            phys_defense=2, mag_defense=1, speed=5),
                is_undead=True,
                actions=("Weapon Attack",),
                weapon=Weapon("Bone Shard", phys_damage=3, mag_damage=0),
                level=1,
            )
        ]
    elif encounter_id == "behemoth_trial":
        return [
            Actor(
                name="Nether Behemoth",
                stats=Stats(max_hp=80, phys_attack=10, mag_attack=8,
                            phys_defense=4, mag_defense=3, speed=4),
                is_undead=False,
                actions=("Weapon Attack",),
                weapon=Weapon("Void Claw", phys_damage=5, mag_damage=0),
                level=5,
            )
        ]
    else:
        # Default mook
        return [
            Actor(
                name="Feral Riftling",
                stats=Stats(max_hp=14, phys_attack=5, mag_attack=2,
                            phys_defense=1, mag_defense=1, speed=6),
                actions=("Weapon Attack",),
                weapon=Weapon("Claws", phys_damage=2, mag_damage=0),
                level=1,
            )
        ]
