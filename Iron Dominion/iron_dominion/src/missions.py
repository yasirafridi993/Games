"""Mission framework: objectives, mission classes, and the library.

A Mission is responsible for:
  * the map seed it uses
  * spawning the initial world contents (player + enemy)
  * providing the list of Objectives that define victory
  * optional per-frame logic and world-space overlays

Objectives are updated every frame by the Game while the match is in
progress. The Game ends when every objective is complete (victory) or when
the player has no remaining buildings or units (defeat).
"""

import pygame

from . import config as C
from . import iso
from .resources import FOOD, WOOD


# ---------------------------------------------------------------------------
# Objective base + concrete types
# ---------------------------------------------------------------------------
class Objective:
    text = "Objective"

    def __init__(self):
        self.complete = False

    # -- lifecycle ------------------------------------------------------
    def update(self, game, dt):
        pass

    # -- display --------------------------------------------------------
    def marker(self):
        return "[x]" if self.complete else "[ ]"

    def progress_text(self, game):
        return ""

    # -- optional world rendering --------------------------------------
    def draw_world(self, surface, game):
        pass


# ---------------------------------------------------------------------------
class EliminateFaction(Objective):
    def __init__(self, owner=C.FACTION_ENEMY):
        super().__init__()
        self.owner = owner
        self.text = "Eliminate all enemy forces"

    def update(self, game, dt):
        if self.complete:
            return
        b_alive = any(b.alive and b.owner == self.owner
                      for b in game.buildings.buildings)
        u_alive = any(not u.dead and u.owner == self.owner
                      for u in game.units.units)
        if not b_alive and not u_alive:
            self.complete = True


class DestroyTownCenter(Objective):
    def __init__(self, owner=C.FACTION_ENEMY):
        super().__init__()
        self.owner = owner
        self.text = "Destroy the enemy Town Center"

    def update(self, game, dt):
        if self.complete:
            return
        if not any(b.alive and b.owner == self.owner
                   and b.kind == "town_center"
                   for b in game.buildings.buildings):
            self.complete = True


class KillUnits(Objective):
    def __init__(self, target, owner=C.FACTION_ENEMY):
        super().__init__()
        self.target = int(target)
        self.owner = owner
        self.text = f"Kill {self.target} enemy units"

    def update(self, game, dt):
        if self.complete:
            return
        if game.units.deaths_by_faction.get(self.owner, 0) >= self.target:
            self.complete = True

    def progress_text(self, game):
        have = game.units.deaths_by_faction.get(self.owner, 0)
        return f"{min(have, self.target)} / {self.target}"


class GatherResource(Objective):
    def __init__(self, resource, amount):
        super().__init__()
        self.resource = resource
        self.amount = int(amount)
        self.text = f"Gather {self.amount} {resource}"

    def update(self, game, dt):
        if self.complete:
            return
        if game.stockpile.get(self.resource) >= self.amount:
            self.complete = True

    def progress_text(self, game):
        cur = game.stockpile.get(self.resource)
        return f"{min(cur, self.amount)} / {self.amount}"


class Survive(Objective):
    def __init__(self, duration):
        super().__init__()
        self.duration = float(duration)
        self.elapsed = 0.0
        self.text = f"Survive for {int(self.duration)} seconds"

    def update(self, game, dt):
        if self.complete:
            return
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.complete = True

    def progress_text(self, game):
        return f"{int(self.elapsed)}s / {int(self.duration)}s"


class ControlArea(Objective):
    def __init__(self, col, row, radius_tiles, duration):
        super().__init__()
        self.col = int(col)
        self.row = int(row)
        self.radius_tiles = radius_tiles
        self.radius_world = radius_tiles * C.TILE_HALF_W
        self.duration = float(duration)
        self.held = 0.0
        self.text = f"Control the strategic point for {int(self.duration)}s"

    def _player_in_area(self, game):
        wx, wy = iso.tile_to_world(self.col, self.row)
        r2 = self.radius_world * self.radius_world
        for u in game.units.units:
            if u.dead or u.owner != C.FACTION_PLAYER:
                continue
            dx = u.x - wx
            dy = u.y - wy
            if dx * dx + dy * dy <= r2:
                return True
        return False

    def update(self, game, dt):
        if self.complete:
            return
        if self._player_in_area(game):
            self.held += dt
            if self.held >= self.duration:
                self.complete = True

    def progress_text(self, game):
        return f"{int(self.held)}s / {int(self.duration)}s"

    def draw_world(self, surface, game):
        wx, wy = iso.tile_to_world(self.col, self.row)
        cam = game.camera
        sx, sy = cam.world_to_screen(wx, wy)
        r = int(self.radius_world * cam.zoom)
        if r < 6:
            return
        rect = pygame.Rect(sx - r, sy - r * 0.5, r * 2, r)
        color = C.OBJECTIVE_DONE_COL if self.complete else C.OBJECTIVE_PENDING_COL
        pygame.draw.ellipse(surface, color, rect, max(2, int(2 * cam.zoom)))
        # Marker dot at the centre
        pygame.draw.circle(surface, color, (int(sx), int(sy)), 3)


