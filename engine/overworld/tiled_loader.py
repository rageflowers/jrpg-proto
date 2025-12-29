# engine/overworld/tiled_loader.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Iterable, Tuple
import os
import math

import pygame
import pytmx


# -----------------------------
# Core world rects (collision/exits/spawns)
# -----------------------------

@dataclass(frozen=True)
class SpawnPoint:
    rect: pygame.Rect
    angle: float | None = None  # radians

@dataclass
class WorldRects:
    collision_rects: List[pygame.Rect]
    exits: Dict[str, pygame.Rect]
    spawns: Dict[str, SpawnPoint]
    map_size_px: tuple[int, int]

# -----------------------------
# Landmarks (TMX-authored props)
# -----------------------------

@dataclass
class LandmarkDef:
    """Definition of a single overworld landmark/prop authored in Tiled."""
    image_path: str
    pos: pygame.Vector2  # world pixel coords (same space as baked TMX)

    # Authoring multiplier; perspective scaling is handled by renderer/projector.
    scale: float = 1.0
    sway: bool = False

    # Optional: nudge sprite feet up/down after projection.
    # Positive pushes sprite DOWN (because y is computed as base_y - spr_h + offset).
    base_offset_px: int = 0

    # Authorable safety bounds (optional per object).
    # If you omit them in Tiled, these defaults apply.
    min_scale: float = 0.05      # below this: skip drawing
    max_scale: float = 8.0       # above this: clamp (prevents insane surfaces)
    max_size_px: int = 1024      # hard cap for smoothscale width/height (each)


# -----------------------------
# Layer iter helpers
# -----------------------------

def _iter_object_groups_with_parent(layers, parent_name: str | None = None):
    """
    Yield (object_group_layer, parent_group_name) for all object layers,
    including those nested under Tiled group layers.
    """
    for layer in layers:
        sublayers = getattr(layer, "layers", None)
        if sublayers:
            # This is a group layer (or behaves like one)
            yield from _iter_object_groups_with_parent(sublayers, parent_name=(layer.name or parent_name))

        if isinstance(layer, pytmx.TiledObjectGroup):
            yield layer, parent_name


def _iter_object_groups_flat(layers) -> Iterable[pytmx.TiledObjectGroup]:
    """Yield all object layers (including those nested under group layers)."""
    for layer, _parent in _iter_object_groups_with_parent(layers):
        yield layer


def _layer_name_matches(layer_name: str | None, want: str) -> bool:
    return (layer_name or "").strip().lower() == want.strip().lower()


def _rect_from_obj(obj) -> Optional[pygame.Rect]:
    """Convert a Tiled object to a pygame.Rect, dropping zero/negative sizes."""
    try:
        r = pygame.Rect(int(obj.x), int(obj.y), int(obj.width), int(obj.height))
    except Exception:
        return None
    if r.w <= 0 or r.h <= 0:
        return None
    return r


def _load_rects_from_object_layer(
    tmx: pytmx.TiledMap,
    *,
    layer_name: str,
    debug_layers: bool = False,
) -> List[pygame.Rect]:
    """Load unnamed rects from an object layer (e.g., collision)."""
    out: List[pygame.Rect] = []

    for layer in _iter_object_groups_flat(tmx.layers):
        if debug_layers:
            print(f"[TMX] object layer: {layer.name} ({len(layer)} objects)")

        if not _layer_name_matches(layer.name, layer_name):
            continue

        for obj in layer:
            r = _rect_from_obj(obj)
            if r is not None:
                out.append(r)

    return out


def _load_named_rects_from_object_layer(
    tmx: pytmx.TiledMap,
    *,
    layer_name: str,
    debug_layers: bool = False,
    require_name: bool = True,
) -> Dict[str, pygame.Rect]:
    """Load name->rect dict from an object layer (e.g., exits, spawns)."""
    out: Dict[str, pygame.Rect] = {}

    for layer in _iter_object_groups_flat(tmx.layers):
        if debug_layers:
            print(f"[TMX] object layer: {layer.name} ({len(layer)} objects)")

        if not _layer_name_matches(layer.name, layer_name):
            continue

        for obj in layer:
            name = (obj.name or "").strip()
            if require_name and not name:
                continue

            r = _rect_from_obj(obj)
            if r is None:
                continue

            # If a name is missing and require_name=False, skip silently (or you could auto-number).
            if not name:
                continue

            out[name] = r

    return out


