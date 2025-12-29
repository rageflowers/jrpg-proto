# engine/battle/skills/statuses.py

from __future__ import annotations
from typing import Any
from game.debug.debug_logger import log as battle_log
from engine.battle.status.effects import (
    RegenStatus,
    StatBuffStatus,
    IceShieldStatus,
    StatusEffect,
)

"""
Status factories used by skill effects.

These helpers create concrete StatusEffect instances. They are used by
ApplyStatusEffect so that the skill effects module does not need to
import specific status classes.
"""

# ---------------------------------------------------------------------------
# Custom elemental status classes (Burn I, Frostbite I)
# ---------------------------------------------------------------------------

class FrostbiteStatus(StatusEffect):
    """
    Frostbite I:

      - Reduces speed (SPD) by 15%.
      - Increases ICE damage taken by +5%.
    """

    def modify_stat_modifiers(self, modifiers: dict[str, float]) -> None:
        spd_mult = getattr(self, "spd_mult", 0.85)  # -15% SPD
        modifiers["spd_mult"] = modifiers.get("spd_mult", 1.0) * spd_mult

    def on_before_owner_takes_damage(
        self,
        owner: Any,
        amount: int,
        element: str,
        damage_type: str,
        context: Any,
    ):
        # No damage => no retaliation
        if amount <= 0:
            return amount, 0, []

        ice_vuln_mult = getattr(self, "ice_vuln_mult", 1.05)

        # +5% damage taken from ice.
        if element == "ice":
            amount = int(amount * ice_vuln_mult)

        retaliation_events = []

        # Try to discover the attacker from context (supports dict or object contexts)
        attacker = None
        if context is not None:
            if isinstance(context, dict):
                attacker = context.get("attacker") or context.get("source_combatant") or context.get("source")
            else:
                attacker = getattr(context, "attacker", None) or getattr(context, "source_combatant", None) or getattr(context, "source", None)

        # Emit frostbite retaliation as a StatusEvent (no controller mutation)
        if attacker is not None:
            from engine.battle.status.status_events import ApplyStatusEvent
            from engine.battle.skills.statuses import make_frostbite_basic

            retaliation_events.append(
                ApplyStatusEvent(
                    target=attacker,
                    status=make_frostbite_basic(),
                    source_combatant=owner,
                    reason="ice_shield_retaliation",
                )
            )

        return amount, 0, retaliation_events

# ---------------------------------------------------------------------------
# Elemental Shields (Tier 1)
# ---------------------------------------------------------------------------

def make_iceshield_t1(user: Any, target: Any, battle_state: Any) -> StatusEffect:
    """
    Tier 1 Ice Shield:
    """
    status = IceShieldStatus(
        id="ice_shield_1",
        name="Chill Ward",
        duration_turns=3,
        dispellable=True,
        stackable=False,
        phys_reduction=0.15,
        magic_reduction=0.20,
        elemental_heal_ratio=0.25,
        retaliation_kind="frostbite",
        retaliation_chance=1.0,
        tier=1,
    )
    status.tags.update({"shield", "ice", "ice_shield", "elemental_shield", "buff"})
    status.icon_type = "buff"
    status.icon_id = "shield_ice"

    return status
# ---------------------------------------------------------------------------
# Nyra: Affirmation Line
# ---------------------------------------------------------------------------
def make_affirmation_status(user: Any, target: Any, battle_state: Any) -> StatusEffect:
    """
    Nyra's Affirmation line, Tier 1 (Blessing Touch):

      - +10% DEF
      - 3T duration
      - Non-stackable (recasting refreshes instead of stacking)
    """
    buff = StatBuffStatus(
        id="nyra_affirmation_1",
        name="Affirmation I",
        duration_turns=3,
        dispellable=True,
        stackable=False,             # important: no stacking cheese
        mults={"def_mult": 1.10},    # +10% DEF
        adds={},
    )

    if hasattr(buff, "tags"):
        buff.tags.update({"nyra", "buff", "def_up", "affirmation"})

    # HUD pip: use the existing 'holy_ward' pip (or whatever you mapped it to)
    buff.icon_type = "buff"
    
    return buff

