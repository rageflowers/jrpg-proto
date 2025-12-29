from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Sequence, TYPE_CHECKING
from engine.battle.skills.base import SkillDefinition, SkillMeta, SkillResolutionResult
from .battle_command import BattleCommand
if TYPE_CHECKING:
    from engine.battle.session import BattleSession

# ============================================
# ActionResult datatypes (shared truth package)
# ============================================


# --------------------------------------------------------------------------- #
#  ActionResult: the truth of an action (math only, no visuals)
# --------------------------------------------------------------------------- #

@dataclass
class TargetResult:
    target_id: str
    hp_delta: int = 0
    mp_delta: int = 0
    is_ko: bool = False
    status_applied: list[str] = field(default_factory=list)
    status_removed: list[str] = field(default_factory=list)

@dataclass
class ActionResult:
    actor_id: str
    command_type: str
    skill_id: Optional[str] = None
    item_id: Optional[str] = None
    item_qty: int = 1
    consumed_items: list[tuple[str, int]] = field(default_factory=list)
    element: Optional[str] = None
    targets: List[TargetResult] = field(default_factory=list)
    xp_gained: int = 0
    loot: list[Any] = field(default_factory=list)
    crit: bool = False
    fumble: bool = False

# --------------------------------------------------------------------------- #
#  ActionResolver: performs all math, creates ActionResult
# --------------------------------------------------------------------------- #
class ActionResolver:
    """
    Thin bridge between existing SkillResolver outputs and the new
    ActionResult / TargetResult shapes.

    XVII.13: This is *not* yet authoritative. It mirrors the old path
    so we can log and inspect without changing behavior.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    # -----------------------------
    # Helper: from SkillResolutionResult
    # -----------------------------
    def build_from_skill_resolution(
        self,
        *,
        actor: Any,
        skill_def: Any | None,
        targets: list[Any],
        skill_result: Any,
        command_type: str = "skill",
    ) -> ActionResult:
        """
        Bridge: SkillResolutionResult -> ActionResult.

        For each TargetChange in skill_result.targets, we create exactly one
        TargetResult with aggregated totals:

            - hp_delta: negative for damage, positive for healing
            - mp_delta: copied from TargetChange.mp_delta
            - status_applied / status_removed: copied from TargetChange

        Additionally:
            - MP cost is charged to the *actor* via a TargetResult mp_delta (negative).
            This keeps all combat mutations inside Session.apply_action_result.
        """
        actor_id = getattr(actor, "id", getattr(actor, "name", "<?>"))

        # Skill metadata
        skill_id: Optional[str] = None
        element: Optional[str] = None

        if skill_def is not None:
            # Accept either a SkillDefinition or a bare SkillMeta-like object
            meta = getattr(skill_def, "meta", None) or skill_def
            skill_id = getattr(meta, "id", None)
            element = getattr(meta, "element", None)
            mp_cost = int(getattr(meta, "mp_cost", 0) or 0)
        else:
            meta = None
            mp_cost = 0

        result = ActionResult(
            actor_id=actor_id,
            command_type=command_type,
            skill_id=skill_id,
            element=element,
        )

        # ----------------------------------------------------------
        # Item-skill bridge: stamp inventory consumption metadata
        # ----------------------------------------------------------
        if skill_def is not None:
            meta = getattr(skill_def, "meta", None)
            tags = set(getattr(meta, "tags", set()) or [])

            consume_tag = next(
                (t for t in tags if isinstance(t, str) and t.startswith("consumes:")),
                None,
            )
            if consume_tag:
                item_id = consume_tag.split(":", 1)[1].strip()
                if item_id:
                    result.command_type = "item"
                    result.item_id = item_id
                    result.item_qty = 1
                    # Session/BattleGains will read this later
                    result.consumed_items = [(item_id, 1)]

        # We assume skill_result.targets is a list of TargetChange-like objects.
        for change in getattr(skill_result, "targets", []):
            tgt = getattr(change, "target", None)
            if tgt is None:
                continue

            target_id = getattr(tgt, "id", getattr(tgt, "name", "<?>"))

            # Totals from TargetChange
            damage = int(getattr(change, "damage", 0) or 0)
            healed = int(getattr(change, "healed", 0) or 0)
            mp_delta = int(getattr(change, "mp_delta", 0) or 0)

            # Convention: hp_delta negative = damage, positive = heal
            hp_delta = 0
            if damage:
                hp_delta -= damage
            if healed:
                hp_delta += healed

            # KO detection (prefer explicit flags from resolver result)
            is_ko = bool(getattr(change, "killed", False))

            # Status markers mirror TargetChange fields.
            status_applied = list(getattr(change, "status_applied", []) or [])
            status_removed = list(getattr(change, "status_removed", []) or [])

            result.targets.append(
                TargetResult(
                    target_id=target_id,
                    hp_delta=hp_delta,
                    mp_delta=mp_delta,
                    is_ko=is_ko,
                    status_applied=status_applied,
                    status_removed=status_removed,
                )
            )

        # ----------------------------------------------------------
        # Actor MP spend (kept inside ActionResult for POST_RESOLVE)
        # ----------------------------------------------------------
        if mp_cost > 0:
            actor_tr = None
            for tr in result.targets:
                if tr.target_id == actor_id:
                    actor_tr = tr
                    break

            if actor_tr is None:
                result.targets.append(
                    TargetResult(
                        target_id=actor_id,
                        hp_delta=0,
                        mp_delta=-mp_cost,
                        is_ko=False,
                        status_applied=[],
                        status_removed=[],
                    )
                )
            else:
                actor_tr.mp_delta = int(getattr(actor_tr, "mp_delta", 0) or 0) - mp_cost

        return result

    # -----------------------------
    # Future: true resolution
    # -----------------------------
    def resolve(self, command: BattleCommand) -> ActionResult:
        """
        Placeholder for future “math brain”.

        XVII.13: We *don’t* call this yet. True authority will move here
        once we decouple SkillResolver from direct HP mutations.
        """
        # For now, just return an empty shell so callers don’t explode
        return ActionResult(actor_id=command.actor_id, command_type=command.command_type)

# ============================================
# StatusEvent translation (events -> ActionResult)
#
# This is a pure translation step used by:
#   engine/battle/status/status_event_resolver.py
#
# It does NOT resolve skills/commands and does NOT mutate combatants.
# ============================================

from engine.battle.status.status_events import (
    StatusEvent,
    DamageTickEvent,
    ApplyStatusEvent,
    RemoveStatusEvent,
    RetaliationEvent,
)

def build_action_result_from_status_events(
    *,
    events: Sequence[StatusEvent],
    session: "BattleSession",
    source: str = "status_tick",
) -> ActionResult:
    """
    Translate a batch of StatusEvent objects into a single ActionResult that can
    be applied via BattleSession.apply_action_result.

    Conventions:
        - DamageTickEvent.amount is treated as a signed HP delta.
          amount < 0 => damage, amount > 0 => healing.
        - ApplyStatusEvent / RemoveStatusEvent update the per-target
          status_applied / status_removed lists.
        - RetaliationEvent is currently a no-op here; its damage and
          status-application can be wired in later once we finalize the
          retaliation pipeline under the new doctrine.
    """
    # Start with an "empty" system-driven action.
    result = ActionResult(
        actor_id="system:status",
        command_type=source,
        skill_id=None,
        item_id=None,
        element=None,
    )

    if not events:
        return result

    # Aggregation buckets
    hp_mp_by_target: Dict[str, Dict[str, int]] = {}
    status_applied_by_target: Dict[str, List[str]] = {}
    status_removed_by_target: Dict[str, List[str]] = {}

    def _ensure_target_bucket(target_id: str) -> None:
        if target_id not in hp_mp_by_target:
            hp_mp_by_target[target_id] = {"hp": 0, "mp": 0}
            status_applied_by_target[target_id] = []
            status_removed_by_target[target_id] = []

    def _resolve_target_id(raw_target: Any) -> Optional[str]:
        """
        Best-effort extraction of a combatant ID from whatever the event carries.

        Priority:
            1) If it's already a str → assume it's a combatant_id.
            2) Common id attributes on our combatant objects.
            3) Fallback: None (event is ignored).
        """
        if isinstance(raw_target, str):
            return raw_target

        # Common combatant id fields used across the codebase
        for attr in ("id", "cid", "combatant_id", "target_id", "name"):
            val = getattr(raw_target, attr, None)
            if isinstance(val, str) and val:
                return val

        return None

    # --------------------------------------------------
    # Fold all events into per-target aggregates
    # --------------------------------------------------
    for ev in events:
        # -----------------------------
        # 1) Damage ticks (DoTs / regen)
        # -----------------------------
        if isinstance(ev, DamageTickEvent):
            target_id = _resolve_target_id(ev.target)
            if target_id is None:
                continue

            _ensure_target_bucket(target_id)

            # Convention (XVII.18):
            #   DamageTickEvent.amount is already a signed HP delta:
            #       amount < 0  => damage
            #       amount > 0  => healing
            amount_int = int(ev.amount)
            if amount_int != 0:
                hp_mp_by_target[target_id]["hp"] += amount_int

        # -----------------------------
        # 2) Apply-status events
        # -----------------------------
        elif isinstance(ev, ApplyStatusEvent):
            target_id = _resolve_target_id(ev.target)
            if target_id is None:
                continue

            _ensure_target_bucket(target_id)

            status_obj = ev.status
            status_id = getattr(status_obj, "id", None)
            if status_id:
                status_applied_by_target[target_id].append(str(status_id))

        # -----------------------------
        # 3) Remove-status events
        # -----------------------------
        elif isinstance(ev, RemoveStatusEvent):
            target_id = _resolve_target_id(ev.target)
            if target_id is None:
                continue

            _ensure_target_bucket(target_id)

            status_identifier: Optional[str] = None

            # Allow either a status object or a bare id to be carried.
            if hasattr(ev, "status") and ev.status is not None:
                status_identifier = getattr(ev.status, "id", None)
                if status_identifier is None and isinstance(ev.status, str):
                    status_identifier = ev.status
            elif hasattr(ev, "status_id") and ev.status_id is not None:
                status_identifier = str(ev.status_id)

            if status_identifier:
                status_removed_by_target[target_id].append(str(status_identifier))

        # -----------------------------
        # 4) Retaliation events (placeholder)
        # -----------------------------
        elif isinstance(ev, RetaliationEvent):
            # We'll wire these into the unified damage/status pipeline once
            # the retaliation design is fully migrated to StatusEvents.
            # For now, we intentionally treat them as metadata-only.
            continue

    # --------------------------------------------------
    # Build TargetResult objects from aggregates
    # --------------------------------------------------
    for target_id, deltas in hp_mp_by_target.items():
        hp_delta = deltas["hp"]
        mp_delta = deltas["mp"]

        applied = status_applied_by_target.get(target_id, [])
        removed = status_removed_by_target.get(target_id, [])

        # Predict KO *before* application so that FX/UI can respond.
        # We look up current HP in the session and apply the pending delta.
        is_ko = False
        try:
            combatant = session.get_combatant(target_id)
            current_hp = int(getattr(combatant, "hp", 0))
            max_hp = max(1, int(getattr(combatant, "max_hp", 1)))
            new_hp = max(0, min(max_hp, current_hp + hp_delta))
            is_ko = new_hp <= 0
        except Exception:
            # If anything goes wrong (bad ID, etc.), we fall back to False.
            is_ko = False

        tr = TargetResult(
            target_id=target_id,
            hp_delta=hp_delta,
            mp_delta=mp_delta,
            is_ko=is_ko,
            status_applied=list(applied),
            status_removed=list(removed),
        )
        result.targets.append(tr)

    return result
    