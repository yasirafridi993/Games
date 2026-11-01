"""The game world: terrain, elevation and props.

Visual overhaul: composition is driven by multiple noise layers so
forests, rocky regions and detail props form natural, irregular shapes.
"""

import math
import random
from .props import (
    Prop,
    TREE_ROUND, TREE_PINE, ROCK, BERRY_BUSH,
    STONE_DEPOSIT, IRON_DEPOSIT,
    FLOWER_PATCH, GRASS_TUFT, FALLEN_LOG, STUMP, SMALL_ROCK,
    BOULDER, STONE_PILE, GRAVEL,
)
from . import config as C
from .terrain import (
    TerrainMap, _fractal_noise,
    GRASS, TALL_GRASS, DIRT, STONE, MOUNTAIN, SAND,
    WATER_TILES,
)
from .props import (
    GRAVEL,
    Prop,
    TREE_ROUND, TREE_PINE, ROCK, BERRY_BUSH,
    STONE_DEPOSIT, IRON_DEPOSIT,
    FLOWER_PATCH, GRASS_TUFT, FALLEN_LOG, STUMP, SMALL_ROCK, BOULDER, STONE_PILE, GRAVEL
)


class World:
    def __init__(self, cols, rows, seed):
        self.cols = cols
        self.rows = rows
        self.seed = seed

        self.terrain = TerrainMap(cols, rows, seed)
        self.props = []
        self.props_by_diag = {}

        self._place_props()
        self._group_props()

        hw = C.TILE_HALF_W
        hh = C.TILE_HALF_H
        self.min_x = -rows * hw
        self.max_x = cols * hw
        self.min_y = -hh - C.ELEVATION_PIXELS * 2
        self.max_y = (cols + rows - 1) * hh

    # ------------------------------------------------------------------
    def _place_props(self):
        rng = random.Random(self.seed ^ 0xBEEF)

        # Multiple density fields
        forest = _fractal_noise(self.cols, self.rows, self.seed + 5)
        rock_field = _fractal_noise(self.cols, self.rows, self.seed + 6)
        flower_field = _fractal_noise(self.cols, self.rows, self.seed + 7)
        grass_field = _fractal_noise(self.cols, self.rows, self.seed + 8)

        # Detail props are more common — put them on a coarser grid to
        # avoid overloading the diagonal buckets
        for row in range(self.rows):
            for col in range(self.cols):
                t, _ = self.terrain.get(col, row)
                el = self.terrain.get_elevation(col, row)
                f = forest[row][col]
                rf = rock_field[row][col]
                fl = flower_field[row][col]
                gf = grass_field[row][col]

                # -------------------- trees ---------------------------
                if t in (GRASS, TALL_GRASS):
                    if f > 0.68:
                        # Dense forest core
                        if rng.random() < 0.78:
                            self._add_tree(col, row, rng, dense=True)
                            continue
                    elif f > 0.56:
                        # Forest edge — sparser, mixed with bushes
                        r = rng.random()
                        if r < 0.34:
                            self._add_tree(col, row, rng, dense=False)
                            continue
                        if r < 0.52:
                            self._add_prop(BERRY_BUSH, col, row, rng)
                            continue
                    elif f > 0.44:
                        if rng.random() < 0.06:
                            self._add_tree(col, row, rng, dense=False)
                            continue
                    else:
                        # Isolated trees on open grass (rare)
                        if rng.random() < 0.012:
                            self._add_tree(col, row, rng, dense=False)
                            continue

                # -------------------- bushes --------------------------
                if t in (GRASS, TALL_GRASS) and 0.40 < f <= 0.62:
                    if rng.random() < 0.10:
                        self._add_prop(BERRY_BUSH, col, row, rng)
                        continue

                # -------------------- forest floor litter -------------
                if t in (GRASS, TALL_GRASS) and f > 0.55:
                    r = rng.random()
                    if r < 0.05:
                        self._add_prop(FALLEN_LOG, col, row, rng)
                        continue
                    if r < 0.09:
                        self._add_prop(STUMP, col, row, rng)
                        continue
                    if r < 0.13:
                        self._add_prop(SMALL_ROCK, col, row, rng)
                        continue
                    if r < 0.20:
                        self._add_prop(GRASS_TUFT, col, row, rng)
                        continue

                # -------------------- scattered rocks -----------------
                                # -------------------- rocky clutter --------------------
                if t in (GRASS, TALL_GRASS, DIRT, STONE, MOUNTAIN):
                    if rf > 0.66:
                        # Dense rocky outcrop
                        r = rng.random()
                        if r < 0.06:
                            self._add_prop(BOULDER, col, row, rng)
                            continue
                        if r < 0.16:
                            self._add_prop(ROCK, col, row, rng)
                            continue
                        if r < 0.22:
                            self._add_prop(STONE_PILE, col, row, rng)
                            continue
                        if r < 0.28:
                            self._add_prop(GRAVEL, col, row, rng)
                            continue
                    elif rf > 0.55:
                        # Sparser rocky region
                        r = rng.random()
                        if r < 0.03:
                            self._add_prop(ROCK, col, row, rng)
                            continue
                        if r < 0.05:
                            self._add_prop(SMALL_ROCK, col, row, rng)
                            continue
                    # Ambient pebbles anywhere on land
                    if rng.random() < 0.020:
                        self._add_prop(SMALL_ROCK, col, row, rng)
                        continue
                    if rng.random() < 0.008:
                        self._add_prop(GRAVEL, col, row, rng)
                        continue

                # -------------------- deposits ------------------------
                                # -------------------- deposits ------------------------
                if t in (STONE, DIRT, MOUNTAIN) and el <= 1:
                    if self._near_type(col, row, MOUNTAIN, radius=3):
                        if rng.random() < 0.32:
                            self._add_prop(STONE_DEPOSIT, col, row, rng)
                            continue
                if t in (STONE, DIRT, MOUNTAIN) and el == 0:
                    if self._near_type(col, row, MOUNTAIN, radius=5):
                        if rng.random() < 0.16:
                            self._add_prop(IRON_DEPOSIT, col, row, rng)
                            continue

                # Also scatter stone/iron anywhere on land, at low density
                if t in (GRASS, TALL_GRASS, DIRT, STONE) and el == 0:
                    r = rng.random()
                    if r < 0.010:
                        self._add_prop(STONE_DEPOSIT, col, row, rng)
                        continue
                    if r < 0.020:
                        self._add_prop(IRON_DEPOSIT, col, row, rng)
                        continue

                # -------------------- environmental details -----------
                if t in (GRASS, TALL_GRASS, DIRT, SAND):
                    # Flower patches
                    if fl > 0.62 and rng.random() < 0.10:
                        self._add_prop(FLOWER_PATCH, col, row, rng)
                        continue
                    # Grass tufts
                    if gf > 0.45 and rng.random() < 0.05:
                        self._add_prop(GRASS_TUFT, col, row, rng)
                        continue

    # ------------------------------------------------------------------
    def _add_tree(self, col, row, rng, dense):
        # More pines in dense forest, more round trees at edges
        if dense:
            kind = TREE_PINE if rng.random() < 0.55 else TREE_ROUND
        else:
            kind = TREE_ROUND if rng.random() < 0.68 else TREE_PINE
        self._add_prop(kind, col, row, rng)

    def _add_prop(self, kind, col, row, rng):
        from .props import STONE_DEPOSIT, IRON_DEPOSIT
        # Resource deposits stick to the tile centre so they're easy to click
        if kind in (STONE_DEPOSIT, IRON_DEPOSIT):
            ox = rng.uniform(-4, 4)
            oy = rng.uniform(-4, 4)
        else:
            hw = C.TILE_HALF_W * 0.60
            hh = C.TILE_HALF_H * 0.60
            ox = rng.uniform(-hw, hw)
            oy = rng.uniform(-hh, hh)
        variant = rng.randrange(6)
        self.props.append(Prop(kind, col, row, ox, oy, variant))

    def _near_type(self, col, row, target_type, radius):
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                nc, nr = col + dc, row + dr
                if 0 <= nc < self.cols and 0 <= nr < self.rows:
                    if self.terrain.get(nc, nr)[0] == target_type:
                        return True
        return False

    def _group_props(self):
        """Bucket props by their TILE diagonal (col + row).

        Do not use the world-Y diagonal here: a prop whose oy is negative
        would land in the diagonal *behind* its own tile, get drawn before
        the tile, and be covered by it — which makes it look like it is
        sunk into the ground.
        """
        self.props_by_diag.clear()
        for p in self.props:
            d = p.col + p.row
            self.props_by_diag.setdefault(d, []).append(p)
        for d in self.props_by_diag:
            self.props_by_diag[d].sort(key=lambda p: p.oy)
    # ------------------------------------------------------------------
    def bounds(self):
        return (self.min_x, self.max_x, self.min_y, self.max_y)

    def center(self):
        return ((self.min_x + self.max_x) * 0.5,
                (self.min_y + self.max_y) * 0.5)

    def in_bounds(self, col, row):
        return 0 <= col < self.cols and 0 <= row < self.rows

    def elevation(self, col, row):
        return self.terrain.get_elevation(col, row)

    # ------------------------------------------------------------------
    def pick_prop(self, wx, wy, radius=None):
        if radius is None:
            radius = C.PROP_PICK_RADIUS
        r2 = radius * radius
        best = None
        best_wy = -float("inf")
        for p in self.props:
            if not p.has_resources():
                continue
            px, py = p.world_position()
            dx, dy = wx - px, wy - py
            if dx * dx + dy * dy <= r2 and py > best_wy:
                best_wy = py
                best = p
        return best

    def pick_nearest_resource(self, resource_type, wx, wy,
                              max_dist=420.0, exclude=None):
        """Return the nearest living resource node of the given type
        within ``max_dist`` world units. ``exclude`` skips a specific
        node (usually the one we just depleted).
        """
        r2 = max_dist * max_dist
        best = None
        best_d2 = r2
        for p in self.props:
            if p is exclude:
                continue
            if not p.has_resources():
                continue
            if p.resource_type != resource_type:
                continue
            px, py = p.world_position()
            dx = px - wx
            dy = py - wy
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                best = p
        return best

    # ------------------------------------------------------------------
    def clear_props_in_rect(self, col, row, w, h):
        removed = []
        for p in list(self.props):
            if col <= p.col < col + w and row <= p.row < row + h:
                removed.append(p)
        for p in removed:
            try:
                self.props.remove(p)
            except ValueError:
                pass
            d = p.col + p.row
            lst = self.props_by_diag.get(d)
            if lst is not None:
                try:
                    lst.remove(p)
                except ValueError:
                    pass