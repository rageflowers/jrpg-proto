# engine/battle/factories.py (example)

from engine.actors.character_sheet import CharacterInstance
from engine.battle.combatants import PlayerCombatant

def make_player_combatant_from_instance(
    inst: CharacterInstance,
    sprite,
) -> PlayerCombatant:
    s = inst.stats  # StatBlock

    stats_dict = {
        "atk":      s.atk,
        "mag":      s.mag,
        "defense":  s.defense,
        "mres":     s.mres,
        "spd":      s.spd,
    }

    return PlayerCombatant(
        name=inst.name,
        max_hp=s.max_hp,
        sprite=sprite,
        max_mp=s.max_mp,
        level=inst.level,
        stats=stats_dict,
    )