# ---------------------------------------------------------------------------
# Mission base class
# ---------------------------------------------------------------------------
class Mission:
    key = "?"
    name = "?"
    description = ""
    seed = 20240517
    map_cols = C.MAP_COLS
    map_rows = C.MAP_ROWS

    # Whether the game should spawn an enemy base at all
    has_enemy_base = True
    # Whether the AI controller should run
    disable_ai = False
    # Difficulty used by the AI controller (see ai.AI_DIFFICULTY)
    enemy_difficulty = "medium"
    # (col, row) offset from the player start to place the enemy camp
    enemy_offset = (14, 4)

    def setup(self, game):
        """Override: spawn any initial world content."""
        pass

    def build_objectives(self, game):
        """Override: return the list of Objectives for this mission."""
        return []

    def tick(self, game, dt):
        """Override: mission-specific per-frame logic."""
        pass

    def draw_world_overlay(self, surface, game):
        for obj in game.objectives:
            obj.draw_world(surface, game)


# ---------------------------------------------------------------------------
# Concrete missions
# ---------------------------------------------------------------------------
class SkirmishMission(Mission):
    key = "skirmish"
    name = "Skirmish"
    description = "Eliminate the enemy base."
    seed = 20240517

    def setup(self, game):
        game.spawn_player_town_center()
        game.spawn_player_starting_units()
        game.spawn_enemy_camp()

    def build_objectives(self, game):
        return [EliminateFaction(C.FACTION_ENEMY)]


class RaidMission(Mission):
    key = "raid"
    name = "Raid"
    description = "Destroy the enemy Town Center."
    seed = 9001001
    enemy_difficulty = "easy"
    enemy_offset = (12, 2)

    def setup(self, game):
        game.spawn_player_town_center()
        game.spawn_player_starting_units()
        game.spawn_enemy_camp(include_army=False)

    def build_objectives(self, game):
        return [DestroyTownCenter(C.FACTION_ENEMY)]


class BlitzMission(Mission):
    key = "blitz"
    name = "Blitz"
    description = "Kill 25 enemy units."
    seed = 3333003
    enemy_difficulty = "hard"

    def setup(self, game):
        game.spawn_player_town_center()
        game.spawn_player_starting_units()
        game.spawn_enemy_camp()

    def build_objectives(self, game):
        return [KillUnits(25, C.FACTION_ENEMY)]

class HarvestMission(Mission):
    key = "harvest"
    name = "Harvest"
    description = "Gather 400 wood and 300 food."
    seed = 5555005
    has_enemy_base = False
    disable_ai = True

    def setup(self, game):
        # Extra starting workers would exceed the TC pop cap; give the
        # player a free House so training is not locked out on turn 1.
        game.spawn_player_town_center(starting_houses=1)
        game.spawn_player_starting_units(extra_workers=4)

    def build_objectives(self, game):
        return [
            GatherResource(WOOD, 400),
            GatherResource(FOOD, 300),
        ]


class SurviveMission(Mission):
    key = "survive"
    name = "Survive"
    description = "Hold out for 180 seconds."
    seed = 7777007
    enemy_difficulty = "medium"

    def setup(self, game):
        # Extra soldiers also exceed the TC pop cap; give the player a
        # free House so Worker production is available immediately.
        game.spawn_player_town_center(starting_houses=1)
        game.spawn_player_starting_units(extra_soldiers=2)
        game.spawn_enemy_camp()

    def build_objectives(self, game):
        return [Survive(180.0)]

class HoldMission(Mission):
    key = "hold"
    name = "Hold the Line"
    description = "Control the strategic point for 60 seconds."
    seed = 8888008
    enemy_difficulty = "medium"

    def setup(self, game):
        game.spawn_player_town_center()
        game.spawn_player_starting_units()
        game.spawn_enemy_camp()

    def build_objectives(self, game):
        pcol, prow = game.find_spawn_center()
        ecol = pcol + self.enemy_offset[0]
        erow = prow + self.enemy_offset[1]
        mid_col = (pcol + ecol) // 2
        mid_row = (prow + erow) // 2
        grid = game.pathfinder.grid
        if grid.is_blocked(mid_col, mid_row):
            snapped = game.pathfinder._nearest_walkable(mid_col, mid_row, 8)
            if snapped is not None:
                mid_col, mid_row = snapped
        return [ControlArea(mid_col, mid_row, 4, 60.0)]


# ---------------------------------------------------------------------------
# Library + canonical order
# ---------------------------------------------------------------------------
MISSION_LIBRARY = {
    "skirmish": SkirmishMission,
    "raid": RaidMission,
    "blitz": BlitzMission,
    "harvest": HarvestMission,
    "survive": SurviveMission,
    "hold": HoldMission,
}

MISSION_ORDER = ("skirmish", "raid", "blitz",
                 "harvest", "survive", "hold")