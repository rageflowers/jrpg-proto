import pygame

class GameClock:
    def __init__(self, cycle_length=20):  # seconds for a full 24h cycle
        self.time = 0.0
        self.cycle_length = cycle_length

    def update(self, dt):
        self.time = (self.time + dt) % self.cycle_length

    def get_phase(self):
        """Return (phase, t) where t is 0..1 blend within that phase"""
        t_day = self.time / self.cycle_length  # normalized 0..1 full cycle
        phase_len = 0.25  # each quarter of the day

        if t_day < 0.25:
            phase, local_t = "dawn", t_day / phase_len
        elif t_day < 0.5:
            phase, local_t = "day", (t_day - 0.25) / phase_len
        elif t_day < 0.75:
            phase, local_t = "sunset", (t_day - 0.5) / phase_len
        else:
            phase, local_t = "night", (t_day - 0.75) / phase_len

        return phase, local_t
