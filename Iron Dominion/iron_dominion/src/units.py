"""Unit entity system. Definitions live in :mod:`unit_defs`."""

import math

from . import config as C
from .unit_defs import (
    UNIT_DEFS, WORKER, SWORDSMAN, SPEARMAN, ARCHER, CAVALRY,
    MILITARY_KINDS,
)

__all__ = [
    "Unit", "UnitState", "WorkerTask", "BuildTask",
    "UNIT_DEFS", "WORKER", "SWORDSMAN", "SPEARMAN", "ARCHER", "CAVALRY",
    "MILITARY_KINDS",
    "facing_from_world_velocity",
    "DIR_NE", "DIR_SE", "DIR_SW", "DIR_NW",
]

DIR_NE, DIR_SE, DIR_SW, DIR_NW = 0, 1, 2, 3


def facing_from_world_velocity(vx, vy):
    if vx == 0.0 and vy == 0.0:
        return DIR_SE
    svx = vx - vy
    svy = vx + vy
    if svx >= 0 and svy < 0:
        return DIR_NE
    if svx >= 0 and svy >= 0:
        return DIR_SE
    if svx < 0 and svy >= 0:
        return DIR_SW
    return DIR_NW


class UnitState:
    IDLE = "idle"
    MOVING = "moving"
    WORKING = "working"
    ATTACKING = "attacking"


class WorkerTask:
    __slots__ = ("node", "dropoff", "node_wx", "node_wy",
                 "drop_wx", "drop_wy", "mode", "timer")
    MODE_TO_NODE = "to_node"
    MODE_GATHERING = "gathering"
    MODE_TO_DROPOFF = "to_dropoff"
    MODE_DEPOSIT = "deposit"

    def __init__(self, node, node_wx, node_wy, dropoff, drop_wx, drop_wy):
        self.node = node
        self.dropoff = dropoff
        self.node_wx = node_wx
        self.node_wy = node_wy
        self.drop_wx = drop_wx
        self.drop_wy = drop_wy
        self.mode = self.MODE_TO_NODE
        self.timer = 0.0


class BuildTask:
    __slots__ = ("building", "stand_x", "stand_y")

    def __init__(self, building, stand_x, stand_y):
        self.building = building
        self.stand_x = stand_x
        self.stand_y = stand_y


