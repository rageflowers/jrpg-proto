# engine/actors/character_sheet.py

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List


# ------------------------------------------------------------
# Primary Stat Block (canonical)
# ------------------------------------------------------------

@dataclass
class StatBlock:
    """
    Primary combat stats, matching your spec:

      HP   -> max_hp
      MP   -> max_mp
      ATK  -> atk
      MAG  -> mag
      DEF  -> defense
      MRES -> mres
      SPD  -> spd
    """
    max_hp: int
    max_mp: int
    atk: int
    mag: int
    defense: int
    mres: int
    spd: int

# ------------------------------------------------------------
# Growth & XP
# ------------------------------------------------------------

@dataclass
class GrowthCurve:
    """
    Per-level growth for each primary stat.
    Numbers are "growth per level" and can be tuned later.
    """
    hp_per_level: float
    mp_per_level: float
    atk_per_level: float
    mag_per_level: float
    def_per_level: float
    mres_per_level: float
    spd_per_level: float

    def apply(self, base: StatBlock, level: int) -> StatBlock:
        lvl = max(1, level)
        d = lvl - 1

        return StatBlock(
            max_hp=base.max_hp + int(self.hp_per_level * d),
            max_mp=base.max_mp + int(self.mp_per_level * d),
            atk=base.atk + int(self.atk_per_level * d),
            mag=base.mag + int(self.mag_per_level * d),
            defense=base.defense + int(self.def_per_level * d),
            mres=base.mres + int(self.mres_per_level * d),
            spd=base.spd + int(self.spd_per_level * d),
        )


@dataclass
class XPTable:
    """
    Simple XP curve: XP required to go from level -> level+1.
    For now, quadratic-ish.
    """
    max_level: int
    base: int = 40
    step: int = 12

    def xp_to_next(self, level: int) -> int:
        if level >= self.max_level:
            return 0
        lvl = max(1, level)
        return self.base + self.step * (lvl * lvl)

    def build_table(self) -> Dict[int, int]:
        return {lvl: self.xp_to_next(lvl) for lvl in range(1, self.max_level + 1)}

# ------------------------------------------------------------
# Templates & instances
# ------------------------------------------------------------

@dataclass
class CharacterTemplate:
    id: str          # "setia"
    name: str        # "Setia"
    element: str     # "wind" / "light" / "shadow"
    base_stats: StatBlock
    growth: GrowthCurve
    xp_table: XPTable

    def stats_for_level(self, level: int) -> StatBlock:
        return self.growth.apply(self.base_stats, level)

    def xp_to_next(self, level: int) -> int:
        return self.xp_table.xp_to_next(level)


@dataclass
class CharacterInstance:
    """
    Per-save character state.
    This is what will eventually live in your SaveGame.
    """
    template_id: str
    name: str
    level: int
    current_xp: int
    stats: StatBlock

    @classmethod
    def new_from_template(cls, template: CharacterTemplate, level: int = 1) -> "CharacterInstance":
        lvl = max(1, level)
        return cls(
            template_id=template.id,
            name=template.name,
            level=lvl,
            current_xp=0,
            stats=template.stats_for_level(lvl),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "level": self.level,
            "current_xp": self.current_xp,
            "stats": asdict(self.stats),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterInstance":
        stats_data = data.get("stats", {})
        stats = StatBlock(**stats_data)
        return cls(
            template_id=data["template_id"],
            name=data["name"],
            level=int(data["level"]),
            current_xp=int(data.get("current_xp", 0)),
            stats=stats,
        )

    def gain_xp(self, amount: int, template: CharacterTemplate) -> List[int]:
        """
        Add XP and level up as needed.
        Returns list of levels gained (could be multiple).
        """
        gained: List[int] = []
        if amount <= 0:
            return gained

        self.current_xp += int(amount)

        while True:
            needed = template.xp_to_next(self.level)
            if needed <= 0:
                self.current_xp = 0
                break
            if self.current_xp < needed:
                break

            self.current_xp -= needed
            self.level += 1
            self.stats = template.stats_for_level(self.level)
            gained.append(self.level)

        return gained
# ------------------------------------------------------------
# Default trio templates
# ------------------------------------------------------------

def default_templates() -> Dict[str, CharacterTemplate]:
    max_lvl = 50
    common_xp = XPTable(max_level=max_lvl, base=40, step=12)

    # Setia — Wind Monk
    setia = CharacterTemplate(
        id="setia",
        name="Setia",
        element="wind",
        base_stats=StatBlock(
            max_hp=120,
            max_mp=40,
            atk=16,
            mag=6,
            defense=10,
            mres=8,
            spd=18,
        ),
        growth=GrowthCurve(
            hp_per_level=8,    # medium-high HP growth
            mp_per_level=3,    # modest MP
            atk_per_level=3,   # strong ATK growth
            mag_per_level=1,   # slow MAG growth
            def_per_level=2,   # steady DEF
            mres_per_level=1,  # slow MRES
            spd_per_level=3,   # fastest SPD growth
        ),
        xp_table=common_xp,
    )

    # Nyra — Radiant Healer
    nyra = CharacterTemplate(
        id="nyra",
        name="Nyra",
        element="light",
        base_stats=StatBlock(
            max_hp=90,
            max_mp=70,
            atk=6,
            mag=16,
            defense=7,
            mres=14,
            spd=14,
        ),
        growth=GrowthCurve(
            hp_per_level=5,    # slow HP
            mp_per_level=5,    # strong MP growth
            atk_per_level=1,   # slow ATK
            mag_per_level=3,   # strong MAG growth
            def_per_level=1,   # slow DEF
            mres_per_level=3,  # strong MRES
            spd_per_level=2,   # moderate SPD
        ),
        xp_table=common_xp,
    )

    # Kaira — Shadow Catalyst
    kaira = CharacterTemplate(
        id="kaira",
        name="Kaira",
        element="shadow",
        base_stats=StatBlock(
            max_hp=80,
            max_mp=60,
            atk=5,
            mag=17,
            defense=6,
            mres=11,
            spd=16,
        ),
        growth=GrowthCurve(
            hp_per_level=3,    # very slow HP
            mp_per_level=4,    # medium MP
            atk_per_level=0.5, # minimal ATK
            mag_per_level=3.5, # very fast MAG
            def_per_level=0.5, # very slow DEF
            mres_per_level=2,  # medium MRES
            spd_per_level=2.5, # fast SPD, but < Setia
        ),
        xp_table=common_xp,
    )

    return {
        "setia": setia,
        "nyra": nyra,
        "kaira": kaira,
    }

def new_default_party(level: int = 1) -> Dict[str, CharacterInstance]:
    templates = default_templates()
    return {
        cid: CharacterInstance.new_from_template(tpl, level=level)
        for cid, tpl in templates.items()
    }
