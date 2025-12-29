import pygame


class AnimatedSprite:
    def __init__(self, image_paths, target_size=None, frame_duration=0.12):
        print("DEBUG: AnimatedSprite loaded from", __file__)

        frames = [pygame.image.load(path).convert_alpha() for path in image_paths]

        if target_size is None and frames:
            target_size = frames[0].get_size()

        self.frames = [
            pygame.transform.smoothscale(frame, target_size)
            for frame in frames
        ]

        self.frame_duration = frame_duration
        self.current_time = 0.0
        self.current_frame = 0

    def update(self, dt: float):
        self.current_time += dt
        if self.current_time >= self.frame_duration:
            self.current_time = 0.0
            self.current_frame = (self.current_frame + 1) % len(self.frames)

    def get_frame(self):
        return self.frames[self.current_frame]
