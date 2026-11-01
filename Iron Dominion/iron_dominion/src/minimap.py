"""Corner minimap.

Renders a downsampled top-down view of the world (one pixel per tile)
showing terrain, fog of war, units, buildings and the current camera view.
Clicking or dragging inside the minimap recenters the camera.
"""

import pygame

from . import config as C
from . import iso
from .terrain import TILE_COLORS


class Minimap:
    def __init__(self, game):
        self.game = game
        self.size = C.MINIMAP_SIZE
        self.rect = pygame.Rect(0, 0, 0, 0)

        # Base terrain surface (cols x rows) built once
        self._base = None
        # Cached fog surface; rebuilt when the fog generation changes
        self._fog_surf = None
        self._last_fog_token = None
        self._build_base()

    # ------------------------------------------------------------------
    def _build_base(self):
        world = self.game.world
        surf = pygame.Surface((world.cols, world.rows))
        for r in range(world.rows):
            for c in range(world.cols):
                t = world.terrain.tiles[r][c][0]
                surf.set_at((c, r), TILE_COLORS[t][0])
        self._base = surf

    # ------------------------------------------------------------------
    def layout(self, surface):
        sw, sh = surface.get_size()
        margin = C.MINIMAP_MARGIN
        size = self.size
        self.rect = pygame.Rect(
            sw - size - margin,
            sh - size - margin,
            size,
            size,
        )

    # ------------------------------------------------------------------
    def hit_test(self, pos):
        return self.rect.collidepoint(pos)

    def screen_to_world(self, pos):
        """Return the world-space centre of the tile under minimap cursor."""
        world = self.game.world
        local_x = (pos[0] - self.rect.x) / self.rect.width
        local_y = (pos[1] - self.rect.y) / self.rect.height
        col = local_x * world.cols
        row = local_y * world.rows
        return iso.tile_to_world(col, row)

    # ------------------------------------------------------------------
    def draw(self, surface):
        self.layout(surface)
        rect = self.rect
        world = self.game.world
        fog = self.game.fog
        faction = C.FACTION_PLAYER

        # Outer border
        pygame.draw.rect(surface, C.MINIMAP_BG, rect.inflate(4, 4))
        pygame.draw.rect(surface, C.MINIMAP_BORDER,
                         rect.inflate(4, 4), C.MINIMAP_BORDER)
        pygame.draw.rect(surface, C.MINIMAP_BORDER_INNER, rect, 1)

        # Scaled terrain
        scaled = pygame.transform.scale(
            self._base, (rect.width, rect.height))
        surface.blit(scaled, rect.topleft)

        # Fog overlay
        fog_token = self._fog_token(faction)
        if self._fog_surf is None or self._last_fog_token != fog_token:
            self._fog_surf = self._build_fog_surface(faction)
            self._last_fog_token = fog_token
        scaled_fog = pygame.transform.scale(
            self._fog_surf, (rect.width, rect.height))
        surface.blit(scaled_fog, rect.topleft)

        # Buildings
        bm = self.game.buildings
        for b in bm.buildings:
            if not b.alive:
                continue
            if b.owner != faction and not fog.is_explored(faction, b.col, b.row):
                continue
            if b.owner != faction and not fog.is_visible(faction, b.col, b.row):
                # Explored but not currently visible: show a faint marker
                color = C.MINIMAP_ENEMY_BUILDING
                draw_r = C.MINIMAP_BUILDING_DOT_RADIUS
                # Only draw faint if we have ever seen it
                px = rect.x + int(b.col / world.cols * rect.width)
                py = rect.y + int(b.row / world.rows * rect.height)
                dot = pygame.Surface((draw_r * 2 + 2, draw_r * 2 + 2),
                                     pygame.SRCALPHA)
                pygame.draw.circle(dot, (*color, 90),
                                   (draw_r + 1, draw_r + 1), draw_r)
                surface.blit(dot, (px - draw_r - 1, py - draw_r - 1))
                continue
            color = (C.MINIMAP_PLAYER_BUILDING if b.owner == faction
                     else C.MINIMAP_ENEMY_BUILDING)
            px = rect.x + int((b.col + b.fp_w * 0.5) / world.cols * rect.width)
            py = rect.y + int((b.row + b.fp_h * 0.5) / world.rows * rect.height)
            pygame.draw.rect(
                surface, color,
                (px - C.MINIMAP_BUILDING_DOT_RADIUS - 1,
                 py - C.MINIMAP_BUILDING_DOT_RADIUS - 1,
                 C.MINIMAP_BUILDING_DOT_RADIUS * 2 + 2,
                 C.MINIMAP_BUILDING_DOT_RADIUS * 2 + 2))

        # Units
        um = self.game.units
        dot_r = C.MINIMAP_UNIT_DOT_RADIUS
        for u in um.units:
            if u.dead:
                continue
            col, row = u.tile_position()
            c = int(col)
            r = int(row)
            if u.owner != faction and not fog.is_visible(faction, c, r):
                continue
            color = (C.MINIMAP_PLAYER_DOT if u.owner == faction
                     else C.MINIMAP_ENEMY_DOT)
            px = rect.x + int(col / world.cols * rect.width)
            py = rect.y + int(row / world.rows * rect.height)
            pygame.draw.rect(
                surface, color,
                (px - dot_r, py - dot_r, dot_r * 2 + 1, dot_r * 2 + 1))

        # Camera view rectangle (projected as a quad)
        self._draw_camera_rect(surface, rect)

    # ------------------------------------------------------------------
    def _draw_camera_rect(self, surface, rect):
        cam = self.game.camera
        world = self.game.world
        vw = cam.view_w * 0.5 / cam.zoom
        vh = cam.view_h * 0.5 / cam.zoom
        cx, cy = cam.x, cam.y

        corners = [
            (cx - vw, cy - vh),
            (cx + vw, cy - vh),
            (cx + vw, cy + vh),
            (cx - vw, cy + vh),
        ]
        hw = C.TILE_HALF_W
        hh = C.TILE_HALF_H
        pts = []
        for (wx, wy) in corners:
            col = (wx / hw + wy / hh) * 0.5
            row = (wy / hh - wx / hw) * 0.5
            px = rect.x + col / world.cols * rect.width
            py = rect.y + row / world.rows * rect.height
            pts.append((px, py))

        pygame.draw.polygon(surface, C.MINIMAP_CAMERA_COLOR, pts, 1)

    # ------------------------------------------------------------------
    def _fog_token(self, faction):
        """Cheap fingerprint of the fog state used as a cache key.

        Fog is recomputed at ~15 Hz; ``len(visible_set)`` plus
        ``explored_count`` gives us a token that changes whenever fog
        actually updates, without hashing the whole grid.
        """
        fog = self.game.fog
        vis = fog._visible.get(faction)
        n_vis = len(vis) if vis else 0
        n_exp = fog.explored_count(faction)
        return (n_vis, n_exp)

    def _build_fog_surface(self, faction):
        world = self.game.world
        fog = self.game.fog
        surf = pygame.Surface((world.cols, world.rows), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))

        unexplored_col = (*C.MINIMAP_UNEXPLORED, 255)
        explored_col = C.MINIMAP_EXPLORED_TINT

        for r in range(world.rows):
            for c in range(world.cols):
                if fog.is_visible(faction, c, r):
                    continue
                if fog.is_explored(faction, c, r):
                    surf.set_at((c, r), explored_col)
                else:
                    surf.set_at((c, r), unexplored_col)
        return surf