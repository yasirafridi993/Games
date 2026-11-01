"""Production queue system for training units at buildings."""

import math
import random

from . import config as C
from . import iso
from .unit_defs import UNIT_DEFS


class ProductionItem:
    __slots__ = ("unit_kind", "time_total", "time_left")

    def __init__(self, unit_kind):
        self.unit_kind = unit_kind
        self.time_total = UNIT_DEFS[unit_kind]["train_time"]
        self.time_left = self.time_total


class ProductionQueue:
    __slots__ = ("building", "items", "max_size")

    def __init__(self, building, max_size=None):
        self.building = building
        self.items = []
        self.max_size = max_size if max_size is not None else C.TRAINING_QUEUE_MAX

    # ------------------------------------------------------------------
    def can_enqueue(self):
        return len(self.items) < self.max_size

    def enqueue(self, unit_kind):
        if not self.can_enqueue():
            return False
        self.items.append(ProductionItem(unit_kind))
        return True

    def cancel_last(self):
        if not self.items:
            return None
        return self.items.pop()

    def cancel_index(self, idx):
        if 0 <= idx < len(self.items):
            return self.items.pop(idx)
        return None

    # ------------------------------------------------------------------
    def update(self, dt, unit_manager, stockpile=None):
        """Advance the first item and spawn a unit when it finishes."""
        if not self.items:
            return
        item = self.items[0]
        item.time_left -= dt
        if item.time_left > 0:
            return

        # Spawn the unit at a free position beside the building, owned by
        # whoever owns the building. Without this every AI-trained unit
        # would inherit owner=0 (the player) and inflate the player's
        # population counter.
        wx, wy = self._spawn_position()
        unit_manager.spawn(item.unit_kind, wx, wy,
                           owner=self.building.owner)
        self.items.pop(0)
    # ------------------------------------------------------------------
    def _spawn_position(self):
        b = self.building
        world = self.building_world()
        terrain = world.terrain if world is not None else None

        # Prefer a spot in front of the building, spread around a small ring.
        angles = [math.pi * 0.25, math.pi * 0.5, math.pi * 0.75,
                  math.pi, math.pi * 1.25, math.pi * 1.5,
                  math.pi * 1.75, 0.0]
        rng = random.Random()
        rng.shuffle(angles)
        base_radius = max(b.fp_w, b.fp_h) * 26.0 + 12.0

        for mult in (1.0, 1.35, 1.75):
            for a in angles:
                r = base_radius * mult
                wx = b.x + math.cos(a) * r
                wy = b.y + math.sin(a) * r * 0.65

                if world is None:
                    return wx, wy
                col, row = iso.world_to_tile(wx, wy)
                if not world.in_bounds(col, row):
                    continue
                t = terrain.tiles[row][col][0]
                from .terrain import WATER_TILES, MOUNTAIN
                if t in WATER_TILES or t == MOUNTAIN:
                    continue
                if terrain.get_elevation(col, row) != 0:
                    continue
                return wx, wy

        # Fallback: just beside the building
        return b.x + base_radius, b.y + base_radius * 0.5

    # ------------------------------------------------------------------
    def building_world(self):
        # Set by BuildingManager when the queue is attached.
        return getattr(self.building, "_world", None)

    def current_progress(self):
        if not self.items:
            return 0.0
        item = self.items[0]
        if item.time_total <= 0:
            return 1.0
        return max(0.0, min(1.0, 1.0 - item.time_left / item.time_total))