# -----------------------------
# Landmarks (TMX-authored props)
# -----------------------------

def load_landmark_defs(
    tmx_path: str,
    *,
    landmarks_layer_name: str = "Landmarks",
    default_scale: float = 1.0,
    strict: bool = False,
    debug: bool = False,
) -> List[LandmarkDef]:
    """Load landmark objects from TMX object layers.

    Supports BOTH authoring styles:

    A) Single object layer named `landmarks_layer_name` (default: "Landmarks")

    B) A GROUP layer named `landmarks_layer_name` that contains any number of
       object sublayers (e.g. "trees", "rocks", "signs"). In this case, all
       objects in those sublayers are treated as landmarks.

    For each object:
      - position: (obj.x, obj.y) is treated as the *ground contact point* (feet)
      - custom properties:
          image_path: string path to sprite (recommended)
          (aliases: path, sprite, src)
          scale: float (optional)
          base_offset_px / base_offset: int (optional)
          min_scale: float (optional)
          max_scale: float (optional)
          max_size_px: int (optional)

    Path handling:
      - Converts backslashes to forward slashes
      - If path is relative, tries:
          1) relative to TMX directory
          2) as-given (relative to cwd)
      - Leaves absolute paths alone

    If strict=False, objects missing an image are skipped.
    """
    tmx = pytmx.load_pygame(tmx_path)
    tmx_dir = Path(tmx_path).resolve().parent

    out: List[LandmarkDef] = []
    layer_found = False
    want = landmarks_layer_name.strip().lower()

    def _norm_path(p: str) -> str:
        p = (p or "").strip().strip('"').strip("'")
        return p.replace("\\", "/")

    def _resolve_path(p: str) -> str:
        p = _norm_path(p)
        if not p:
            return ""
        if os.path.isabs(p):
            return p
        cand1 = (tmx_dir / p).resolve()
        if cand1.exists():
            return str(cand1)
        return p

    def _float_prop(props: dict, key: str, default: float) -> float:
        try:
            return float(props.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    def _int_prop(props: dict, key: str, default: int) -> int:
        try:
            return int(props.get(key, default))
        except (TypeError, ValueError):
            return int(default)

    # Iterate object layers (including nested), and accept:
    #  - layer.name == "Landmarks"
    #  - OR parent group name == "Landmarks"
    for layer, parent_name in _iter_object_groups_with_parent(tmx.layers):
        lname = (layer.name or "").strip().lower()
        pname = (parent_name or "").strip().lower()

        if lname != want and pname != want:
            continue

        layer_found = True

        for obj in layer:
            props = getattr(obj, "properties", {}) or {}

            # --- image path ---
            raw = (
                props.get("image_path")
                or props.get("path")
                or props.get("sprite")
                or props.get("src")
                or ""
            )
            image_path = _resolve_path(str(raw))

            if not image_path:
                # Allow using object NAME as a path (handy for quick authoring)
                name = _norm_path(obj.name or "")
                if name and ("/" in name or name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))):
                    image_path = _resolve_path(name)

            if not image_path:
                if strict:
                    raise ValueError(
                        f"Landmark object missing image_path/path (layer={landmarks_layer_name!r}, tmx={tmx_path!r})"
                    )
                if debug:
                    print("[TMX][Landmarks] skipping object with no image_path:", obj)
                continue

            # --- authoring props ---
            scale = _float_prop(props, "scale", default_scale)
            sway = bool(props.get("sway", False))

            bo = props.get("base_offset_px", props.get("base_offset", 0))
            base_offset_px = _int_prop({"_": bo}, "_", 0)

            min_scale = _float_prop(props, "min_scale", 0.05)
            max_scale = _float_prop(props, "max_scale", 8.0)
            max_size_px = _int_prop(props, "max_size_px", 1024)

            # Treat (x, y) as the ground contact point (feet).
            pos = pygame.Vector2(float(obj.x), float(obj.y))

            if debug:
                print(
                    "[TMX][Landmark]",
                    f"pos=({pos.x:.1f},{pos.y:.1f})",
                    f"img={image_path!r}",
                    f"scale={scale}",
                    f"base_offset_px={base_offset_px}",
                    f"min_scale={min_scale}",
                    f"max_scale={max_scale}",
                    f"max_size_px={max_size_px}",
                )

            out.append(LandmarkDef(
                image_path=image_path,
                pos=pos,
                scale=scale,
                sway=sway,
                base_offset_px=base_offset_px,
                min_scale=min_scale,
                max_scale=max_scale,
                max_size_px=max_size_px,
            ))

    if strict and not layer_found:
        raise ValueError(f"No Landmarks layer/group named {landmarks_layer_name!r} found in TMX: {tmx_path!r}")

    return out


