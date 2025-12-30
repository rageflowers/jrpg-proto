# game/debug/run_integrated.py
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# --- ensure project root is importable ---
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import pygame

from engine.router import EventRouter
from engine.fx.system import FXSystem

from engine.overworld.overworld_scene import OverworldScene, OverworldConfig

from engine.battle.battle_arena import BattleArena
from engine.battle.skills.registry import initialize_defaults
from engine.actors.character_sheet import CharacterInstance, new_default_party
from engine.actors.enemy_sheet import initialize_enemy_templates
from engine.battle.action_phases import ActionPhase

from engine.meta.ledger_state import LedgerState
from engine.meta.battle_outcome import BattleOutcome

# -----------------------------
# Battle asset wiring (v0)
# -----------------------------
def _build_battle_arena(
    *,
    screen_w: int,
    screen_h: int,
    router: EventRouter,
    fx_system: FXSystem,
    ledger: LedgerState,
    battle_request,
) -> BattleArena:
    """
    Minimal battle arena builder.
    Uses ledger.party.get_active_party() as the identity faucet.
    battle_request comes from overworld (BattleRequest).
    """
    # Ensure registries are ready
    initialize_defaults()
    

    # You can swap these to your real sprite folder conventions.
    # BattleArena accepts frame lists (it may load internally depending on implementation).
    SPRITE_FOLDER = os.path.join(ROOT, "assets", "sprites", "battle")
    setia_frames = [os.path.join(SPRITE_FOLDER, f"setia_idle_{i}.png") for i in range(3)]
    nyra_frames = [os.path.join(SPRITE_FOLDER, f"nyra_idle_{i}.png") for i in range(3)]
    kaira_frames = [os.path.join(SPRITE_FOLDER, f"kaira_idle_{i}.png") for i in range(3)]
    enemy_frames = [os.path.join(SPRITE_FOLDER, f"enemy_idle_{i}.png") for i in range(3)]

    party_instances = ledger.party.get_active_party()
    party_keys = list(party_instances.keys())  # or ledger.party.active_ids

    region = getattr(battle_request, "backdrop_id", None) or getattr(battle_request, "region_id", "default")
    enemy_frame = []
    arena = BattleArena(
        screen_w,
        screen_h,
        setia_frames,
        nyra_frames,
        kaira_frames,
        enemy_frames,
        fonts=None,
        region=region,
        phase="day",
        router=router,
        party_instances=party_instances,
        party_keys=party_keys,
        enemy_party_id=getattr(battle_request, "enemy_party_id", None),
        seed=getattr(battle_request, "seed", None),
    )

    # 🔑 CRITICAL: attach ledger snapshot to battle session
    arena.runtime.session.ledger = ledger

    arena.fx_system = fx_system
    return arena



def _battle_is_finished(arena: BattleArena) -> bool:
    """
    v0: determine completion using the existing action mapper phase.
    """
    try:
        phase = arena.runtime.action_mapper.phase
    except Exception:
        return False
    return phase == ActionPhase.BATTLE_END


def _build_outcome(arena: BattleArena) -> BattleOutcome:
    """
    v0: derive outcome from BattleSession's own checks and logs.
    """
    session = arena.runtime.session
    status = session.check_battle_outcome()  # "victory" | "defeat" | "ongoing"
    victory = status == "victory"
    defeat = status == "defeat"
    return BattleOutcome(
        victory=victory,
        defeat=defeat,
        xp_log=list(getattr(session, "xp_log", []) or []),
        loot_log=list(getattr(session, "loot_log", []) or []),
    )


def _apply_outcome_to_ledger(ledger: LedgerState, outcome: BattleOutcome) -> None:
    """
    v0 policy:
    - Just log/commit loot stacks + add tiny gild as proof of persistence.
    - XP distribution can come next (Forge XIX.1 / XIX.2).
    """
    # Apply loot to inventory (stackables)
    for e in outcome.loot_log:
        item_id = str(e.get("item_id", "")).strip()
        qty = int(e.get("qty", 1) or 1)
        if item_id:
            ledger.inventory.add(item_id, qty)

    # Proof-of-life currency
    if outcome.victory:
        ledger.wallet.add(5)
        ledger.world.flags.add("battle_won_once")
    if outcome.defeat:
        ledger.world.flags.add("battle_lost_once")

    # Future: ledger.party.apply_xp(outcome.xp_log)

def enemy_frames_for(enemy_template_id: str) -> list[str]:
    sprite_dir = os.path.join(ROOT, "assets", "sprites", "merchant_trail")
    return [
        os.path.join(sprite_dir, f"{enemy_template_id}__idle_00.png"),
        os.path.join(sprite_dir, f"{enemy_template_id}__idle_01.png"),
        os.path.join(sprite_dir, f"{enemy_template_id}__attack_00.png"),
    ]


def main() -> int:
    pygame.init()
    pygame.display.set_caption("Integrated Harness — Forge XIX.0")
    SCREEN_SIZE = (1024, 768)
    screen = pygame.display.set_mode(SCREEN_SIZE)
    clock = pygame.time.Clock()

    router = EventRouter()
    fx_system = FXSystem(router, viewport_size=SCREEN_SIZE)

    # Ledger is the persistent truth
    ledger = LedgerState.new_game_default()
    ledger.inventory.stacks["potion_small"] = 1
    # Start in overworld using ledger continuity
    cfg = OverworldConfig()
    overworld = OverworldScene(cfg)

    # Bind overworld flags to ledger flags (shared reference)
    # Minimal change: we simply point the scene at the ledger-owned set.
    overworld.flags = ledger.world.flags

    mode: str = "overworld"
    arena: Optional[BattleArena] = None

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        ledger.playtime_s += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                continue

            # Route input to the active scene
            if mode == "battle" and arena is not None:
                arena.handle_event(event)
            # OverworldScene currently reads pygame state directly, so no event forwarding needed.

        if mode == "overworld":
            exit_name = overworld.update(dt)

            # Battle seam: check for pending battle request
            req = getattr(overworld, "pending_battle", None)
            if req is not None:
                ledger.inventory.stacks["iron_sword"] = 1
                arena = _build_battle_arena(
                    screen_w=screen.get_width(),
                    screen_h=screen.get_height(),
                    router=router,
                    fx_system=fx_system,
                    ledger=ledger,
                    battle_request=req,
                )

                # clear the pending request on the overworld side
                if hasattr(overworld, "clear_pending_battle"):
                    overworld.clear_pending_battle()
                mode = "battle"

            # draw overworld
            screen.fill((0, 0, 0))
            overworld.draw(screen, dt)
            overworld.draw_hud(screen)
            pygame.display.flip()
            continue

        # -------------------
        # Battle mode
        # -------------------
        if arena is None:
            # fail-safe
            mode = "overworld"
            continue

        # Update battle + FX
        arena.update(dt)
        fx_system.update(dt)

        # Draw battle + FX
        screen.fill((0, 0, 0))
        arena.draw(screen)
        fx_system.draw(screen)
        pygame.display.flip()

        # Return seam
        if _battle_is_finished(arena):
            outcome = _build_outcome(arena)
            _apply_outcome_to_ledger(ledger, outcome)

            # Rebuild overworld fresh (safe during early integration)
            overworld = OverworldScene(cfg)
            overworld.flags = ledger.world.flags

            arena = None
            mode = "overworld"

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
