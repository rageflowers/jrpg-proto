import os
import pygame
from game.debug.animated_sprite import AnimatedSprite


class Setia(pygame.sprite.Sprite):
    def __init__(self, root_folder: str, start_pos=(400, 300), speed=220):
        super().__init__()
        print("DEBUG: Setia initialized from", __file__)

        #
        # ---- LOAD SPRITE PATHS ----
        #
        right_paths = [
            os.path.join(root_folder, f"setia_right_{i}.png")
            for i in (1, 2, 3)
        ]
        left_paths = [
            os.path.join(root_folder, f"setia_left_{i}.png")
            for i in (1, 2, 3)
        ]
        up_paths = [
            os.path.join(root_folder, f"setia_up_{i}.png")
            for i in (1, 2, 3)
        ]
        down_paths = [
            os.path.join(root_folder, f"setia_down_{i}.png")
            for i in (1, 2, 3)
        ]

        # Determine base size from right-facing frame
        temp_frames = [pygame.image.load(p).convert_alpha() for p in right_paths]
        base_w, base_h = temp_frames[0].get_size()

        scale_factor = 0.1  # tweak if you want her larger/smaller
        target_size = (int(base_w * scale_factor), int(base_h * scale_factor))

        # Animations
        self.anim_right = AnimatedSprite(right_paths, target_size=target_size)
        self.anim_left = AnimatedSprite(left_paths, target_size=target_size)
        self.anim_up = AnimatedSprite(up_paths, target_size=target_size)
        self.anim_down = AnimatedSprite(down_paths, target_size=target_size)

        # State
        self.current_anim = self.anim_down
        self.facing = "down"
        self.speed = speed
        self.velocity = pygame.math.Vector2(0, 0)

        self.image = self.current_anim.get_frame()
        self.rect = self.image.get_rect()
        self.rect.center = start_pos

    # ---- Direction helpers ----

    def face_right(self):
        self.current_anim = self.anim_right
        self.facing = "right"

    def face_left(self):
        self.current_anim = self.anim_left
        self.facing = "left"

    def face_up(self):
        self.current_anim = self.anim_up
        self.facing = "up"

    def face_down(self):
        self.current_anim = self.anim_down
        self.facing = "down"

    # ---- Input + movement ----

    def handle_input(self, keys):
        """
        keys: pygame.key.get_pressed()
        Updates velocity and facing based on WASD / arrow keys.
        """
        vx = 0
        vy = 0

        # Horizontal
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            vx += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            vx -= 1

        # Vertical
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            vy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            vy += 1

        direction = pygame.math.Vector2(vx, vy)
        if direction.length_squared() > 0:
            direction = direction.normalize()
            self.velocity = direction * self.speed

            # Pick facing based on dominant axis
            if abs(direction.x) > abs(direction.y):
                if direction.x > 0:
                    self.face_right()
                else:
                    self.face_left()
            else:
                if direction.y > 0:
                    self.face_down()
                else:
                    self.face_up()
        else:
            # No input
            self.velocity.update(0, 0)
            # Later we can add "idle" animations here if we want

    def update(self, dt: float):
        # Move
        if self.velocity.length_squared() > 0:
            self.rect.x += self.velocity.x * dt
            self.rect.y += self.velocity.y * dt

        # Animate
        self.current_anim.update(dt)
        center = self.rect.center
        self.image = self.current_anim.get_frame()
        self.rect = self.image.get_rect(center=center)
