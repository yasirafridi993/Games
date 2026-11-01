"""Footprint-aware buildings + manager."""

import math

from . import config as C
from . import iso
from .building_defs import (
    BUILDING_DEFS, TOWN_CENTER, produces, researches,
)
from .building_sprites import BuildingSpriteCache
from .production import ProductionQueue
from .tech import TechQueue


class Building:
    __slots__ = (
        "kind", "col", "row", "fp_w", "fp_h",
        "x", "y", "front_y",
        "hp", "max_hp", "alive", "selected",
        "complete", "progress", "build_time", "build_work",
        "sprite", "queue", "_world",
        "owner", "armor", "hit_flash",
        "research_queue",
        # Farm resource state
        "food_reserve", "food_max", "food_regen",
    )

    def __init__(self, kind, col, row, world=None, owner=C.FACTION_PLAYER):
        defn = BUILDING_DEFS[kind]
        self.kind = kind
        self.col = int(col)
        self.row = int(row)
        self.fp_w, self.fp_h = defn["footprint"]

        cc = self.col + (self.fp_w - 1) * 0.5
        rr = self.row + (self.fp_h - 1) * 0.5
        self.x, self.y = iso.tile_to_world(cc, rr)

        front_col = self.col + self.fp_w - 1
        front_row = self.row + self.fp_h - 1
        self.front_y = (front_col + front_row) * C.TILE_HALF_H

        self.max_hp = defn["max_hp"]
        self.hp = self.max_hp
        self.alive = True
        self.selected = False

        self.build_time = float(defn["build_time"])
        self.build_work = 0.0
        if self.build_time <= 0.0:
            self.complete = True
            self.progress = 1.0
        else:
            self.complete = False
            self.progress = 0.0

        self.sprite = BuildingSpriteCache.get(kind)

        self.queue = ProductionQueue(self) if produces(kind) else None
        self.research_queue = TechQueue(self) if researches(kind) else None

        self._world = world
        if self.queue is not None and world is not None:
            self.queue.building._world = world

        self.owner = owner
        self.armor = 3
        self.hit_flash = 0.0
        if kind == "farm":
            self.food_reserve = 500.0
            self.food_max = 500.0
            self.food_regen = 4.0    # food per second
        else:
            self.food_reserve = 0.0
            self.food_max = 0.0
            self.food_regen = 0.0

    # ------------------------------------------------------------------
    def is_dropoff(self):
        return BUILDING_DEFS[self.kind]["is_dropoff"]

    def can_produce(self):
        return self.queue is not None

    def can_research(self):
        return self.research_queue is not None

    def tiles(self):
        for dc in range(self.fp_w):
            for dr in range(self.fp_h):
                yield self.col + dc, self.row + dr

    def contains_tile(self, col, row):
        return (self.col <= col < self.col + self.fp_w
                and self.row <= row < self.row + self.fp_h)

    def contains_world_point(self, wx, wy):
        cf, rf = iso.world_to_tile_f(wx, wy)
        return self.contains_tile(int(math.floor(cf)), int(math.floor(rf)))

    def distance_sq_to(self, wx, wy):
        return (self.x - wx) ** 2 + (self.y - wy) ** 2

    # ------------------------------------------------------------------
    def add_build_work(self, seconds):
        if self.complete:
            return False
        self.build_work += seconds
        if self.build_time > 0:
            self.progress = min(1.0, self.build_work / self.build_time)
        if self.progress >= 1.0:
            self.progress = 1.0
            self.complete = True
            return True
        return False

    def take_damage(self, amount):
        if not self.alive:
            return False
        self.hp -= amount
        self.hit_flash = C.COMBAT_HIT_FLASH_TIME
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            return True
        return False
        # ------------------------------------------------------------------
    # Farm-as-resource interface (mimics Prop for gather code)
    # ------------------------------------------------------------------
    def is_resource(self):
        return self.kind == "farm"

    @property
    def resource_type(self):
        if self.kind == "farm":
            from .resources import FOOD
            return FOOD
        return None

    def has_resources(self):
        if self.kind != "farm" or not self.complete:
            return False
        return self.food_reserve >= 1.0

    def harvest(self, amount):
        if self.kind != "farm" or not self.complete:
            return 0
        taken = min(int(amount), int(self.food_reserve))
        if taken <= 0:
            return 0
        self.food_reserve -= taken
        return taken

    def world_position(self):
        return (self.x, self.y)

    def update_farm(self, dt):
        """Regenerate the food reserve on a completed Farm."""
        if self.kind != "farm" or not self.complete:
            return
        if self.food_reserve < self.food_max:
            self.food_reserve = min(
                self.food_max,
                self.food_reserve + self.food_regen * dt,
            )

