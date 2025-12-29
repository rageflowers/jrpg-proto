# engine/battle/skills/kaira.py

from .base import SkillMeta, SkillDefinition
from .effects import DamageEffect, ApplyStatusEffect

# New DoT classes
from engine.battle.status.effects import (
    PoisonStatus,
    BleedStatus,
    BurnStatus,
)


def register_kaira_skills(register_fn):
    """
    Registers all Kaira skills, updated for the new DoT engine.
    Kaira focuses on physical DoTs (Bleed, Poison) and agile offense.
    """

    # ================================================================
    # 1. BASIC ATTACK — remains a damage skill
    # ================================================================
    meta_attack = SkillMeta(
        id="kaira_attack_1",
        name="Slash",
        user="Kaira",
        category="damage",
        element="shadow",
        tier=1,
        mp_cost=0,
        target_type="enemy_single",
        description="A swift, malicious slash.",
        tags={"shadow", "basic"},
        fx_tag="hit_light",
        menu_group="attack",
    )

    attack_def = SkillDefinition(
        meta=meta_attack,
        effects=[
            DamageEffect(base_damage=10, element="shadow")
        ],
    )
    register_fn(attack_def)

    # ================================================================
    # 2. BLOOD CUT — pure Bleed DoT (no upfront damage)
    # ================================================================
    meta_blood_cut = SkillMeta(
        id="kaira_blood_cut_1",
        name="Blood Cut",
        user="Kaira",
        category="dot",
        element="physical",
        tier=1,
        mp_cost=4,
        target_type="enemy_single",
        description="A vicious strike that causes bleeding.",
        tags={"bleed", "dot", "physical"},
        fx_tag="curse_pulse",
        menu_group="arts",
    )

    def bleed_factory(user, target, battle_state):
        # Tier-ready duration: T1 = 2 turns
        duration = 2
        status = BleedStatus(
            id="bleed",
            name="Bleed I",
            duration_turns=duration,
        )
        # Add DOT tags (new system uses tags for detection)
        status.tags.update({"bleed", "dot", "debuff"})
        status.icon_type = "dot"
        status.icon_id = "bleed"
        return status

    blood_cut_def = SkillDefinition(
        meta=meta_blood_cut,
        effects=[
            # No DamageEffect here — pure DoT application
            ApplyStatusEffect(bleed_factory),
        ],
    )
    register_fn(blood_cut_def)

    # ================================================================
    # 3. POISON DAGGER — pure Poison DoT (no upfront damage)
    # ================================================================
    meta_poison_dagger = SkillMeta(
        id="kaira_poison_dagger_1",
        name="Poison Dagger",
        user="Kaira",
        category="dot",
        element="physical",
        tier=1,
        mp_cost=5,
        target_type="enemy_single",
        description="A shadowed stab that leaves venom coursing through the foe.",
        tags={"poison", "dot", "physical", "shadow"},
        fx_tag="curse_pulse",
        menu_group="arts",
    )

    def poison_factory(user, target, battle_state):
        # Tier-ready duration: T1 = 4 turns
        duration = 4
        status = PoisonStatus(
            id="poison",
            name="Poison I",
            duration_turns=duration,
        )
        status.tags.update({"poison", "dot", "debuff"})
        status.icon_type = "dot"
        status.icon_id = "poison"
        return status

    poison_dagger_def = SkillDefinition(
        meta=meta_poison_dagger,
        effects=[
            # again, DoT only — no direct damage component
            ApplyStatusEffect(poison_factory),
        ],
    )
    register_fn(poison_dagger_def)

    # ================================================================
    # (Future skill here)
    # 4. Shadow Curses / Soul Rot / Hex — magical DoTs using Burn engine
    # ================================================================
    # Left empty for future Forge steps.