class Unit:
    __slots__ = (
        "kind", "x", "y", "hp", "max_hp", "speed", "radius",
        "damage", "armor", "attack_range", "attack_cooldown", "aggro_range",
        "state", "facing", "path",
        "anim_state", "anim_timer", "anim_phase",
        "selected",
        "task", "carrying", "carrying_type", "gather_buffer",
        "owner", "attack_target", "attack_timer",
        "attack_repath_timer", "hit_flash", "dead",
        # Phase 10
        "base_damage", "base_armor", "base_speed", "base_max_hp",
        "carry_capacity", "gather_rate_mult",
    )

    def __init__(self, kind, x, y, owner=0):
        defn = UNIT_DEFS[kind]
        self.kind = kind
        self.x = float(x)
        self.y = float(y)
        self.max_hp = defn["max_hp"]
        self.hp = self.max_hp
        self.speed = defn["speed"]
        self.radius = defn["radius"]
        self.damage = defn["damage"]
        self.armor = defn["armor"]
        self.attack_range = defn["attack_range"]
        self.attack_cooldown = defn["attack_cooldown"]
        self.aggro_range = defn.get("aggro_range", 0.0)

        self.state = UnitState.IDLE
        self.facing = DIR_SE
        self.path = []

        self.anim_state = "idle"
        self.anim_timer = 0.0
        self.anim_phase = 0

        self.selected = False

        self.task = None
        self.carrying = 0
        self.carrying_type = None
        self.gather_buffer = 0.0

        self.owner = owner
        self.attack_target = None
        self.attack_timer = 0.0
        self.attack_repath_timer = 0.0
        self.hit_flash = 0.0
        self.dead = False

        # ---- Phase 10 base stats -------------------------------------
        self.base_damage = self.damage
        self.base_armor = self.armor
        self.base_speed = self.speed
        self.base_max_hp = self.max_hp
        self.carry_capacity = C.WORKER_CARRY_CAPACITY
        self.gather_rate_mult = 1.0

    # ------------------------------------------------------------------
    def apply_tech(self, tech_state):
        b = tech_state.bonuses
        self.damage = self.base_damage + b.get("attack", 0)
        self.armor = self.base_armor + b.get("armor", 0)
        self.speed = self.base_speed * b.get("speed_mult", 1.0)
        self.carry_capacity = C.WORKER_CARRY_CAPACITY + b.get("carry_bonus", 0)
        self.gather_rate_mult = b.get("gather_rate_mult", 1.0)

    # ------------------------------------------------------------------
    def set_path(self, waypoints):
        self.path = list(waypoints)
        if self.path:
            # A new path always switches the unit into MOVING, EXCEPT
            # when it is currently ATTACKING (so we don't clobber the
            # attack state that _update_combat manages). WORKING is
            # no longer protected — without this, a worker finishing
            # a gather cycle receives a path home but stays in the
            # WORKING state, never follows the path, and never
            # deposits its resources.
            if self.state != UnitState.ATTACKING:
                self.state = UnitState.MOVING
        elif self.state == UnitState.MOVING:
            self.state = UnitState.IDLE
            self.anim_state = "idle"
            self.anim_timer = 0.0
            self.anim_phase = 0

    def set_idle(self):
        self.state = UnitState.IDLE
        self.path = []
        self.attack_target = None
        self.anim_state = "idle"
        self.anim_timer = 0.0
        self.anim_phase = 0

    def set_working(self):
        self.state = UnitState.WORKING
        self.path = []
        self.attack_target = None
        self.anim_state = "work"
        self.anim_timer = 0.0
        self.anim_phase = 0

    def set_attacking(self, target):
        self.state = UnitState.ATTACKING
        self.attack_target = target
        self.attack_timer = 0.0
        self.attack_repath_timer = 0.0
        self.anim_state = "attack"
        self.anim_timer = 0.0
        self.anim_phase = 0

    def cancel_task(self):
        self.task = None

    def begin_gather_task(self, node, node_wx, node_wy,
                          dropoff, drop_wx, drop_wy):
        self.task = WorkerTask(node, node_wx, node_wy,
                               dropoff, drop_wx, drop_wy)
        self.carrying_type = node.resource_type
        self.gather_buffer = 0.0
        self.attack_target = None
        self.set_path([(node_wx, node_wy)])
        self.state = UnitState.MOVING

    def begin_build_task(self, building, stand_x, stand_y):
        self.task = BuildTask(building, stand_x, stand_y)
        self.attack_target = None
        self.set_path([(stand_x, stand_y)])
        self.state = UnitState.MOVING

    # ------------------------------------------------------------------
    def tile_position(self):
        hw, hh = C.TILE_HALF_W, C.TILE_HALF_H
        col = (self.x / hw + self.y / hh) * 0.5
        row = (self.y / hh - self.x / hw) * 0.5
        return col, row

    def diagonal(self):
        # Round to the *visual* tile the sprite's base falls on, not the
        # spatial tile. A unit whose feet straddle a tile boundary is
        # drawn after the front tile, so the front tile can no longer
        # occlude the sprite's bottom.
        col, row = self.tile_position()
        c = int(math.floor(col + 0.5))
        r = int(math.floor(row + 0.5))
        return c + r

    # ------------------------------------------------------------------
    def take_damage(self, amount):
        if self.dead:
            return False
        self.hp -= amount
        self.hit_flash = C.COMBAT_HIT_FLASH_TIME
        if self.hp <= 0:
            self.hp = 0
            self.dead = True
            return True
        return False

    # ------------------------------------------------------------------
    def update(self, dt):
        if self.hit_flash > 0:
            self.hit_flash -= dt

        if self.path and self.state != UnitState.WORKING:
            self._follow_path(dt)

        if self.state == UnitState.WORKING:
            self.anim_state = "work"
            self.anim_timer += dt
            self.anim_phase = int(
                self.anim_timer / (C.UNIT_WORK_CYCLE_TIME / 4.0)) % 4
        elif self.state == UnitState.ATTACKING:
            self.anim_state = "attack"
            self.anim_timer += dt
            self.anim_phase = int(
                self.anim_timer / (C.UNIT_ATTACK_CYCLE_TIME / 4.0)) % 4
        elif self.state == UnitState.MOVING and self.path:
            self.anim_state = "walk"
            self.anim_timer += dt
            self.anim_phase = int(
                self.anim_timer / (C.UNIT_WALK_CYCLE_TIME / 4.0)) % 4
        else:
            self.anim_state = "idle"
            self.anim_timer += dt
            self.anim_phase = int(
                self.anim_timer / (C.UNIT_IDLE_CYCLE_TIME / 2.0)) % 2

    # ------------------------------------------------------------------
    def _follow_path(self, dt):
        remaining = self.speed * dt
        moved = False

        while remaining > 1e-6 and self.path:
            tx, ty = self.path[0]
            dx = tx - self.x
            dy = ty - self.y
            dist = math.hypot(dx, dy)

            if dist <= C.UNIT_ARRIVAL_EPSILON:
                self.x = tx
                self.y = ty
                self.path.pop(0)
                continue

            if dist <= remaining:
                self.x = tx
                self.y = ty
                self.path.pop(0)
                remaining -= dist
                moved = True
            else:
                nx = dx / dist
                ny = dy / dist
                self.x += nx * remaining
                self.y += ny * remaining
                self.facing = facing_from_world_velocity(nx, ny)
                remaining = 0.0
                moved = True

        if not self.path and self.state == UnitState.MOVING:
            self.state = UnitState.IDLE
            self.anim_state = "idle"
            self.anim_timer = 0.0
            self.anim_phase = 0