class BuildingManager:
    def __init__(self, world):
        self.world = world
        self.buildings = []

    def add(self, building):
        building._world = self.world
        if building.queue is not None:
            building.queue.building._world = self.world
        self.buildings.append(building)
        return building

    # ------------------------------------------------------------------
    def find_nearest_dropoff(self, wx, wy, owner=C.FACTION_PLAYER):
        best = None
        best_d = float("inf")
        for b in self.buildings:
            if not (b.alive and b.complete and b.is_dropoff()):
                continue
            if b.owner != owner:
                continue
            d = b.distance_sq_to(wx, wy)
            if d < best_d:
                best_d = d
                best = b
        return best

    def is_area_valid(self, col, row, w, h):
        terrain = self.world.terrain
        from .terrain import WATER_TILES, MOUNTAIN
        for dc in range(w):
            for dr in range(h):
                c, r = col + dc, row + dr
                if not self.world.in_bounds(c, r):
                    return False
                t = terrain.tiles[r][c][0]
                if t in WATER_TILES or t == MOUNTAIN:
                    return False
                if terrain.get_elevation(c, r) != 0:
                    return False
                for b in self.buildings:
                    if b.alive and b.contains_tile(c, r):
                        return False
        return True

    def building_at_tile(self, col, row):
        for b in self.buildings:
            if b.alive and b.contains_tile(col, row):
                return b
        return None

    def building_at_screen(self, camera, sx, sy, owner_filter=None):
        best = None
        best_y = -float("inf")
        for b in self.buildings:
            if not b.alive:
                continue
            if owner_filter is not None and b.owner != owner_filter:
                continue
            cx, cy = self._sprite_anchor(camera, b)
            sw = b.sprite.get_width() * camera.zoom
            sh = b.sprite.get_height() * camera.zoom
            if (cx - sw * 0.5 <= sx <= cx + sw * 0.5
                    and cy - sh <= sy <= cy):
                if b.front_y > best_y:
                    best_y = b.front_y
                    best = b
        return best

    def enemy_building_at_screen(self, camera, sx, sy, attacker_owner):
        best = None
        best_y = -float("inf")
        for b in self.buildings:
            if not b.alive or b.owner == attacker_owner:
                continue
            cx, cy = self._sprite_anchor(camera, b)
            sw = b.sprite.get_width() * camera.zoom
            sh = b.sprite.get_height() * camera.zoom
            if (cx - sw * 0.5 <= sx <= cx + sw * 0.5
                    and cy - sh <= sy <= cy):
                if b.front_y > best_y:
                    best_y = b.front_y
                    best = b
        return best

    @staticmethod
    def _sprite_anchor(camera, b):
        world_y = b.front_y + C.TILE_HALF_H
        return camera.world_to_screen(b.x, world_y)

    # ------------------------------------------------------------------
    def total_pop_capacity(self, owner=C.FACTION_PLAYER):
        total = 0
        for b in self.buildings:
            if not b.alive or not b.complete:
                continue
            if b.owner != owner:
                continue
            total += BUILDING_DEFS[b.kind]["pop_bonus"]
        return total

    def update_production(self, dt, unit_manager, tech_states):
        for b in self.buildings:
            if not b.alive or not b.complete:
                continue
            if b.kind == "farm":
                b.update_farm(dt)
            if b.queue is not None and b.queue.items:
                b.queue.update(dt, unit_manager)
            if b.research_queue is not None and b.research_queue.items:
                ts = tech_states.get(b.owner)
                if ts is not None:
                    b.research_queue.update(dt, ts, unit_manager, self)


    def queued_unit_count(self, owner=C.FACTION_PLAYER):
        total = 0
        for b in self.buildings:
            if not b.alive or b.queue is None:
                continue
            if b.owner != owner:
                continue
            total += len(b.queue.items)
        return total

    def pop_cost_in_queue(self, owner=C.FACTION_PLAYER):
        from .unit_defs import UNIT_DEFS
        total = 0
        for b in self.buildings:
            if not b.alive or b.queue is None:
                continue
            if b.owner != owner:
                continue
            for item in b.queue.items:
                total += UNIT_DEFS[item.unit_kind]["pop_cost"]
        return total

    # ------------------------------------------------------------------
    def apply_tech_to_faction(self, tech_state, owner):
        """Currently a no-op; reserved for future building HP upgrades."""
        return

    def remove_dead(self, particles, selected_holder):
        alive = []
        destroyed = False
        new_sel = selected_holder
        for b in self.buildings:
            if b.alive:
                alive.append(b)
            else:
                destroyed = True
                particles.spawn_building_death(b.x, b.y)
                if new_sel is b:
                    new_sel = None
        self.buildings = alive
        return destroyed, new_sel