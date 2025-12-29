import os
import pygame

from engine.router import EventRouter
from engine.fx.system import FXSystem
from engine.battle.battle_arena import BattleArena
from engine.battle.skills.registry import initialize_defaults, debug_dump_skills
from engine.battle.combatants import debug_print_all_statuses

from game.debug.debug_logger import log as battle_log, set_categories
from engine.battle import battle_controller as battle_controller
from engine.actors.character_sheet import new_default_party
from engine.actors.enemy_sheet import initialize_enemy_templates
from engine.battle.action_phases import ActionPhase


WIDTH, HEIGHT = 1024, 768

SPRITE_FOLDER = os.path.join("assets", "sprites")
BATTLE_SPRITE_SCALE = 0.2

# Idle frames for each character (3-frame breathing loops, like before)
SETIA_IDLE_FRAMES = [os.path.join(SPRITE_FOLDER, f"setia_idle_{i}.png") for i in range(3)]
NYRA_IDLE_FRAMES  = [os.path.join(SPRITE_FOLDER, f"nyra_idle_{i}.png") for i in range(3)]
KAIRA_IDLE_FRAMES = [os.path.join(SPRITE_FOLDER, f"kaira_idle_{i}.png") for i in range(3)]

# For now, enemy just reuses Setia's idle frames
ENEMY_IDLE_FRAMES = SETIA_IDLE_FRAMES


def _terminal_key(arena: BattleArena) -> str | None:
    """Return a stable terminal key once battle is ended, else None."""
    phase = arena.runtime.action_mapper.phase
    if phase != ActionPhase.BATTLE_END:
        return None

    sess = getattr(arena.runtime, "session", None)
    flags = getattr(sess, "flags", None) if sess is not None else None
    if flags is not None:
        if getattr(flags, "defeat", False):
            return "defeat"
        if getattr(flags, "victory", False):
            return "victory"
    return "battle_end"


def main() -> None:
    print("DEBUG: Running test_battle_arena.main()")

    # Debug categories and enemy damage tuning for this harness
    set_categories({"runtime", "enemy_ai", "harness", "resolver", "skill"})
    battle_controller.ENEMY_DAMAGE_MULTIPLIER = 1.0  # stress-test mode (adjust as needed)

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Battle Arena Test")

    clock = pygame.time.Clock()
    router = EventRouter()
    fx_system = FXSystem(router, screen.get_size())

    # Fonts, created after pygame.init()
    font_small = pygame.font.SysFont("consolas", 18)
    font_med   = pygame.font.SysFont("consolas", 24)
    font_large = pygame.font.SysFont("consolas", 32)
    fonts = (font_small, font_med, font_large)

    # Create canonical character instances for the party
    party_instances = new_default_party(level=1)

    # Temporary debug print so we can see the stats are coming through
    print("[DEBUG] Setia stats:", party_instances["setia"].stats)
    print("[DEBUG] Nyra stats:",  party_instances["nyra"].stats)
    print("[DEBUG] Kaira stats:", party_instances["kaira"].stats)

    initialize_defaults()
    debug_dump_skills()
    initialize_enemy_templates()

    arena = BattleArena(
        WIDTH,
        HEIGHT,
        SETIA_IDLE_FRAMES,
        NYRA_IDLE_FRAMES,
        KAIRA_IDLE_FRAMES,
        ENEMY_IDLE_FRAMES,
        fonts=fonts,
        region="grasslands",
        phase="day",
        router=router,
        party_instances=party_instances,
        party_keys=["setia", "nyra", "kaira"],
    )
    arena.fx_system = fx_system

    running = True
    last_terminal_state: str | None = None

    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if event.type == pygame.KEYDOWN:
                # Escape quits harness
                if event.key == pygame.K_ESCAPE:
                    running = False
                    continue

                # F3: unified debug snapshot
                if event.key == pygame.K_F3:
                    print("\n========== DEBUG SNAPSHOT (F3) ==========")
                    arena.fx_system.toggle_debug_auto_print()

                    controller = arena.controller
                    # Safe-guard: older controllers may not have this helper after refactors.
                    if hasattr(controller, "debug_print_targets"):
                        controller.debug_print_targets()

                    debug_print_all_statuses(controller.party, controller.enemies)

                    try:
                        fx_system.debug_print_recent_events()
                    except Exception:
                        print("[DEBUG] fx_system.debug_print_recent_events() unavailable")

                    print("========== END DEBUG SNAPSHOT ==========")
                    continue

                # F4: dump skill registry
                if event.key == pygame.K_F4:
                    print("\n========== DEBUG SKILL REGISTRY (F4) ==========")
                    debug_dump_skills()
                    print("========== END SKILL REGISTRY ==========")
                    try:
                        arena.fx_system.print_recent_events()
                    except Exception:
                        pass
                    continue

                # F6/F7: camera debug helpers
                if event.key == pygame.K_F6:
                    print("[DEBUG] Triggering camera_sweep → enemy side")
                    fx_system.camera_sweep(direction=(1.0, 0.0), distance=40.0, duration=0.18, hold=0.03)
                    continue

                if event.key == pygame.K_F7:
                    print("[DEBUG] Triggering basic skill cinematic")
                    fx_system.play_basic_skill_cinematic()
                    continue

            # Everything else goes to the arena
            arena.handle_event(event)

        arena.update(dt)
        fx_system.update(dt)

        # Terminal logging (once per transition)
        terminal_key = _terminal_key(arena)
        if terminal_key is not None:
            if last_terminal_state != terminal_key:
                if terminal_key == "defeat":
                    battle_log("harness", "Battle ended with DEFEAT (harness will reset or restart soon).")
                elif terminal_key == "victory":
                    battle_log("harness", "Battle ended with VICTORY (harness will reset or restart soon).")
                else:
                    battle_log("harness", "Battle ended (terminal phase reached).")
            last_terminal_state = terminal_key
        else:
            last_terminal_state = None

        screen.fill((0, 0, 0))
        arena.draw(screen)
        fx_system.draw(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
