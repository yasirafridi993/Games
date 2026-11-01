"""Grid-based A* pathfinding on the isometric tile map.

The grid is a plain 2D boolean array. Obstacles come from two sources:
  * terrain (deep water, mountains)
  * buildings (any footprint tile)

Both are cheap to test in the A* inner loop. Paths are computed on tiles
and then smoothed with a "string pulling" line-of-sight pass before being
converted into world-space waypoints.

Diagonal movement is allowed only when both orthogonal neighbours are free
(no corner cutting). Elevation changes are permitted between adjacent
walkable tiles but cost extra, which makes units prefer flat routes.
"""

import heapq
import math

from . import config as C
from . import iso
from .terrain import DEEP_WATER, MOUNTAIN

# sqrt(2)
_SQRT2 = 1.41421356237


# ---------------------------------------------------------------------------
# Obstacle grid
# ---------------------------------------------------------------------------
class PathGrid:
    """Fast lookup: ``is_blocked(col, row)`` -> bool."""

    __slots__ = ("cols", "rows", "terrain_blocked", "building_blocked",
                 "world")

    def __init__(self, world):
        self.world = world
        self.cols = world.cols
        self.rows = world.rows
        self.terrain_blocked = [[False] * self.rows for _ in range(self.cols)]
        self.building_blocked = [[False] * self.rows for _ in range(self.cols)]
        self.rebuild_terrain()

    # ------------------------------------------------------------------
    def rebuild_terrain(self):
        terrain = self.world.terrain
        for row in range(self.rows):
            row_blocked = self.terrain_blocked  # for reference clarity
            for col in range(self.cols):
                t = terrain.tiles[row][col][0]
                self.terrain_blocked[col][row] = (t == DEEP_WATER or t == MOUNTAIN)

    def rebuild_buildings(self, buildings):
        for col in range(self.cols):
            col_row = self.building_blocked[col]
            for row in range(self.rows):
                col_row[row] = False

        for b in buildings:
            if not b.alive:
                continue
            for (c, r) in b.tiles():
                if 0 <= c < self.cols and 0 <= r < self.rows:
                    self.building_blocked[c][r] = True

    # ------------------------------------------------------------------
    def is_blocked(self, col, row):
        if col < 0 or col >= self.cols or row < 0 or row >= self.rows:
            return True
        return self.terrain_blocked[col][row] or self.building_blocked[col][row]

    def is_terrain_blocked(self, col, row):
        if col < 0 or col >= self.cols or row < 0 or row >= self.rows:
            return True
        return self.terrain_blocked[col][row]


# ---------------------------------------------------------------------------
# Line-of-sight (Bresenham)
# ---------------------------------------------------------------------------
def line_of_sight(grid, a, b):
    """True if no blocked tile lies between tile ``a`` and tile ``b`` inclusive."""
    x0, y0 = a
    x1, y1 = b
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    # Allow diagonal corners: only block if the direct tile is blocked.
    while True:
        if grid.is_blocked(x0, y0):
            return False
        if x0 == x1 and y0 == y1:
            return True
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


def smooth_path(grid, path):
    """Greedy string-pulling: drop waypoints that are directly visible."""
    if path is None:
        return None
    n = len(path)
    if n <= 2:
        return path

    out = [path[0]]
    i = 0
    while i < n - 1:
        j = n - 1
        while j > i + 1 and not line_of_sight(grid, path[i], path[j]):
            j -= 1
        out.append(path[j])
        i = j
    return out


