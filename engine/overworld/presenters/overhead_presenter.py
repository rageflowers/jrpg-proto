# engine/overworld/presenters/overhead_presenter.py
from __future__ import annotations

import pygame
from engine.overworld.mode7_renderer_px import Mode7Camera


class OverheadPresenter:
    """
    Creation-mode overhead renderer.

    Contract:
      - Pure rendering (no collisions/exits/flags)
      - Uses the *existing* Mode7Camera pose as "world camera center"
        so camera authority remains singular (CameraController still owns it).
      - Draws the baked TMX ground texture as a top-down map.
    """

    def __init__(
        self,
        *,
        internal_surface: pygame.Surface,
        camera: Mode7Camera,
        ground_texture: pygame.Surface,
        get_player_rect,  # callable -> pygame.Rect (scene-owned)
        get_landmarks,
        get_aerial_actor=lambda: None,
    ) -> None:
        self.internal_surface = internal_surface
        self.camera = camera
        self.ground_texture = ground_texture
        self._get_player_rect = get_player_rect
        self._get_landmarks = get_landmarks
        self._get_aerial_actor = get_aerial_actor
        

    def draw(self, screen: pygame.Surface, dt: float) -> None:
        internal = self.internal_surface
        sw, sh = screen.get_size()
        iw, ih = internal.get_size()

        # Camera center in world px (we reuse Mode7Camera.x/y)
        cx = float(self.camera.x)
        cy = float(self.camera.y)

        tex = self.ground_texture
        tw, th = tex.get_size()

        # View rect in world coords (centered on camera)
        view = pygame.Rect(0, 0, iw, ih)
        view.center = (int(cx), int(cy))

        # Clamp view to texture bounds
        if view.left < 0:
            view.left = 0
        if view.top < 0:
            view.top = 0
        if view.right > tw:
            view.right = tw
        if view.bottom > th:
            view.bottom = th

        # If texture is smaller than view (unlikely), ensure non-negative size
        view.w = max(1, min(view.w, tw))
        view.h = max(1, min(view.h, th))

        # Clear
        internal.fill((0, 0, 0))

        # Blit the visible portion of the world map into internal
        # Place at (0,0) — since view is clamped, edges will be hard-cut for now (fine for MVP).
        sub = tex.subsurface(view)
        internal.blit(sub, (0, 0))
        
        # --- DEPTH SORT (top-down) ---
        # Rule: draw by "feet Y" (back-to-front). If player feet are above tree base,
        # player draws first -> tree drawn over player (player is behind).
        draw_items: list[tuple[float, str, object]] = []

        # Landmarks: use authored feet/root contact point (lm.pos.y)
        for lm in self._get_landmarks():
            img = getattr(lm, "image", None)
            if img is None:
                continue
            draw_items.append((float(lm.pos.y), "landmark", lm))

        # Player dot: use feet Y (rect.bottom). For the dot, we still draw at center,
        # but sorting uses bottom to match future sprite behavior.
        p = self._get_player_rect()
        draw_items.append((float(p.bottom), "player", p))

        draw_items.sort(key=lambda t: t[0])

        for _y, kind, obj in draw_items:
            if kind == "landmark":
                lm = obj
                img = lm.image

                # Apply authoring scale (overhead has no perspective scaling)
                scale = float(getattr(lm, "scale", getattr(lm, "scale_mul", 1.0)) or 1.0)
                if scale != 1.0:
                    w = int(img.get_width() * scale)
                    h = int(img.get_height() * scale)
                    if w <= 0 or h <= 0:
                        continue  # safety
                    img = pygame.transform.smoothscale(img, (w, h))

                lx = float(lm.pos.x)
                ly = float(lm.pos.y)

                sx = lx - view.left
                sy = ly - view.top

                # Anchor: bottom-center at (sx, sy)
                x0 = int(sx - img.get_width() * 0.5)
                y0 = int(sy - img.get_height())
                internal.blit(img, (x0, y0))

            else:
                # Player: draw FEET dot (depth anchor) + CENTER dot (body indicator)
                p = obj

                # Feet (depth anchor)
                fx = p.centerx - view.left
                fy = p.bottom - view.top
                pygame.draw.circle(internal, (255, 255, 255), (int(fx), int(fy)), 6)
                pygame.draw.circle(internal, (0, 0, 0), (int(fx), int(fy)), 6, 1)

                # Center (body indicator)
                cx = p.centerx - view.left
                cy = p.centery - view.top
                pygame.draw.circle(internal, (255, 255, 255), (int(cx), int(cy)), 2)
                pygame.draw.circle(internal, (0, 0, 0), (int(cx), int(cy)), 2, 1)

        actor = self._get_aerial_actor()
        if actor is not None:
            actor.draw(
                internal,
                cam_angle=float(self.camera.angle),
                horizon_y=int(self.camera.horizon),
                dt=dt,
                sky_t=0.0,
                view_left=float(view.left),
                view_top=float(view.top),
                world_w=float(tw),
                world_h=float(th),
            )

        # Upscale to screen
        screen.blit(pygame.transform.scale(internal, (sw, sh)), (0, 0))
