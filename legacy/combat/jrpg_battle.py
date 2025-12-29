# jrpg_battle.py

from __future__ import annotations
from typing import List
import random

from legacy.entities.jrpg_entities import Actor
from legacy.combat.jrpg_actions import ACTIONS, Action

class Battle:
    def __init__(self, party: List[Actor], enemies: List[Actor], rng_seed: int = 42):
        self.party = party
        self.enemies = enemies
        random.seed(rng_seed)
        self.turn_count = 1

    # ---------- Helpers ----------

    def living_party(self) -> List[Actor]:
        return [a for a in self.party if a.alive]

    def living_enemies(self) -> List[Actor]:
        return [a for a in self.enemies if a.alive]

    def is_over(self) -> bool:
        return not self.living_party() or not self.living_enemies()

    def next_turn_order(self) -> List[Actor]:
        actors = [a for a in (self.party + self.enemies) if a.alive]
        random.shuffle(actors)
        actors.sort(key=lambda a: a.stats.speed, reverse=True)
        return actors

    # ---------- AI ----------

    def choose_ai_action(self, actor: Actor) -> Action:
        names = actor.actions
        usable = [ACTIONS[n] for n in names if n in ACTIONS and actor.mp >= ACTIONS[n].mp_cost]
        if not usable:
            usable = [ACTIONS[n] for n in names if n in ACTIONS]
        if not usable:
            return ACTIONS["Weapon Attack"]
        return max(usable, key=lambda a: a.mp_cost)

    def choose_target(self, actor: Actor, action: Action) -> Actor | None:
        if action.target_allies:
            pool = self.living_party() if actor in self.party else self.living_enemies()
        else:
            pool = self.living_enemies() if actor in self.party else self.living_party()
        return random.choice(pool) if pool else None

    # ---------- HUD ----------

    def render_hud(self) -> str:
        def fmt(a: Actor) -> str:
            status = "KO" if not a.alive else ""
            return (f"{a.name:8} "
                    f"HP {a.hp:>3}/{a.stats.max_hp:<3} "
                    f"MP {a.mp:>2}/{a.stats.max_mp:<2} "
                    f"TEM {a.tempo:+2d} {status}")
        lines = ["\n=== PARTY ==="]
        for a in self.party:
            lines.append(fmt(a))
        lines.append("=== ENEMIES ===")
        for e in self.enemies:
            lines.append(fmt(e))
        lines.append("")
        return "\n".join(lines)

    # ---------- Core Loop ----------

    def run(self) -> bool:
        print("\nA battle begins!")
        while not self.is_over():
            print(f"\n--- Turn {self.turn_count} ---")
            print(self.render_hud())

            for actor in self.next_turn_order():
                if not actor.alive or self.is_over():
                    continue

                # Player controls all living party members
                if actor in self.party:
                    action = self.player_choose_action(actor)
                else:
                    action = self.choose_ai_action(actor)

                target = self.choose_target(actor, action)
                if not target:
                    continue

                # MP check
                if action.mp_cost > 0:
                    if actor.mp < action.mp_cost:
                        print(f"{actor.name} tries to use {action.name}, but lacks MP!")
                        continue
                    actor.mp -= action.mp_cost

                log = action.perform(actor, target)
                print(log)

                if not target.alive:
                    print(f"*** {target.name} is KO'd! ***")

                # end-of-turn status ticks
                for s in list(actor.statuses):
                    s.tick(actor)
                actor.cleanup_status()

                if self.is_over():
                    break

            self.turn_count += 1

        print(self.render_hud())
        if self.living_party():
            print("Victory!")
            return True
        else:
            print("Defeat...")
            return False

    # ---------- Player Input ----------

    def player_choose_action(self, actor: Actor) -> Action:
        options: List[Action] = [ACTIONS[n] for n in actor.actions if n in ACTIONS]
        if not options:
            return ACTIONS["Weapon Attack"]
        while True:
            print(f"\nYour turn, {actor.name}. Choose action:")
            for i, act in enumerate(options, start=1):
                mpinfo = f" (MP {act.mp_cost})" if act.mp_cost else ""
                tgt = "[Ally]" if act.target_allies else "[Foe]"
                print(f"  {i}. {act.name}{mpinfo} {tgt}")
            choice = input("> ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    chosen = options[idx]
                    if chosen.mp_cost > 0 and actor.mp < chosen.mp_cost:
                        print("Not enough MP.")
                        continue
                    return chosen
            print("Invalid choice.")
