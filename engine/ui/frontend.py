import pygame
import sys

# -------- Virtual resolution (design space) --------
VIRTUAL_W = 256
VIRTUAL_H = 224

# Initial window scale (3x for comfy size)
INITIAL_SCALE = 3

def create_window(scale=INITIAL_SCALE, fullscreen=False):
    flags = pygame.RESIZABLE
    if fullscreen:
        flags |= pygame.FULLSCREEN
        display_info = pygame.display.Info()
        width, height = display_info.current_w, display_info.current_h
    else:
        width = VIRTUAL_W * scale
        height = VIRTUAL_H * scale

    window = pygame.display.set_mode((width, height), flags)
    pygame.display.set_caption("JRPG-Proto — Frontend")
    return window

def compute_scaled_rect(window_size):
    """Compute scaled size & position to keep aspect ratio and crisp pixels."""
    win_w, win_h = window_size
    # maximum integer scale that fits
    scale = max(1, min(win_w // VIRTUAL_W, win_h // VIRTUAL_H))
    # fallback: if somehow tiny window, just use scale 1
    surf_w = VIRTUAL_W * scale
    surf_h = VIRTUAL_H * scale
    x = (win_w - surf_w) // 2
    y = (win_h - surf_h) // 2
    return scale, pygame.Rect(x, y, surf_w, surf_h)

def draw_virtual_scene(surface, t):
    """Temporary mock scene to visualize layout & scaling."""
    surface.fill((0, 0, 16))  # dark background

    # Top area: 'world / battle sprites'
    pygame.draw.rect(surface, (40, 40, 120), (0, 0, VIRTUAL_W, 120))
    # Fake party positions
    pygame.draw.rect(surface, (200, 220, 255), (10, 60, 24, 24))   # Setia slot
    pygame.draw.rect(surface, (230, 210, 255), (40, 60, 24, 24))   # Nyra slot
    pygame.draw.rect(surface, (180, 180, 255), (70, 60, 24, 24))   # Kaira slot
    # Fake enemy slots
    pygame.draw.rect(surface, (255, 120, 120), (VIRTUAL_W - 34, 20, 24, 24))
    pygame.draw.rect(surface, (255, 180, 140), (VIRTUAL_W - 64, 40, 24, 24))

    # Middle: maybe messages
    msg_box_y = 120
    pygame.draw.rect(surface, (10, 10, 40), (0, msg_box_y, VIRTUAL_W, 40))
    # Simple blinking text indicator
    if (t // 500) % 2 == 0:
        font = pygame.font.SysFont("Consolas", 10)
        txt = font.render("Setia uses Palm of Aether! (CRITICAL!)", True, (240, 240, 255))
        surface.blit(txt, (6, msg_box_y + 8))

    # Bottom: HUD mock
    hud_y = 164
    pygame.draw.rect(surface, (4, 4, 24), (0, hud_y, VIRTUAL_W, VIRTUAL_H - hud_y))
    font = pygame.font.SysFont("Consolas", 8)

    # Example party HUD lines
    lines = [
        "Setia  HP 34/34  MP 6/6   Rosary of Aether",
        "Nyra   HP 26/26  MP12/12  Celestial Staff",
        "Kaira  HP 22/22  MP 8/8   Eclipsed Fang",
    ]
    for i, line in enumerate(lines):
        txt = font.render(line, True, (220, 220, 255))
        surface.blit(txt, (4, hud_y + 4 + i * 10))

def main():
    pygame.init()
    pygame.font.init()

    window = create_window()
    virtual_surface = pygame.Surface((VIRTUAL_W, VIRTUAL_H))

    clock = pygame.time.Clock()
    fullscreen = False

    while True:
        dt = clock.tick(60)
        t = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.VIDEORESIZE and not fullscreen:
                # Window resized; nothing special, scaling handled each frame
                pass

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_F11:
                    # Toggle fullscreen
                    fullscreen = not fullscreen
                    window = create_window(fullscreen=fullscreen)

        # Draw your game to the virtual surface at fixed resolution
        draw_virtual_scene(virtual_surface, t)

        # Scale to fit current window with integer scale + letterboxing
        win_size = window.get_size()
        scale, dest_rect = compute_scaled_rect(win_size)

        window.fill((0, 0, 0))  # black bars
        scaled = pygame.transform.scale(virtual_surface, (dest_rect.w, dest_rect.h))
        window.blit(scaled, dest_rect.topleft)

        pygame.display.flip()

if __name__ == "__main__":
    main()
