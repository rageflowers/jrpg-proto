import pygame
import math
from engine.overworld.mode7_renderer_px import Mode7Camera, draw_mode7_floor_pixelarray


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def main():
    pygame.init()
    screen = pygame.display.set_mode((1024, 768))
    pygame.display.set_caption("Mode-7 PixelArray Test Harness")

    internal_size = (512, 384)
    internal = pygame.Surface(internal_size).convert()

    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 18)

    # Load tileable ground
    ground = pygame.image.load("assets/ground_tileable.png").convert()

    # Camera
    cam = Mode7Camera()
    cam.x = 0.0
    cam.y = 0.0
    cam.angle = 0.0

    cam.horizon = int(internal_size[1] * 0.6)
    cam.height = 140.0
    cam.scale = 520.0
    cam.near = 220.0
    cam.min_dist = 4.0
    cam.look_px = 0.0

    render_step = 2

    pygame.key.set_repeat(180, 35)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                # Horizon
                if event.key == pygame.K_i: cam.horizon += 5
                if event.key == pygame.K_k: cam.horizon -= 5

                # Near
                if event.key == pygame.K_o: cam.near += 10
                if event.key == pygame.K_l: cam.near -= 10

                # Scale
                if event.key == pygame.K_u: cam.scale += 20
                if event.key == pygame.K_j: cam.scale -= 20

                # Height
                if event.key == pygame.K_y: cam.height += 10
                if event.key == pygame.K_h: cam.height -= 10

                # min_dist
                if event.key == pygame.K_t: cam.min_dist += 0.1
                if event.key == pygame.K_g: cam.min_dist -= 0.1

                # Render step
                if event.key == pygame.K_LEFTBRACKET:  render_step = max(1, render_step - 1)
                if event.key == pygame.K_RIGHTBRACKET: render_step = min(8, render_step + 1)

                cam.horizon = int(clamp(cam.horizon, 0, internal_size[1] - 1))
                cam.near = clamp(cam.near, 0, 600)
                cam.scale = clamp(cam.scale, 50, 2000)
                cam.height = clamp(cam.height, 10, 600)
                cam.min_dist = clamp(cam.min_dist, 0.1, 10)

        # Turn with Q/E
        keys = pygame.key.get_pressed()
        turn_input = int(keys[pygame.K_e]) - int(keys[pygame.K_q])
        cam.angle += turn_input * 1.5 * dt

        # Auto-look
        LOOK_MAX = 110.0
        cam.look_px += ((LOOK_MAX * turn_input) - cam.look_px) * 0.18

        # Move forward/back for testing
        fx = math.cos(cam.angle)
        fy = math.sin(cam.angle)
        if keys[pygame.K_w]:
            cam.x += fx * 120 * dt
            cam.y += fy * 120 * dt
        if keys[pygame.K_s]:
            cam.x -= fx * 120 * dt
            cam.y -= fy * 120 * dt

        # Draw
        internal.fill((30, 30, 40))
        draw_mode7_floor_pixelarray(
            internal,
            ground,
            cam,
            step=render_step,
            wrap=True,
        )

        scaled = pygame.transform.scale(internal, (1024, 768))
        screen.blit(scaled, (0, 0))

        hud = [
            "Mode-7 Renderer Test (No TMX)",
            "W/S move | Q/E turn | ESC quit",
            "",
            f"horizon (I/K): {cam.horizon}",
            f"near    (O/L): {cam.near:.1f}",
            f"scale   (U/J): {cam.scale:.1f}",
            f"height  (Y/H): {cam.height:.1f}",
            f"min_dist(T/G): {cam.min_dist:.2f}",
            f"step   ([/]): {render_step}",
        ]

        y = 10
        for line in hud:
            screen.blit(font.render(line, True, (255,255,255)), (10, y))
            y += 20

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