# ---------------------------------------------------------------------------
# A* search
# ---------------------------------------------------------------------------
class Pathfinder:
    # (dx, dy, base_cost)
    _ORTHO = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0))
    _DIAG = ((1, 1, _SQRT2), (1, -1, _SQRT2),
             (-1, 1, _SQRT2), (-1, -1, _SQRT2))

    def __init__(self, world, building_manager):
        self.world = world
        self.buildings = building_manager
        self.grid = PathGrid(world)
        self.refresh()
        # Metrics (for the debug HUD)
        self.searches = 0
        self.nodes_expanded = 0

    # ------------------------------------------------------------------
    def refresh(self):
        self.grid.rebuild_buildings(self.buildings.buildings)

    # ------------------------------------------------------------------
    def find_path(self, start_col, start_row, goal_col, goal_row,
                  max_nodes=None):
        if max_nodes is None:
            max_nodes = C.PATH_MAX_NODES

        start = self._coerce_walkable(start_col, start_row)
        goal = self._coerce_walkable(goal_col, goal_row)
        if start is None or goal is None:
            return None
        if start == goal:
            return [start]

        self.searches += 1

        elev = self.world.terrain.elevation

        open_heap = [(self._h(start, goal), 0.0, start)]
        came_from = {}
        g_score = {start: 0.0}
        closed = set()
        expanded = 0

        push = heapq.heappush
        pop = heapq.heappop

        while open_heap:
            _f, g, current = pop(open_heap)
            if current in closed:
                continue
            closed.add(current)
            expanded += 1
            if expanded > max_nodes:
                self.nodes_expanded += expanded
                return None
            if current == goal:
                self.nodes_expanded += expanded
                return self._reconstruct(came_from, current)

            cx, cy = current
            cur_e = elev[cy][cx]

            # Orthogonal neighbours
            for dx, dy, base in self._ORTHO:
                nx, ny = cx + dx, cy + dy
                if self.grid.is_blocked(nx, ny):
                    continue
                ne = elev[ny][nx]
                step = base + abs(ne - cur_e) * C.PATH_ELEVATION_COST
                self._relax((nx, ny), g + step, current, goal,
                            g_score, came_from, closed, open_heap)

            # Diagonal neighbours (no corner cutting)
            for dx, dy, base in self._DIAG:
                nx, ny = cx + dx, cy + dy
                if self.grid.is_blocked(nx, ny):
                    continue
                if (self.grid.is_blocked(cx + dx, cy)
                        or self.grid.is_blocked(cx, cy + dy)):
                    continue
                ne = elev[ny][nx]
                step = base + abs(ne - cur_e) * C.PATH_ELEVATION_COST
                self._relax((nx, ny), g + step, current, goal,
                            g_score, came_from, closed, open_heap)

        self.nodes_expanded += expanded
        return None

    # ------------------------------------------------------------------
    def _relax(self, node, tentative_g, parent, goal,
               g_score, came_from, closed, open_heap):
        if node in closed:
            return
        prev = g_score.get(node)
        if prev is not None and tentative_g >= prev:
            return
        g_score[node] = tentative_g
        came_from[node] = parent
        f = tentative_g + self._h(node, goal)
        heapq.heappush(open_heap, (f, tentative_g, node))

    # ------------------------------------------------------------------
    @staticmethod
    def _h(a, b):
        """Octile heuristic."""
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        return (dx + dy) + (_SQRT2 - 2.0) * min(dx, dy)

    # ------------------------------------------------------------------
    @staticmethod
    def _reconstruct(came_from, current):
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    # ------------------------------------------------------------------
    def _coerce_walkable(self, col, row):
        if not self.grid.is_blocked(col, row):
            return (col, row)
        return self._nearest_walkable(col, row, max_radius=6)

    def _nearest_walkable(self, col, row, max_radius=6):
        for r in range(0, max_radius + 1):
            for dc in range(-r, r + 1):
                for dr in range(-r, r + 1):
                    if max(abs(dc), abs(dr)) != r:
                        continue
                    c, rr = col + dc, row + dr
                    if not self.grid.is_blocked(c, rr):
                        return (c, rr)
        return None


# ---------------------------------------------------------------------------
# Tile-path -> world-waypoint conversion
# ---------------------------------------------------------------------------
def path_to_waypoints(tile_path, final_world_xy=None):
    """Convert an A* tile path into world-space waypoints.

    The start tile is skipped (the unit is already there). The final waypoint
    is replaced by ``final_world_xy`` if provided, so the unit lands exactly
    where the player clicked rather than on a tile centre.
    """
    if not tile_path or len(tile_path) < 2:
        if final_world_xy is not None:
            return [tuple(final_world_xy)]
        return []

    waypoints = []
    for (c, r) in tile_path[1:]:
        waypoints.append(iso.tile_to_world(c, r))

    if final_world_xy is not None:
        waypoints[-1] = (float(final_world_xy[0]), float(final_world_xy[1]))
    return waypoints