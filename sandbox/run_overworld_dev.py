# run_overworld_dev.py
from __future__ import annotations

import argparse
import sys
import pygame

from engine.overworld.overworld_scene import OverworldScene, OverworldConfig


def _parse_size(s: str) -> tuple[int, int]:
    try:
        a, b = s.lower().replace("x", " ").split()
        return int(a), int(b)
    except Exception:
        raise argparse.ArgumentTypeError(f"Expected WxH (e.g. 1024x768), got: {s!r}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="JRPG-Proto Overworld (DEV harness)")
    p.add_argument("--region", default="velastra_highlands", help="Starting region id")
    p.add_argument("--tmx", default=None, help="Optional TMX override (quick testing)")
    p.add_argument("--spawn", default="600,340", help="Spawn px as 'x,y' (default: 600,340)")
    p.add_argument("--seed", default=None, type=int, help="Optional RNG seed")
    p.add_argument("--window", default="1024x768", type=_parse_size, help="Window size WxH")
    p.add_argument("--internal", default="512x384", type=_parse_size, help="Internal render size WxH")
    p.add_argument("--no-strafe", action="store_true", help="Disable strafe (A/D)")
    p.add_argument("--no-encounters", action="store_true", help="Disable encounter ticking")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = build_arg_parser().parse_args(argv)

    try:
        sx_str, sy_str = args.spawn.split(",")
        spawn_px = (int(sx_str.strip()), int(sy_str.strip()))
    except Exception:
        print(f"[DEV] Invalid --spawn value: {args.spawn!r}. Expected 'x,y' like 600,340")
        return 2

    pygame.init()
    try:
        screen = pygame.display.set_mode(args.window)
        pygame.display.set_caption("Overworld DEV")

        cfg = OverworldConfig(
            region_id=args.region,
            tmx_path=args.tmx,
            window_size=args.window,
            internal_size=args.internal,
            allow_strafe=(not args.no_strafe),
            spawn_px=spawn_px,
            seed=args.seed,
        )

        scene = OverworldScene(cfg)
        if args.no_encounters:
            scene.debug_encounters = False

        clock = pygame.time.Clock()
        running = True

        print("[DEV] Controls:")
        print("  ESC          Quit")
        print("  F1           Toggle debug overlay")
        print("  F2           Clear pending battle (if any)")
        print("  F3           Toggle encounter debug")
        print("  (WASD/Arrows movement, Q/E turn in Mode7 regions)")

        while running:
            dt = clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

                    elif event.key == pygame.K_F1:
                        scene.toggle_debug()

                    elif event.key == pygame.K_F2:
                        scene.clear_pending_battle()

                    elif event.key == pygame.K_F3:
                        scene.debug_encounters = not scene.debug_encounters
                        print("[DEV] debug_encounters =", scene.debug_encounters)

            scene.update(dt)

            # Draw
            screen.fill((0, 0, 0))
            scene.draw(screen, dt)
            scene.draw_hud(screen)
            pygame.display.flip()

    finally:
        pygame.quit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
