import pygame
from setia_sprite import Setia


def main():
    print("DEBUG: Running test_setia_sprite.main()")

    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Setia Sprite Test")
    clock = pygame.time.Clock()

    SPRITE_FOLDER = "assets/sprites"

    setia = Setia(SPRITE_FOLDER, start_pos=(400, 300))
    all_sprites = pygame.sprite.Group(setia)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        # Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # Input
        keys = pygame.key.get_pressed()
        setia.handle_input(keys)

        # Update
        all_sprites.update(dt)

        # Draw
        screen.fill((30, 30, 40))
        all_sprites.draw(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
