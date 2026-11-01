"""Per-faction fog of war with a cached overlay surface for fast drawing."""

from . import config as C
from . import iso
from .unit_defs import (
    WORKER, SWORDSMAN, SPEARMAN, ARCHER, CAVALRY,
)

_UNIT_RADIUS = {
    WORKER: C.FOG_VISION_WORKER,
    SWORDSMAN: C.FOG_VISION_DEFAULT,
    SPEARMAN: C.FOG_VISION_DEFAULT,
    ARCHER: C.FOG_VISION_ARCHER,
    CAVALRY: C.FOG_VISION_CAVALRY,
}


class FogOfWar:
    def __init__(self, world):
        self.world = world
        self.cols = world.cols
        self.rows = world.rows

        self._centers = [
            [iso.tile_to_world(c, r) for c in range(self.cols)]
            for r in range(self.rows)
        ]

        self._explored = {}
        self._visible = {}

    # ------------------------------------------------------------------
    def register_faction(self, faction):
        if faction in self._explored:
            return
        self._explored[faction] = [
            [False] * self.cols for _ in range(self.rows)
        ]
        self._visible[faction] = set()

    # ------------------------------------------------------------------
    def update(self, faction, unit_manager, building_manager):
        self.register_faction(faction)

        visible = set()
        exp = self._explored[faction]

        for u in unit_manager.units:
            if u.dead or u.owner != faction:
                continue
            tiles = _UNIT_RADIUS.get(u.kind, C.FOG_VISION_DEFAULT)
            radius_px = tiles * C.TILE_HALF_W
            self._reveal_into(visible, exp, u.x, u.y, radius_px)

        for b in building_manager.buildings:
            if not b.alive or b.owner != faction:
                continue
            base = C.FOG_VISION_BUILDING
            if b.kind == "town_center":
                base = C.FOG_VISION_TOWN_CENTER
            footprint = max(b.fp_w, b.fp_h)
            radius_px = (base + footprint * 0.5) * C.TILE_HALF_W
            self._reveal_into(visible, exp, b.x, b.y, radius_px)

        self._visible[faction] = visible

    # ------------------------------------------------------------------
    def _reveal_into(self, visible, exp, wx, wy, radius_px):
        r2 = radius_px * radius_px
        cf, rf = iso.world_to_tile_f(wx, wy)

        r_tiles = int(radius_px / min(C.TILE_HALF_W, C.TILE_HALF_H)) + 2
        c0 = max(0, int(cf) - r_tiles)
        c1 = min(self.cols - 1, int(cf) + r_tiles)
        r0 = max(0, int(rf) - r_tiles)
        r1 = min(self.rows - 1, int(rf) + r_tiles)

        add = visible.add
        for r in range(r0, r1 + 1):
            centers = self._centers[r]
            exp_row = exp[r]
            for c in range(c0, c1 + 1):
                tx, ty = centers[c]
                dx = tx - wx
                dy = ty - wy
                if dx * dx + dy * dy <= r2:
                    add((r, c))
                    exp_row[c] = True

    # ------------------------------------------------------------------
    def is_visible(self, faction, col, row):
        if col < 0 or col >= self.cols or row < 0 or row >= self.rows:
            return False
        return (row, col) in self._visible.get(faction, ())

    def is_explored(self, faction, col, row):
        if col < 0 or col >= self.cols or row < 0 or row >= self.rows:
            return False
        grid = self._explored.get(faction)
        if grid is None:
            return False
        return grid[row][col]

    def is_visible_world(self, faction, wx, wy):
        c, r = iso.world_to_tile(wx, wy)
        return self.is_visible(faction, c, r)

    def explored_count(self, faction):
        grid = self._explored.get(faction)
        if grid is None:
            return 0
        return sum(sum(1 for v in row if v) for row in grid)