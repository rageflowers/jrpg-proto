# ambient_layer.py

import pygame
import random
import math

class AmbientParticle:
    def __init__(self, x, y, color, lifetime, drift, speed):
        self.x = x
        self.y = y
        self.color = color
        self.lifetime = lifetime
        self.age = 0.0
        self.drift = drift  # horizontal drift amplitude
        self.speed = speed  # vertical speed
        self.alpha = 255

    def update(self, dt):
        self.age += dt
        if self.age >= self.lifetime:
            self.alpha = 0
            return
        # gentle drift and fade
        self.x += math.sin(self.age * 3.0) * self.drift * dt
        self.y -= self.speed * dt
        self.alpha = max(0, int(255 * (1 - self.age / self.lifetime)))

    def draw(self, surface, offset=(0, 0)):
            if self.alpha > 0:
                s = pygame.Surface((2, 2), pygame.SRCALPHA)
                s.fill((*self.color, self.alpha))
                ox, oy = offset
                surface.blit(s, (int(self.x + ox), int(self.y + oy)))


class AmbientLayer:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.particles = []

    def spawn(self, count, color, speed, drift, lifetime):
        for _ in range(count):
            x = random.uniform(0, self.width)
            y = random.uniform(0, self.height)
            self.particles.append(AmbientParticle(x, y, color, lifetime, drift, speed))

    def update(self, dt):
        for p in list(self.particles):
            p.update(dt)
            if p.alpha <= 0:
                self.particles.remove(p)

    def draw(self, surface, offset=(0, 0)):
        for p in self.particles:
            p.draw(surface, offset)
