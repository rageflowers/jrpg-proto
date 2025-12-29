import os
import sys
from pathlib import Path

# --- ensure project root is importable ---
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import pygame
from engine.overworld.overworld_scene import OverworldScene, OverworldConfig


def main() -> int:
    pygame.init()
    pygame.display.set_caption("Overworld — Mode-7 Video Renderer")

    cfg = OverworldConfig(
        tmx_path="assets/maps/velastra_highlands.tmx",
        window_size=(1024, 768),
        internal_size=(512, 384),
        allow_strafe=True,
    )

    screen = pygame.display.set_mode(cfg.window_size)
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 16)

    scene = OverworldScene(cfg)
    print("[EXITS]")
    for name, r in scene.world.exits.items():
        print(f"  {name}: {r}")

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F1:
                scene.toggle_debug()
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F10:
                scene.clear_pending_battle()
                print("[DEBUG] Cleared pending battle")
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F2:
                scene.camera_ctl.takeover()
                scene.camera_ctl.pan_to(
                    x=scene.pos.x + 300,
                    y=scene.pos.y,
                    angle=scene.camera.angle + 0.5,
                    duration_s=2.0,
                )
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F3:
                scene.camera_ctl.release(blend_s=0.75)

        # update + exit hook
        exit_name = scene.update(dt)
        if exit_name:
            print(f"[EXIT] {exit_name}")

        # --- HUD ---
        fps = clock.get_fps()
        cam = scene.camera
        hud = [
            f"{fps:5.1f} FPS",
            "W/S move   A/D strafe   Q/E turn   ESC quit",
            f"pos=({scene.pos.x:.1f}, {scene.pos.y:.1f})",
            f"angle={cam.angle:.3f}",
            f"horizon={cam.horizon}  focal={cam.focal_len}  scale={cam.scale:.1f}  alt={cam.alt:.2f}",

        ]
        y = 8
        for line in hud:
            screen.blit(font.render(line, True, (255, 255, 255)), (10, y))
            y += 18
        scene.draw(screen, dt)
        scene.draw_hud(screen)

        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