# -----------------------------
# TMX object layers: collision + exits + spawns
# -----------------------------

def load_world_rects(
    tmx_path: str,
    *,
    collision_layer_name: str = "Collision",
    exits_layer_name: str = "Exits",
    spawns_layer_name: str = "spawns",
    debug_layers: bool = False,
) -> WorldRects:
    """
    Reads object layers from a TMX:
      - collision rects from layer `collision_layer_name`
      - named exit rects from layer `exits_layer_name` (object.name required)
      - named spawn rects from layer `spawns_layer_name` (object.name required)

    Note: layer-name matching is case-insensitive. Recommended authoring:
      - gameplay semantics: lowercase ('collision', 'exits', 'spawns')
      - landmark/content: 'Landmarks' group
    """
    tmx = pytmx.load_pygame(tmx_path)
    map_w_px = tmx.width * tmx.tilewidth
    map_h_px = tmx.height * tmx.tileheight

    collision = _load_rects_from_object_layer(tmx, layer_name=collision_layer_name, debug_layers=debug_layers)
    exits = _load_named_rects_from_object_layer(tmx, layer_name=exits_layer_name, debug_layers=debug_layers)
    spawns: dict[str, SpawnPoint] = {}

    for layer in _iter_object_groups_flat(tmx.layers):
        if not _layer_name_matches(layer.name, spawns_layer_name):
            continue

        for obj in layer:
            name = (obj.name or "").strip()
            if not name:
                continue

            rect = _rect_from_obj(obj)
            if rect is None:
                continue

            angle = None
            props = getattr(obj, "properties", {}) or {}

            if "angle" in props:
                try:
                    angle = math.radians(float(props["angle"]))
                except (TypeError, ValueError):
                    angle = None

            spawns[name] = SpawnPoint(rect=rect, angle=angle)
            print(
                f"[SPAWN DEBUG] name={name!r} "
                f"properties={getattr(obj, 'properties', None)} "
                f"type(properties)={type(getattr(obj, 'properties', None))}"
            )

    return WorldRects(
        collision_rects=collision,
        exits=exits,
        spawns=spawns,
        map_size_px=(map_w_px, map_h_px),
    )


# -----------------------------
# TMX bake: tile layers -> single ground texture surface
# -----------------------------

def bake_tmx_ground_surface(
    tmx_path: str,
    *,
    include_layers: Optional[List[str]] = None,
    exclude_layers: Optional[List[str]] = None,
) -> pygame.Surface:
    """
    Bakes TMX tile layers into a single Surface (full map size in pixels).
    This surface can be used as the 'ground texture' for floorcasting.

    - include_layers: if provided, only these layer names are baked
    - exclude_layers: if provided, these layer names are skipped
    """
    tmx = pytmx.load_pygame(tmx_path)
    map_w_px = tmx.width * tmx.tilewidth
    map_h_px = tmx.height * tmx.tileheight

    surf = pygame.Surface((map_w_px, map_h_px)).convert()
    surf.fill((0, 0, 0))

    for layer in tmx.visible_layers:
        # Only bake tile layers
        if not isinstance(layer, pytmx.TiledTileLayer):
            continue

        lname = layer.name

        if include_layers is not None and lname not in include_layers:
            continue
        if exclude_layers is not None and lname in exclude_layers:
            continue

        for x, y, gid in layer:
            if gid == 0:
                continue
            tile = tmx.get_tile_image_by_gid(gid)
            if tile is None:
                continue

            px = x * tmx.tilewidth
            py = y * tmx.tileheight
            surf.blit(tile, (px, py))

    return surf
