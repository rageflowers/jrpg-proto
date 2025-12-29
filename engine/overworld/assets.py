from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional
import pygame


@dataclass
class OverworldAssets:
    """
    Simple surface cache. This is deliberately tiny for now.
    Presenters should NEVER call pygame.image.load directly.
    """
    root_dir: str = "assets"

    _images: Dict[str, pygame.Surface] = None

    def __post_init__(self) -> None:
        if self._images is None:
            self._images = {}

    def _resolve(self, path: str) -> str:
        # If a relative path is provided, resolve it under root_dir
        if self.root_dir and not os.path.isabs(path):
            return os.path.join(self.root_dir, path)
        return path

    def image(self, path: str, *, convert_alpha: bool = True) -> pygame.Surface:
        key = path
        if key in self._images:
            return self._images[key]

        real = self._resolve(path)
        surf = pygame.image.load(real)
        if convert_alpha:
            surf = surf.convert_alpha()
        else:
            surf = surf.convert()

        self._images[key] = surf
        return surf
