# engine/battle/ui_flow.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal, Any

import pygame

from engine.battle.battle_command import BattleCommand
from engine.battle.targeting import UnifiedTargetCursor, build_candidates_from_combatants

UIMode = Literal["menu", "skills", "items", "weapons", "targeting", "tactical"]
CORE_HERO_IDS = {"Setia", "Nyra", "Kaira"}


@dataclass
class UIFlowState:
    mode: UIMode = "menu"
    tactical_index: int = 0
    cursor: Optional[UnifiedTargetCursor] = None
    hover_id: Optional[str] = None

    pending_actor_id: Optional[str] = None
    pending_skill_id: Optional[str] = None
    pending_item_id: Optional[str] = None
    target_context_key: Optional[str] = None
    menu_actor_id: Optional[str] = None


class UIFlow:
    """
    UIFlow — Battle UI Input & Intent Controller

    Responsibilities:
    - Own UI mode state: "menu", "tactical", "targeting"
    - Interpret player input (keys → intent)
    - Manage selection state (menu choice, tactical choice, target hover)
    - Emit BattleCommand when an action is confirmed

    Non-Responsibilities:
    - Rendering, layout, fonts, or visual effects
    - Battle mechanics, damage, CTB, or status logic

    Design Contract:
    - UIFlow decides *what happens*.
    - UIFlow never draws anything.
    """
    def __init__(self) -> None:
        self.state = UIFlowState()
        self._last_hover_by_context: dict[str, str] = {}
        self._last_menu_index_by_group: dict[str, int] = {}
        self._last_root_index_by_actor: dict[str, int] = {}
        self._last_sub_index_by_actor_group: dict[tuple[str, str], int] = {}

    def _actor_id(self, actor: Any) -> str:
        return str(getattr(actor, "id", getattr(actor, "name", "unknown_actor")))

    def _can_weapon_swap(self, actor: Any) -> bool:
        return self._actor_id(actor) in CORE_HERO_IDS

    def _list_consumables(self) -> list:
        from engine.items.defs import all_items
        return [it for it in all_items() if getattr(it, "kind", None) == "consumable"]

    def _list_compatible_weapons(self, actor: Any) -> list:
        from engine.items.defs import all_items
        aid = self._actor_id(actor)

        allowed = {
            "Setia": {"fist"},
            "Nyra": {"staff"},
            "Kaira": {"dagger"},
        }.get(aid, set())

        if not allowed:
            return []

        out = []
        for it in all_items():
            if getattr(it, "kind", None) != "weapon":
                continue
            tags = set(getattr(it, "weapon_tags", ()) or ())
            if tags & allowed:
                out.append(it)
        return out

    def _allowed_sides_for_target_type(self, target_type: object) -> set[str]:
        """
        Returns allowed sides as {"party"} / {"enemy"} / {"party","enemy"}.
        We keep this conservative and string-based for now.
        """
        if not isinstance(target_type, str):
            return {"party", "enemy"}

        tt = target_type.lower()
        if tt.startswith("ally") or tt.startswith("self"):
            return {"party"}
        if tt.startswith("enemy"):
            return {"enemy"}
        return {"party", "enemy"}

    def _target_context_key(self, *, actor: object, skill_def: object) -> str:
        meta = getattr(skill_def, "meta", None)
        target_type = getattr(meta, "target_type", None)
        allowed = ",".join(sorted(self._allowed_sides_for_target_type(target_type)))
        actor_id = str(getattr(actor, "id", getattr(actor, "name", "unknown_actor")))
        return f"actor:{actor_id}:sides:{allowed}"

    def _cursor_set_if_valid(self, cur: UnifiedTargetCursor, wanted_id: str, *, allowed_sides: set[str]) -> bool:
        """
        Set cursor to wanted_id only if it's a living candidate and on an allowed side.
        """
        for c in cur.candidates:
            if c.combatant_id == wanted_id and c.alive and c.side in allowed_sides:
                cur.current_id = wanted_id
                return True
        return False

    def begin_actor_menu(self, *, arena, actor) -> None:
        ui = getattr(arena, "ui", None)
        if ui is None:
            return

        actor_id = str(getattr(actor, "id", getattr(actor, "name", "unknown_actor")))

        self.state.mode = "menu"
        self.state.menu_actor_id = actor_id

        ui.menu_layer = "root"
        ui.current_group = None
        ui.root_index = self._last_root_index_by_actor.get(actor_id, 0)
        ui.skills_index = 0

    # --------- Mode transitions ---------
    def enter_targeting(self, party, enemies, *, controller, actor, skill_def=None, item_def=None) -> None:
        self.state.mode = "targeting"
        self.state.cursor = UnifiedTargetCursor(build_candidates_from_combatants(party, enemies))

        actor_id = str(getattr(actor, "id", getattr(actor, "name", "unknown_actor")))

        # -----------------------------
        # Determine targeting context
        # -----------------------------
        if skill_def is not None:
            meta = getattr(skill_def, "meta", None)
            target_type = getattr(meta, "target_type", None)
            ctx = self._target_context_key(actor=actor, skill_def=skill_def)

            self.state.pending_actor_id = getattr(actor, "id", None)
            self.state.pending_skill_id = str(getattr(meta, "id", None))
            self.state.pending_item_id = None

        elif item_def is not None:
            meta = None
            # ItemDef.targeting values: "self"/"ally"/"party"/"enemy"/"none"
            target_type = getattr(item_def, "targeting", None)
            ctx = f"actor:{actor_id}:item:{getattr(item_def, 'id', '<unknown>')}:tt:{target_type}"

            self.state.pending_actor_id = getattr(actor, "id", None)
            self.state.pending_skill_id = None
            self.state.pending_item_id = str(getattr(item_def, "id", None))
            
        else:
            # nothing to target
            self.exit_targeting()
            return

        allowed_sides = self._allowed_sides_for_target_type(target_type)
        self.state.target_context_key = ctx

        # 1) Prefer restoring last hover for this context
        restored = False
        last_id = self._last_hover_by_context.get(ctx)
        if self.state.cursor and last_id:
            restored = self._cursor_set_if_valid(self.state.cursor, last_id, allowed_sides=allowed_sides)

        # 2) Otherwise fall back to your current default entry behavior
        if not restored and self.state.cursor:
            prefer_allies = ("party" in allowed_sides) and ("enemy" not in allowed_sides)

            if prefer_allies:
                ally_id = self._first_living_ally_id(party)
                if ally_id is not None:
                    self.state.cursor.current_id = ally_id
            else:
                enemy_id = self._first_living_enemy_id(enemies)
                if enemy_id is not None:
                    self.state.cursor.current_id = enemy_id

        # Seed hover truth + controller bridge
        c = self.state.cursor.current() if self.state.cursor else None
        self.state.hover_id = c.combatant_id if c else None
        controller._target_hover_id = self.state.hover_id

        # Record immediately (so cancel also “remembers” what you hovered)
        if self.state.hover_id:
            self._last_hover_by_context[ctx] = self.state.hover_id

    def exit_targeting(self) -> None:
        self.state.mode = "menu"
        self.state.cursor = None
        self.state.hover_id = None
        self.state.target_context_key = None
        self.state.pending_item_id = None

    def open_tactical(self) -> None:
        self.state.mode = "tactical"
        self.state.tactical_index = 0
        self.state.pending_actor_id = None
        self.state.pending_skill_id = None
        self.state.pending_item_id = None

    def close_tactical(self) -> None:
        self.state.mode = "menu"

    def get_battle_available_item_qty(self, arena, item_id: str) -> int:
        # 1) Base quantity from ledger snapshot
        base_qty = 0
        ledger = getattr(arena.runtime.session, "ledger", None)
        if ledger is not None:
            inv = getattr(ledger, "inventory", None)
            if inv is not None and isinstance(inv.stacks, dict):
                base_qty = int(inv.stacks.get(item_id, 0))
   
        # 2) Apply battle gains
        gains = getattr(arena.runtime, "gains", None)
        if gains is None:
            return base_qty

        gained = 0
        for iid, qty in gains.items_gained:
            if iid == item_id:
                gained += int(qty)

        consumed = 0
        for iid, qty in gains.items_consumed:
            if iid == item_id:
                consumed += int(qty)

        return max(0, base_qty + gained - consumed)

    # --------- Input handling ---------
    def move_target_cursor(self, dx: int, dy: int, *, controller) -> None:
        """
        Transitional bridge: UIFlow decides movement.
        Controller still applies it for now.
        (Later: UIFlow stores cursor and controller becomes pure read/model.)
        """
        controller.move_cursor(dx, dy)

    def _combatant_id(self, c) -> str:
        return str(getattr(c, "id", getattr(c, "name", "unknown")))

    def _first_living_enemy_id(self, enemies) -> str | None:
        for e in enemies:
            if bool(getattr(e, "alive", True)):
                return self._combatant_id(e)
        return None

    def _first_living_ally_id(self, party) -> str | None:
        for p in party:
            if bool(getattr(p, "alive", True)):
                return self._combatant_id(p)
        return None

    def handle_key(
        self,
        key: int,
        *,
        arena,       # BattleArena (has .ui)
        controller,  # BattleController (has party/enemies/skills etc.)
        actor: Any,
        skills: list,
        flee_allowed: bool = True,
    ) -> tuple[bool, Optional[int], Optional[BattleCommand]]:
        """
        Returns: (handled, chosen_skill_index, command)

        - handled: True means BattleArena shouldn't process further
        - chosen_skill_index: index into skills if a skill was confirmed in menu
        - command: BattleCommand if a tactical choice was confirmed
        """

        ui = getattr(arena, "ui", None)

        # ---------------- MENU ----------------
        if self.state.mode == "menu":
            if ui is None:
                return False, None, None

            actor_id = str(getattr(actor, "id", getattr(actor, "name", "unknown_actor")))

            # Root index: keep UI in sync with remembered value (safe)
            if ui.menu_layer == "root":
                remembered_root = self._last_root_index_by_actor.get(actor_id)
                if remembered_root is not None and ui.root_index != remembered_root:
                    ui.root_index = remembered_root

            # Submenu index: keep UI in sync with remembered value
            if ui.menu_layer == "skills":
                group = ui.current_group or "arts"
                remembered_sub = self._last_sub_index_by_actor_group.get((actor_id, group))
                if remembered_sub is not None and ui.skills_index != remembered_sub:
                    ui.skills_index = remembered_sub

            # Build root menu options (Attack / Arts / Elemental / Items)
            root_options = ui._get_root_menu_options(actor, skills)

            # LEFT special-case: on ROOT, if highlighting Items, open weapon popup
            if ui is not None and ui.menu_layer == "root" and key == pygame.K_LEFT:
                _label, group = root_options[ui.root_index]
                if group == "items" and self._can_weapon_swap(actor):
                    ui.menu_layer = "weapons"
                    ui.skills_index = 0
                    return True, None, None

            # LEFT opens Tactical (spec)
            if key == pygame.K_LEFT:
                self.open_tactical()
                return True, None, None

            # ROOT MENU
            if ui.menu_layer == "root":
                if key == pygame.K_UP:
                    ui.root_index = (ui.root_index - 1) % len(root_options)
                    actor_id = str(getattr(actor, "id", getattr(actor, "name", "unknown_actor")))
                    self._last_root_index_by_actor[actor_id] = ui.root_index
                    return True, None, None

                if key == pygame.K_DOWN:
                    ui.root_index = (ui.root_index + 1) % len(root_options)
                    actor_id = str(getattr(actor, "id", getattr(actor, "name", "unknown_actor")))
                    self._last_root_index_by_actor[actor_id] = ui.root_index                    
                    return True, None, None

                if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_x):
                    return True, None, None

                if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                    _label, group = root_options[ui.root_index]

                    if group == "attack":
                        # instant: first attack skill
                        for idx, s in enumerate(skills):
                            meta = getattr(s, "meta", None)
                            if meta and getattr(meta, "menu_group", "") == "attack":
                                return True, idx, None
                        return True, None, None

                    if group == "items":
                        # Open consumables list (handled as a submenu)
                        ui.menu_layer = "items"
                        # reuse skills_index as a generic submenu cursor for now
                        ui.skills_index = 0
                        return True, None, None

                    # open skills submenu + restore last index for that group
                    ui.menu_layer = "skills"
                    ui.current_group = group
                    ui.skills_index = self._last_sub_index_by_actor_group.get((actor_id, group), 0)
                    return True, None, None

                return False, None, None

            # ---------------- ITEMS SUBMENU (Consumables) ----------------
            if ui.menu_layer == "items":
                items = self._list_consumables()

                if not items:
                    if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_x):
                        ui.menu_layer = "root"
                        return True, None, None
                    return True, None, None

                if key == pygame.K_UP:
                    ui.skills_index = (ui.skills_index - 1) % len(items)
                    return True, None, None

                if key == pygame.K_DOWN:
                    ui.skills_index = (ui.skills_index + 1) % len(items)
                    return True, None, None

                if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_x):
                    ui.menu_layer = "root"
                    return True, None, None

                if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                    chosen = items[ui.skills_index]
                    actor_id = self._actor_id(actor)

                    # Stage item targeting (reuse existing targeting flow)
                    self.state.pending_actor_id = actor_id
                    self.state.pending_skill_id = None
                    self.state.pending_item_id = chosen.id
                    self.state.target_context_key = f"item:{chosen.id}"

                    # Enter targeting using your existing machinery.
                    # NOTE: you likely already have a method that sets cursor based on context;
                    # reuse it if it exists (e.g., enter_targeting()).
                    self.enter_targeting(
                        arena.runtime.session.party,
                        arena.runtime.session.enemies,
                        controller=controller,
                        actor=actor,
                        item_def=chosen,
                    )
                    return True, None, None

                return True, None, None


            # ---------------- WEAPONS POPUP ----------------
            if ui.menu_layer == "weapons":
                weapons = self._list_compatible_weapons(actor)

                if not weapons:
                    if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_x):
                        ui.menu_layer = "root"
                        return True, None, None
                    # no compatible weapons: just ignore inputs besides back
                    return True, None, None

                if key == pygame.K_UP:
                    ui.skills_index = (ui.skills_index - 1) % len(weapons)
                    return True, None, None

                if key == pygame.K_DOWN:
                    ui.skills_index = (ui.skills_index + 1) % len(weapons)
                    return True, None, None

                if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_x):
                    ui.menu_layer = "root"
                    return True, None, None

                if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                    actor_id = self._actor_id(actor)
                    chosen = weapons[ui.skills_index]

                    cmd = BattleCommand(
                        actor_id=actor_id,
                        command_type="equip_weapon",
                        skill_id=None,
                        item_id=chosen.id,
                        targets=[actor_id],  # self-only
                        source="player",
                        reason=None,
                    )
                    ui.menu_layer = "root"
                    return True, None, cmd

                return True, None, None

            # ---------------- SKILLS SUBMENU ----------------
            group = ui.current_group or "arts"
            actor_id = str(getattr(actor, "id", getattr(actor, "name", "unknown_actor")))
            sub_key = (actor_id, group)

            grouped: list[tuple[int, Any]] = []
            for global_idx, s in enumerate(skills):
                meta = getattr(s, "meta", None)
                if meta and getattr(meta, "menu_group", None) == group:
                    grouped.append((global_idx, s))

            # If no skills exist for the group, allow backing out
            if not grouped:
                if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_x, pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                    ui.menu_layer = "root"
                    ui.current_group = None
                    # keep last index remembered for this actor+group
                    ui.skills_index = self._last_sub_index_by_actor_group.get(sub_key, 0)
                    return True, None, None
                return True, None, None

            if key == pygame.K_UP:
                ui.skills_index = (ui.skills_index - 1) % len(grouped)
                self._last_sub_index_by_actor_group[sub_key] = ui.skills_index
                return True, None, None

            if key == pygame.K_DOWN:
                ui.skills_index = (ui.skills_index + 1) % len(grouped)
                self._last_sub_index_by_actor_group[sub_key] = ui.skills_index
                return True, None, None

            if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_x):
                # remember where we were in this actor+group
                self._last_sub_index_by_actor_group[sub_key] = ui.skills_index
                ui.menu_layer = "root"
                ui.current_group = None
                return True, None, None

            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                # remember where we were in this actor+group
                self._last_sub_index_by_actor_group[sub_key] = ui.skills_index
                global_idx, _skill = grouped[ui.skills_index]
                return True, global_idx, None

            return False, None, None


        # ---------------- TACTICAL POPUP ----------------
        if self.state.mode == "tactical":
            max_idx = 1 if flee_allowed else 0

            if key == pygame.K_UP:
                self.state.tactical_index = max(0, self.state.tactical_index - 1)
                return True, None, None

            if key == pygame.K_DOWN:
                self.state.tactical_index = min(max_idx, self.state.tactical_index + 1)
                return True, None, None

            if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_x):
                self.close_tactical()
                return True, None, None

            if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                cmd_type = "defend" if self.state.tactical_index == 0 else "flee"
                self.close_tactical()
                actor_id = getattr(actor, "id", getattr(actor, "name", "unknown_actor"))
                return True, None, BattleCommand(actor_id=actor_id, command_type=cmd_type, source="player")

            return True, None, None

        # ---------------- TARGETING ----------------
        if self.state.mode == "targeting":
            cur = self.state.cursor
            if cur is None:
                self.exit_targeting()
                return True, None, None

            moved = False

            # movement
            if key == pygame.K_UP:
                cur.move("up"); moved = True
            elif key == pygame.K_DOWN:
                cur.move("down"); moved = True
            elif key == pygame.K_LEFT:
                cur.move("left"); moved = True
            elif key == pygame.K_RIGHT:
                cur.move("right"); moved = True

            # confirm
            elif key in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
                actor_id = self.state.pending_actor_id
                skill_id = self.state.pending_skill_id
                item_id  = self.state.pending_item_id
                target_id = self.state.hover_id

                if not actor_id or not target_id:
                    return True, None, None

                if skill_id:
                    # --------------------------------------------------
                    # Gate: item-skills (skills tagged consumes:*)
                    # --------------------------------------------------
                    try:
                        consumes_item_id = None

                        # Find the selected skill definition by id and read its tags
                        for s in skills:
                            meta = getattr(s, "meta", None)
                            if meta is None:
                                continue
                            if getattr(meta, "id", None) != skill_id:
                                continue

                            tags = set(getattr(meta, "tags", set()) or [])
                            for t in tags:
                                if isinstance(t, str) and t.startswith("consumes:"):
                                    consumes_item_id = t.split(":", 1)[1].strip()
                                    break
                            break

                        if consumes_item_id:
                            available = self.get_battle_available_item_qty(arena, consumes_item_id)
                            
                            # Also print both possible ledger stores so we know who’s real
                            ledger = getattr(arena.runtime.session, "ledger", None)
                            inv = getattr(ledger, "inventory", None) if ledger is not None else None
                            if available <= 0:
                                try:
                                    arena.message = f"Out of {consumes_item_id.replace('_', ' ').title()}."
                                except Exception:
                                    pass
                                return True, None, None
                    except Exception:
                        pass

                    cmd = BattleCommand(
                        actor_id=actor_id,
                        command_type="skill",
                        skill_id=skill_id,
                        item_id=None,
                        targets=[target_id],
                        source="player",
                        reason=None,
                    )
                    self.exit_targeting()
                    return True, None, cmd


                if item_id:
                    # -----------------------------
                    # Item quantity gate (battle-available)
                    # -----------------------------
                    available = self.get_battle_available_item_qty(arena, str(item_id))
                    if available <= 0:
                        try:
                            arena.message = f"Out of {str(item_id).replace('_', ' ').title()}."
                        except Exception:
                            pass
                        return True, None, None

                    cmd = BattleCommand(
                        actor_id=actor_id,
                        command_type="item",
                        skill_id=None,
                        item_id=item_id,
                        item_qty=1,
                        targets=[target_id],
                        source="player",
                        reason=None,
                    )
                    self.exit_targeting()
                    return True, None, cmd

            # cancel
            elif key in (pygame.K_x, pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.exit_targeting()
                return True, None, None

            else:
                return False, None, None

            # update hover truth after movement
            if moved:
                c = cur.current()
                self.state.hover_id = c.combatant_id if c else None
                controller._target_hover_id = self.state.hover_id

                # remember hover for this targeting context
                ctx = self.state.target_context_key
                if ctx and self.state.hover_id:
                    self._last_hover_by_context[ctx] = self.state.hover_id

            return True, None, None

        return False, None, None
