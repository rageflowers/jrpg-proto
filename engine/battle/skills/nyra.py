from .base import SkillMeta, SkillDefinition
from .effects import DamageEffect, HealEffect, ApplyStatusEffect
from .statuses import make_affirmation_status, make_affirmation_regen_status


def register_nyra_skills(register_fn):
    # --------------------------------------------------
    # Basic Attack
    # --------------------------------------------------
    meta_attack = SkillMeta(
        id="nyra_attack_1",
        name="Attack",
        user="Nyra",
        category="damage",
        element="physical",  # staff bonk for now; we can holy-ify later
        tier=1,
        mp_cost=0,
        target_type="enemy_single",
        description="A simple staff strike.",
        tags={"basic", "physical"},
        fx_tag="hit_light",
        menu_group="attack",
    )

    attack_def = SkillDefinition(
        meta=meta_attack,
        effects=[DamageEffect(base_damage=10, element="physical")],
    )

    register_fn(attack_def)


    # --------------------------------------------------
    # First Light (T1 Heal)
    # --------------------------------------------------
    meta_first_light = SkillMeta(
        id="nyra_first_light_1",
        name="First Light",
        user="Nyra",
        category="heal",
        element="holy",
        tier=1,
        mp_cost=4,
        target_type="ally_single",
        description="A gentle restoring prayer.",
        tags={"holy", "heal"},
        fx_tag="heal_single",
        menu_group="arts",
    )

    first_light_def = SkillDefinition(
        meta=meta_first_light,
        effects=[HealEffect(base_heal=20)],
    )

    register_fn(first_light_def)

    # --------------------------------------------------
    # Blessing Touch (Regen T1)
    # --------------------------------------------------
    meta_blessing_touch = SkillMeta(
        id="nyra_blessing_touch_1",
        name="Blessing Touch",
        user="Nyra",
        category="buff",
        element="holy",
        tier=1,
        mp_cost=6,  # per your bible
        target_type="ally_single",
        description="Affirming prayer that fortifies defense and kindles gentle regeneration.",
        tags={"holy", "buff", "affirmation"},
        fx_tag="buff_aura",
        menu_group="arts",
    )

    def blessing_def_factory(user, target, battle_state):
        # +10% DEF for 3T (Affirmation I)
        return make_affirmation_status(user, target, battle_state)

    def blessing_regen_factory(user, target, battle_state):
        # Regen (MAG × 0.25) for 3T (Affirmation I)
        return make_affirmation_regen_status(user, target, battle_state)

    blessing_touch_def = SkillDefinition(
        meta=meta_blessing_touch,
        effects=[
            ApplyStatusEffect(blessing_def_factory),
            ApplyStatusEffect(blessing_regen_factory),
        ],
    )


    register_fn(blessing_touch_def)
