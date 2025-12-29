# engine/overworld/regions/validate.py
from __future__ import annotations

from typing import List

def _validate_profile_id(issues: list[str], field_name: str, ref) -> str | None:
    pid = getattr(ref, "profile_id", None)
    if not isinstance(pid, str) or not pid.strip():
        issues.append(f"{field_name}.profile_id missing/invalid (got {pid!r})")
        return None
    return pid

def validate_region_spec(spec) -> List[str]:
    """
    Validate a declarative RegionSpec for authoring sanity.

    Returns a list of human-readable warnings.
    - No asset loads
    - No pygame surfaces
    - No runtime mutation
    - Registry lookups are allowed (they are pure reads), but performed via local imports
      to avoid import cycles.
    """
    issues: List[str] = []

    # ---- Identity ----------------------------------------------------
    region_id = getattr(spec, "id", None)
    if not region_id or not isinstance(region_id, str):
        issues.append("id missing/invalid")
    elif any(c.isspace() for c in region_id):
        issues.append(f"id contains whitespace: {region_id!r}")

    name = getattr(spec, "name", None)
    if not name or not isinstance(name, str):
        issues.append("name missing/invalid")

    # ---- Presenter + map source -------------------------------------
    presenter_type = getattr(spec, "presenter_type", None)
    if presenter_type not in ("mode7", "overhead"):
        issues.append(f"presenter_type must be 'mode7' or 'overhead' (got {presenter_type!r})")

    tmx_path = getattr(spec, "tmx_path", None)
    if not tmx_path or not isinstance(tmx_path, str):
        issues.append("tmx_path missing/invalid")
    else:
        if not tmx_path.lower().endswith(".tmx"):
            issues.append(f"tmx_path does not end with .tmx: {tmx_path!r}")

    # ---- Registry refs (celestial / weather / encounters) -----------
    # These are "should resolve" checks. If they fail, you'll crash later anyway.
    # We keep them as warnings for now (you can promote to errors later).

    # ---- Celestial profile --------------------------------------------
    try:
        from engine.overworld.celestial.registry import get_celestial_profile
    except Exception:  # pragma: no cover
        get_celestial_profile = None

    celestial_ref = getattr(spec, "celestial", None)
    if celestial_ref is not None:
        pid = _validate_profile_id(issues, "celestial", celestial_ref)
        if pid and get_celestial_profile is not None:
            try:
                if get_celestial_profile(pid) is None:
                    issues.append(f"celestial profile_id not found: {pid!r}")
            except Exception as e:
                issues.append(f"celestial profile_id lookup failed for {pid!r}: {e}")

    # ---- Weather profile ----------------------------------------------
    try:
        from engine.overworld.weather.registry import get_weather_profile
    except Exception:  # pragma: no cover
        get_weather_profile = None

    weather_ref = getattr(spec, "weather", None)
    if weather_ref is not None:
        pid = _validate_profile_id(issues, "weather", weather_ref)
        if pid:
            try:
                from engine.overworld.weather.registry import get_weather_profile
            except Exception:
                issues.append("weather registry unavailable (import failed)")
            else:
                try:
                    if get_weather_profile(pid) is None:
                        issues.append(f"weather profile_id not found: {pid!r}")
                except Exception as e:
                    issues.append(f"weather profile_id lookup failed for {pid!r}: {e}")
    # ---- Enemy Packs profile ------------------------------
    enemy_packs = getattr(spec, "enemy_packs", None) or ()
    try:
        from engine.actors.enemy_packs.registry import known_enemy_packs
    except Exception:
        known_enemy_packs = None

    if known_enemy_packs is not None:
        known = set(known_enemy_packs())
        for i, pid in enumerate(enemy_packs):
            if pid not in known:
                issues.append(f"enemy_packs[{i}] unknown pack id: {pid!r} (known: {sorted(known)})")

    # ---- Encounter profile (placeholder validation) -------------------
    encounters_ref = getattr(spec, "encounters", None)
    if encounters_ref is not None:
        _validate_profile_id(issues, "encounters", encounters_ref)

    # ---- Aerial actor spec (light sanity) ----------------------------
    aerial = getattr(spec, "aerial_actor", None)
    if aerial is not None:
        # We don't know full shape here; just ensure it isn't something obviously wrong.
        # (AerialActorSpec is data; builder will do deeper checks.)
        if not hasattr(aerial, "__dict__") and not isinstance(aerial, dict):
            issues.append(f"aerial_actor looks invalid type: {type(aerial).__name__}")

    # ---- Silhouettes -------------------------------------------------
    silhouettes = getattr(spec, "silhouettes", None) or ()
    for i, sb in enumerate(silhouettes):
        prefix = f"silhouettes[{i}]"

        image_path = getattr(sb, "image_path", None)
        if not image_path or not isinstance(image_path, str):
            issues.append(f"{prefix}: image_path missing/invalid")
        else:
            if not image_path.lower().endswith((".png", ".webp", ".jpg", ".jpeg")):
                issues.append(f"{prefix}: image_path does not look like an image file: {image_path!r}")

        tier = getattr(sb, "tier", None)
        if not isinstance(tier, int):
            issues.append(f"{prefix}: tier should be int (got {type(tier).__name__})")
        elif tier < 0:
            issues.append(f"{prefix}: tier < 0 (got {tier})")

        th = getattr(sb, "target_height_px", None)
        if not isinstance(th, int) or th <= 0:
            issues.append(f"{prefix}: target_height_px should be int > 0 (got {th!r})")

        twm = getattr(sb, "tile_width_mul", None)
        if not isinstance(twm, (int, float)) or float(twm) <= 0:
            issues.append(f"{prefix}: tile_width_mul should be > 0 (got {twm!r})")

        preserve = getattr(sb, "preserve_aspect", None)
        if not isinstance(preserve, bool):
            issues.append(f"{prefix}: preserve_aspect should be bool (got {preserve!r})")

        fi = getattr(sb, "fade_inner_rad", None)
        fo = getattr(sb, "fade_outer_rad", None)
        if not isinstance(fi, (int, float)) or not isinstance(fo, (int, float)):
            issues.append(f"{prefix}: fade_inner_rad/fade_outer_rad must be numbers (got {fi!r}/{fo!r})")
        else:
            fi = float(fi)
            fo = float(fo)
            if fi < 0 or fo < 0:
                issues.append(f"{prefix}: fade angles should be >= 0 (got inner={fi}, outer={fo})")
            if fo <= fi:
                issues.append(f"{prefix}: fade_outer_rad must be > fade_inner_rad (got inner={fi}, outer={fo})")

        amax = getattr(sb, "alpha_max", None)
        amin = getattr(sb, "alpha_min", None)
        if not isinstance(amax, int) or not (0 <= amax <= 255):
            issues.append(f"{prefix}: alpha_max must be int in [0..255] (got {amax!r})")
        if not isinstance(amin, int) or not (0 <= amin <= 255):
            issues.append(f"{prefix}: alpha_min must be int in [0..255] (got {amin!r})")
        if isinstance(amax, int) and isinstance(amin, int) and amin > amax:
            issues.append(f"{prefix}: alpha_min > alpha_max (got {amin} > {amax})")

        overlap = getattr(sb, "horizon_overlap", None)
        if not isinstance(overlap, int) or overlap < 0:
            issues.append(f"{prefix}: horizon_overlap should be int >= 0 (got {overlap!r})")

        yaw = getattr(sb, "yaw_factor", None)
        if not isinstance(yaw, (int, float)):
            issues.append(f"{prefix}: yaw_factor should be a number (got {yaw!r})")

        # facing angle is numeric (no range enforcement; radians wrap naturally)
        fa = getattr(sb, "facing_angle_rad", None)
        if not isinstance(fa, (int, float)):
            issues.append(f"{prefix}: facing_angle_rad should be a number (got {fa!r})")

    # ---- Exits ---------------------------------------------------------
    exits = getattr(spec, "exits", None) or ()
    seen_ids: set[str] = set()

    for i, ex in enumerate(exits):
        prefix = f"exits[{i}]"

        ex_id = getattr(ex, "id", None)
        if not isinstance(ex_id, str) or not ex_id.strip():
            issues.append(f"{prefix}: id missing/invalid (got {ex_id!r})")
            continue

        if ex_id in seen_ids:
            issues.append(f"{prefix}: duplicate exit id {ex_id!r}")
        seen_ids.add(ex_id)

        to_region_id = getattr(ex, "to_region_id", None)
        if not isinstance(to_region_id, str) or not to_region_id.strip():
            issues.append(f"{prefix}: to_region_id missing/invalid (got {to_region_id!r})")
        else:
            # Optional resolution check (safe, local import to avoid cycles)
            try:
                from engine.overworld.regions.registry import get_region
            except Exception:
                issues.append(f"{prefix}: cannot import region registry to validate to_region_id {to_region_id!r}")
            else:
                try:
                    if get_region(to_region_id) is None:
                        issues.append(f"{prefix}: to_region_id not found in registry: {to_region_id!r}")
                except Exception as e:
                    issues.append(f"{prefix}: to_region_id lookup failed for {to_region_id!r}: {e}")

        # Optional spawn label (we won't enforce semantics yet)
        to_spawn = getattr(ex, "to_spawn", None)
        if to_spawn is not None and (not isinstance(to_spawn, str) or not to_spawn.strip()):
            issues.append(f"{prefix}: to_spawn must be a non-empty string if provided (got {to_spawn!r})")

        # Optional flag gating (validate reference format only)
        requires_flag = getattr(ex, "requires_flag", None)
        if requires_flag is not None:
            if not isinstance(requires_flag, str) or not requires_flag.strip():
                issues.append(f"{prefix}: requires_flag must be a non-empty string if provided (got {requires_flag!r})")
            elif " " in requires_flag:
                issues.append(f"{prefix}: requires_flag contains spaces (got {requires_flag!r})")

