from .base import SkillMeta, SkillDefinition
from .effects import DamageEffect, ApplyStatusEffect, ApplyStatusToUserEffect
from .statuses import make_flow_i

SETIA_ATTACK_ID = "setia_attack_1"
SETIA_WIND_STRIKE_ID = "setia_wind_strike_1"
SETIA_BASIC_COEFF = 1.0
WIND_STRIKE_T1_PHYS_COEFF = 0.33
WIND_STRIKE_T1_MAG_COEFF  = 0.22

def register_setia_skills(register_fn):

    # --------------------------------------------------
    # Basic Attack
    # --------------------------------------------------
    meta_attack = SkillMeta(
        id="setia_attack_1",
        name="Attack",
        user="Setia",
        category="damage",
        element="physical",
        tier=1,
        mp_cost=0,
        target_type="enemy_single",
        description="A swift physical strike.",
        tags={"basic", "physical"},
        fx_tag="hit_light",
        menu_group="attack",
    )

    attack_def = SkillDefinition(
        meta=meta_attack,
        effects=[
            DamageEffect(
                base_damage=16,                   # fallback floor
                element="none",
                damage_type="physical",
                scaling="atk",
                coeff=SETIA_BASIC_COEFF,
            )
        ]
    )

    register_fn(attack_def)

    # --------------------------------------------------
    # Wind Strike (T1)
    # --------------------------------------------------
    meta_wind_strike = SkillMeta(
        id="setia_wind_strike_1",
        name="Wind Strike",
        user="Setia",
        category="damage",
        element="wind",
        tier=1,
        mp_cost=40,
        target_type="enemy_single",
        description="A cutting strike infused with wind.",
        tags={"wind", "technique"},
        fx_tag="hit_light",
        menu_group="arts",
    )

    wind_strike_def = SkillDefinition(
        meta=meta_wind_strike,
        effects = [
            DamageEffect(
                base_damage=16,                  # TEMP baseline; we’ll replace with proper scaling later
                element="none",            # "wind" is flavor-only right now
                damage_type="physical",    # existing DamageType field
                scaling="atk",
                coeff=WIND_STRIKE_T1_PHYS_COEFF,
            ),
            DamageEffect(
                base_damage=16,                  # TEMP baseline again
                element="none",
                damage_type="magic",
                scaling="mag",
                coeff=WIND_STRIKE_T1_MAG_COEFF,
            ),
            ApplyStatusToUserEffect(status_factory=make_flow_i),
        ]
    )

    register_fn(wind_strike_def)
