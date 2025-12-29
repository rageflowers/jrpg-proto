import math
import pygame


class Mode7Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.angle = 0.0

        # TUNABLES (match the repo’s “feel”)
        self.horizon = 230          # move up/down
        self.focal_len = 220        # repo uses 250
        self.scale = 90.0          # repo uses 100
        self.alt = 1.0              # “pseudo altitude” in repo

        # optional: turning feel
        self.vanish_shift = 0.0     # pixels; try +/-40 later

def draw_mode7_floor_video_pixelarray(
    dst: pygame.Surface,
    ground: pygame.Surface,
    cam: Mode7Camera,
    *,
    step: int = 2,
    wrap: bool = True,
    fog_strength: int = 230,
) -> None:
    w, h = dst.get_size()
    gw, gh = ground.get_size()

    # Work surface (low-res) then scale up
    if step > 1:
        rw, rh = w // step, h // step
        work = pygame.Surface((rw, rh)).convert()

        # DO NOT resample the sky into work.
        # We only draw the floor into work, then composite below horizon.
        work.fill((0, 0, 0))
    else:
        rw, rh = w, h
        work = dst

    src = pygame.PixelArray(ground)
    out = pygame.PixelArray(work)

    half_w = rw // 2
    horizon = int(cam.horizon / step)
    focal = cam.focal_len / step
    vanish = cam.vanish_shift / step

    sin_a = math.sin(cam.angle)
    cos_a = math.cos(cam.angle)

    # Draw ONLY below horizon so sky stays intact
    start_j = max(horizon, 0)
    for i in range(rw):
        x = (half_w - i) + vanish

        for j in range(start_j, rh):
            y = (j - horizon) + focal
            z = (j - horizon) + cam.alt
            inv_z = 1.0 / max(z, 0.0001)

            # rotate
            px = x * cos_a - y * sin_a
            py = x * sin_a + y * cos_a

            tx = cam.x + (px * inv_z) * cam.scale
            ty = cam.y + (py * inv_z) * cam.scale

            if wrap:
                ix = int(tx) % gw
                iy = int(ty) % gh
            else:
                ix = int(tx)
                iy = int(ty)
                if ix < 0: ix = 0
                elif ix >= gw: ix = gw - 1
                if iy < 0: iy = 0
                elif iy >= gh: iy = gh - 1

            col = src[ix, iy]
            c = ground.unmap_rgb(col)
            r, g, b = c.r, c.g, c.b

            depth = min(max(2.5 * (z / max(rh // 2, 1)), 0.0), 1.0)
            fog = int((1.0 - depth) * fog_strength)

            r = 255 if r + fog > 255 else r + fog
            g = 255 if g + fog > 255 else g + fog
            b = 255 if b + fog > 255 else b + fog

            out[i, j] = work.map_rgb((r, g, b))

    del out
    del src

    if step > 1:
        scaled = pygame.transform.scale(work, (w, h))

        full_horizon = int(cam.horizon)
        old_clip = dst.get_clip()
        try:
            dst.set_clip(pygame.Rect(0, full_horizon, w, h - full_horizon))
            dst.blit(scaled, (0, 0))
        finally:
            dst.set_clip(old_clip)


