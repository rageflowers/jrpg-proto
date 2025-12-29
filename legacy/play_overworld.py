# play_overworld.py

import pygame
import sys

from engine.story.state import StoryState
from game.world.world_map import create_world
from game.overworld import WorldMapScene
from engine.battle.battle_arena import BattleArena

from engine.router import EventRouter
from engine.fx.system import FXSystem

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
FPS = 60
FADE_SPEED = 400  # alpha units per second for transitions


def main():
    # Existing story/world for future integration
    story = StoryState()
    world = create_world(story)

    pygame.init()
    pygame.display.set_caption("JRPG-Proto — Overworld Test")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    router = EventRouter()
    fx_system = FXSystem(router)

    # Start on overworld
    scene = WorldMapScene(SCREEN_WIDTH, SCREEN_HEIGHT, router=router)
    previous_scene = None

    # Fade / transition state
    fade_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)).convert_alpha()
    fade_alpha = 0
    transition_mode = "none"      # "none", "fade_out", "fade_in"
    transition_target = None      # the scene we'll switch to after fade_out
    
    if scene.request_map_change:
        next_id = scene.request_map_change
        transition_target = WorldMapScene(
            SCREEN_WIDTH, SCREEN_HEIGHT, next_id
        )
        scene.request_map_change = None
        transition_mode = "fade_out"

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                # Only forward input when not transitioning
                if transition_mode == "none":
                    scene.handle_event(event)

        # --- Update current scene (only when not fading) ---
        if transition_mode == "none":
            scene.update(dt)

                # --- Decide if we should start a transition ---
        if transition_mode == "none":
            if isinstance(scene, WorldMapScene):
                if getattr(scene, "pending_battle", None):
                    encounter = scene.pending_battle
                    region = getattr(scene, "region", "grasslands")
                    phase = scene.clock.get_phase() if hasattr(scene, "clock") else "day"
                    scene.pending_battle = None

                    previous_scene = scene
                    transition_target = BattleArena(
                        SCREEN_WIDTH,
                        SCREEN_HEIGHT,
                        encounter.setia_frames,   # or however you currently feed frames in
                        encounter.nyra_frames,
                        encounter.kaira_frames,
                        encounter.enemy_frames,
                        region=region,
                        phase=phase,
                        router=router,  # NEW
                    )
                    transition_mode = "fade_out"

                elif getattr(scene, "request_map_change", None):
                    next_map_id = scene.request_map_change
                    scene.request_map_change = None

                    transition_target = WorldMapScene(
                        SCREEN_WIDTH,
                        SCREEN_HEIGHT,
                        map_id=next_map_id,
                        router=router,  # NEW
                    )
                    transition_mode = "fade_out"

            # Battle -> Overworld or Quit
            elif isinstance(scene, BattleArena) and getattr(scene, "done", False):
                if scene.result in ("victory", "escape") and previous_scene is not None:
                    transition_target = previous_scene
                    previous_scene = None
                    transition_mode = "fade_out"
                else:
                    # defeat or weird state -> exit for now
                    running = False

        # --- Draw current scene ---
        screen.fill((0, 0, 0))
        scene.draw(screen)

        # --- Apply fade effect ---
        if transition_mode == "fade_out":
            fade_alpha += FADE_SPEED * dt
            if fade_alpha >= 255:
                fade_alpha = 255
                # Swap scene at peak darkness
                if transition_target is not None:
                    scene = transition_target
                    transition_target = None
                transition_mode = "fade_in"

            fade_surface.set_alpha(int(fade_alpha))
            screen.blit(fade_surface, (0, 0))

        elif transition_mode == "fade_in":
            fade_alpha -= FADE_SPEED * dt
            if fade_alpha <= 0:
                fade_alpha = 0
                transition_mode = "none"

            fade_surface.set_alpha(int(fade_alpha))
            screen.blit(fade_surface, (0, 0))

        # --- Flip ---
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
