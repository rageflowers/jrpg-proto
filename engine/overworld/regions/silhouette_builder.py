# engine/overworld/regions/silhouette_builder.py
from __future__ import annotations

import pygame

from engine.overworld.regions.silhouettes import SilhouetteSystem, SilhouetteBand


def build_silhouettes(spec, *, assets, internal_w: int) -> SilhouetteSystem:
    system = SilhouetteSystem()

    for sb in getattr(spec, "silhouettes", ()) or ():
        img = assets.image(sb.image_path)

        preserve_aspect = bool(getattr(sb, "preserve_aspect", True))

        # Neutral defaults:
        # - if target_height_px is not provided (or <= 0), keep original height
        target_h = int(getattr(sb, "target_height_px", 0) or 0)

        # - if tile_width_mul is not provided, don't force a band width
        tile_mul = getattr(sb, "tile_width_mul", None)
        band_w = int(internal_w * float(tile_mul)) if tile_mul is not None else None

        # --- Build band image ---
        if target_h > 0:
            # We have an explicit authored target height
            if preserve_aspect:
                ow, oh = img.get_size()
                new_h = target_h
                new_w = max(1, int(ow * (new_h / max(1, oh))))
                piece = pygame.transform.smoothscale(img, (new_w, new_h))

                if band_w is None:
                    # Neutral: no tiling requested; just use the single piece
                    band_img = piece
                else:
                    # Tile horizontally to requested band width
                    bw = max(new_w, max(1, band_w))
                    band_img = pygame.Surface((bw, new_h), pygame.SRCALPHA)
                    x = 0
                    while x < bw:
                        band_img.blit(piece, (x, 0))
                        x += new_w
            else:
                # Legacy: scale directly to band width if provided; otherwise scale height only (keep width)
                ow, oh = img.get_size()
                new_h = target_h
                if band_w is None:
                    # Neutral: height set, width preserved by aspect if possible
                    new_w = max(1, int(ow * (new_h / max(1, oh))))
                    band_img = pygame.transform.smoothscale(img, (new_w, new_h))
                else:
                    band_img = pygame.transform.smoothscale(img, (max(1, band_w), new_h))
        else:
            # Neutral: no authored height => no scaling
            if band_w is None:
                band_img = img
            else:
                # Neutral: only width requested => tile original
                ow, oh = img.get_size()
                bw = max(1, band_w)
                band_img = pygame.Surface((bw, oh), pygame.SRCALPHA)
                x = 0
                while x < bw:
                    band_img.blit(img, (x, 0))
                    x += max(1, ow)

        band = SilhouetteBand(
            image=band_img,
            facing_angle=float(sb.facing_angle_rad),
            tier=int(sb.tier),
            fade_inner=float(sb.fade_inner_rad),
            fade_outer=float(sb.fade_outer_rad),
            yaw_factor=float(sb.yaw_factor),
            y_offset=int(sb.y_offset),
            alpha_max=int(sb.alpha_max),
            alpha_min=int(sb.alpha_min),
            horizon_overlap=int(sb.horizon_overlap),
        )
        system.add(band)

    return system
