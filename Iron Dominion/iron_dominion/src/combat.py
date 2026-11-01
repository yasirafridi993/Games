"""Pure functions for combat: damage math and target search."""

import math
import random

from . import config as C
from .unit_defs import UNIT_DEFS, counter_multiplier, WORKER

_FACTIONS = None


def set_faction_manager(fm):
    global _FACTIONS
    _FACTIONS = fm

def _owner_of(entity):
    return getattr(entity, "owner", None)


def is_hostile(a, b):
    oa = _owner_of(a)
    ob = _owner_of(b)
    if oa is None or ob is None:
        return False
    if _FACTIONS is not None:
        return _FACTIONS.are_hostile(oa, ob)
    return oa != ob


def _entity_position(e):
    """Returns (x, y, radius) for a Unit or (x, y, footprint_r) for a Building."""
    from .units import Unit
    if isinstance(e, Unit):
        return e.x, e.y, e.radius
    # Building: use an approximate radius from its footprint
    fp = max(getattr(e, "fp_w", 1), getattr(e, "fp_h", 1))
    return e.x, e.y, fp * C.TILE_HALF_W * 0.55


def in_attack_range(attacker, target):
    tx, ty, tr = _entity_position(target)
    dx = tx - attacker.x
    dy = ty - attacker.y
    dist = math.hypot(dx, dy)
    return dist <= attacker.attack_range + tr


def compute_damage(attacker_kind, target_kind, base_damage, target_armor):
    counter = counter_multiplier(attacker_kind, target_kind)
    raw = base_damage * counter
    reduced = max(1.0, raw - target_armor)
    variance = 1.0 + random.uniform(-C.COMBAT_DAMAGE_VARIANCE,
                                    C.COMBAT_DAMAGE_VARIANCE)
    return max(1, int(round(reduced * variance)))


def find_nearest_enemy_unit(attacker, units, max_dist):
    best = None
    best_d2 = max_dist * max_dist
    for u in units:
        if u is attacker:
            continue
        if u.dead:
            continue
        if not is_hostile(attacker, u):
            continue
        dx = u.x - attacker.x
        dy = u.y - attacker.y
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_d2 = d2
            best = u
    return best


def find_nearest_enemy_building(attacker, buildings, max_dist):
    best = None
    best_d2 = max_dist * max_dist
    for b in buildings:
        if not b.alive:
            continue
        if not is_hostile(attacker, b):
            continue
        dx = b.x - attacker.x
        dy = b.y - attacker.y
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_d2 = d2
            best = b
    return best


def find_best_target(attacker, units, buildings, max_dist):
    """Prefer nearest enemy unit; fall back to buildings."""
    u = find_nearest_enemy_unit(attacker, units, max_dist)
    if u is not None:
        return u
    return find_nearest_enemy_building(attacker, buildings, max_dist)