def make_affirmation_regen_status(
    user: Any, target: Any, battle_state: Any
) -> StatusEffect:
    """
    Regen component of Affirmation Tier 1 (Blessing Touch):

      - Small Regen = MAG × 0.25
      - 3T duration
      - Non-stackable (recasting refreshes)
    """
    mag = getattr(user, "mag", 0)
    heal = int(mag * 0.25)
    if mag > 0 and heal <= 0:
        heal = 1  # minimum 1 if she has any MAG at all

    regen = RegenStatus(
        id="nyra_affirmation_regen_1",
        name="Affirmation I (Regen)",
        duration_turns=3,
        dispellable=True,
        stackable=False,   # also non-stackable
        heal_per_turn=heal,
    )

    if hasattr(regen, "tags"):
        regen.tags.update({"nyra", "buff", "regen", "affirmation"})

    # HUD pip: basic regen pip (single char)
    regen.icon_type = "buff"
    regen.icon_id = "regen"

    return regen

# ---------------------------------------------------------------------------
# Elemental: Burn I and Frostbite I (for Ember Bolt / Frost Shot)
# ---------------------------------------------------------------------------

def make_burn_basic(user: Any, target: Any, battle_state: Any) -> StatusEffect:
    """
    Burn I: MAG×0.25 per tick, +5% Fire dmg taken, 3T.
    If MAG is not wired (0 or missing), fall back to a small flat tick
    so you can actually *see* the effect in Forge XVI tests.
    """
    mag = getattr(user, "mag", 0) or 0
    try:
        tick = int(mag * 0.25)
    except Exception:
        tick = 0

    # If MAG is tiny or zero, give a noticeable baseline.
    if tick <= 0:
        tick = 4  # tweak to taste

    status = BurnStatus(
        id="burn_1",
        name="Burn I",
        duration_turns=3,
        dispellable=True,
        stackable=True,
    )
    status.tick_amount = max(0, tick)
    status.fire_vuln_mult = 1.05
    status.tags.update({"burn", "dot", "fire", "debuff"})

    # HUD metadata
    status.icon_type = "debuff"
    status.icon_id = "burn"   # battle_ui.DEBUFF_PIPS.get("burn", "†")

    return status

def make_frostbite_basic(user: Any, target: Any, battle_state: Any) -> StatusEffect:
    """
    Frostbite I: –15% SPD, +5% Ice dmg taken, 3T.
    """
    status = FrostbiteStatus(
        id="frostbite_1",
        name="Frostbite I",
        duration_turns=3,
        dispellable=True,
        stackable=True,
    )
    status.spd_mult = 0.85       # -15% SPD
    status.ice_vuln_mult = 1.05  # +5% ice damage taken
    status.tags.update({"frostbite", "slow", "ice", "debuff"})

    # HUD metadata
    status.icon_type = "debuff"
    status.icon_id = "frostbite"  # you can add this to DEBUFF_PIPS later

    return status

# ---------------------------------------------------------------------------
# Setia: Flow I (speed buff)
# ---------------------------------------------------------------------------

def make_flow_i(user: Any, target: Any, battle_state: Any) -> StatusEffect:
    """
    Flow I: +15% SPD, 3T, stackable (we'll enforce stack cap later in manager).
    """
    status = StatBuffStatus(
        id="flow_1",
        name="Flow I",
        duration_turns=3,
        dispellable=True,
        stackable=True,
        mults={"spd_mult": 1.15},
        adds={},
    )

    # Tags + HUD metadata
    if hasattr(status, "tags"):
        status.tags.update({"setia", "buff", "flow", "speed"})

    status.icon_type = "buff"
    status.icon_id = "flow"

    return status

# ---------------------------------------------------------------------------
# Defend
# ---------------------------------------------------------------------------

def make_defend_basic(target=None, user=None, context=None):
    from engine.battle.status.effects import DefendStatus
    return DefendStatus(id="defend_1", name="Defend", duration_turns=1)

