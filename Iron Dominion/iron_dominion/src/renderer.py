"""Isometric rendering: terrain, props, buildings, units, effects, fog."""

import math

import pygame
from .mountain_sprites import get_mountain
from . import config as C
from . import iso
from .terrain import MOUNTAIN, get_tile_surface
from .building_defs import BUILDING_DEFS
from .terrain import (
    TILE_COLORS, make_tile_surface, make_edge_overlay, shade,
    SHALLOW_WATER, DEEP_WATER,
)
from .unit_sprites import UnitSpriteCache
from .units import UnitState

DIR_NE, DIR_SE, DIR_SW, DIR_NW = 0, 1, 2, 3

_WATER_TYPES = (SHALLOW_WATER, DEEP_WATER)


class TerrainRenderer:
    _SCALED_CACHE_LIMIT = 4000
    _PROP_CACHE_LIMIT = 3000
    _UNIT_CACHE_LIMIT = 2500
    _BUILDING_CACHE_LIMIT = 128

    def __init__(self, world, camera):
        self.world = world
        self.camera = camera
        self._base_tiles = {}
        self._edge_overlays = {}
        self._base_scaled = {}
        self._edge_scaled = {}
        self._prop_scaled = {}
        self._unit_scaled = {}
        self._building_scaled = {}
        self._build_base_assets()
        self._mtn_scaled = {}

        # Cached full-screen overlay surface for fog (reused each frame)
        self._fog_overlay = None
        # Animated water time
        self.water_time = 0.0
        # A small pre-rendered water highlight sprite we can cheaply blit
        self._water_glint = self._build_water_glint()
        self._glint_zoom = None
        self._glint_scaled = None
        # WorldFx is injected by Game after construction
        self.world_fx = None

    # ------------------------------------------------------------------
    def update(self, dt):
        self.water_time += dt

    def _get_mountain(self, col, row, zoom):
        base = get_mountain(col, row)
        if abs(zoom - 1.0) < 1e-3:
            return base
        zk = round(zoom, 2)
        key = (col % 6, row % 6, zk)
        s = self._mtn_scaled.get(key)
        if s is None:
            s = pygame.transform.scale(
                base, (max(1, int(base.get_width() * zk)),
                       max(1, int(base.get_height() * zk))))
            if len(self._mtn_scaled) > 600:
                self._mtn_scaled.clear()
            self._mtn_scaled[key] = s
        return s

    # ------------------------------------------------------------------
    def _build_base_assets(self):
        # Tile surfaces are generated lazily on first use now; there is
        # no eager build step. Kept as a method for constructor symmetry.
        pass

    def _build_water_glint(self):
        """A soft horizontal light patch to blit over water tiles."""
        w, h = 44, 12
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for x in range(w):
            # Bell-ish alpha curve along the length
            t = x / (w - 1)
            amp = math.sin(t * math.pi)
            for y in range(h):
                yt = y / (h - 1)
                fade = 1.0 - abs(yt - 0.5) * 2.0
                a = int(70 * amp * fade)
                if a > 0:
                    surf.set_at((x, y), (220, 240, 255, a))
        return surf

    # ------------------------------------------------------------------
    def _get_tile(self, tile_type, col, row, zoom):
        # Base surface at 1x zoom — terrain handles the sampling and
        # caching internally by (type, tex_x, tex_y).
        if abs(zoom - 1.0) < 1e-3:
            return get_tile_surface(tile_type, col, row)
        # Scaled: key the cache on (type, col, row, zoom_rounded).
        # get_tile_surface has its own cache for the base surface, so
        # this cache only stores the scaled variant.
        zk = round(zoom, 2)
        key = (tile_type, col, row, zk)
        s = self._base_scaled.get(key)
        if s is None:
            base = get_tile_surface(tile_type, col, row)
            s = pygame.transform.smoothscale(
                base, (max(1, int(C.TILE_WIDTH * zk)),
                       max(1, int(C.TILE_HEIGHT * zk))))
            if len(self._base_scaled) > self._SCALED_CACHE_LIMIT:
                self._base_scaled.clear()
            self._base_scaled[key] = s
        return s

    def _get_edge(self, t, d, z, subvariant=0):
        k1 = (t, d, subvariant)
        if abs(z - 1.0) < 1e-3:
            s = self._edge_overlays.get(k1)
            if s is None:
                s = make_edge_overlay(t, d, subvariant)
                self._edge_overlays[k1] = s
            return s
        zk = round(z, 2)
        k = (t, d, subvariant, zk)
        s = self._edge_scaled.get(k)
        if s is None:
            base = self._edge_overlays.get(k1)
            if base is None:
                base = make_edge_overlay(t, d, subvariant)
                self._edge_overlays[k1] = base
            s = pygame.transform.smoothscale(
                base, (max(1, int(C.TILE_WIDTH * zk)),
                       max(1, int(C.TILE_HEIGHT * zk))))
            if len(self._edge_scaled) > self._SCALED_CACHE_LIMIT:
                self._edge_scaled.clear()
            self._edge_scaled[k] = s
        return s

    def _get_prop(self, prop, z):
        if abs(z - 1.0) < 1e-3:
            return prop.sprite
        zk = round(z, 2)
        k = (prop.kind, prop.variant, zk)
        s = self._prop_scaled.get(k)
        if s is None:
            b = prop.sprite
            s = pygame.transform.smoothscale(
                b, (max(1, int(b.get_width() * zk)),
                    max(1, int(b.get_height() * zk))))
            if len(self._prop_scaled) > self._PROP_CACHE_LIMIT:
                self._prop_scaled.clear()
            self._prop_scaled[k] = s
        return s

    def _get_unit(self, kind, facing, state, phase, z):
        if abs(z - 1.0) < 1e-3:
            return UnitSpriteCache.get(kind, facing, state, phase)
        zk = round(z, 2)
        k = (kind, facing, state, phase, zk)
        s = self._unit_scaled.get(k)
        if s is None:
            b = UnitSpriteCache.get(kind, facing, state, phase)
            s = pygame.transform.smoothscale(
                b, (max(1, int(b.get_width() * zk)),
                    max(1, int(b.get_height() * zk))))
            if len(self._unit_scaled) > self._UNIT_CACHE_LIMIT:
                self._unit_scaled.clear()
            self._unit_scaled[k] = s
        return s

    def _get_building(self, kind, sprite, z):
        if abs(z - 1.0) < 1e-3:
            return sprite
        zk = round(z, 2)
        k = (kind, zk)
        s = self._building_scaled.get(k)
        if s is None:
            s = pygame.transform.smoothscale(
                sprite,
                (max(1, int(sprite.get_width() * zk)),
                 max(1, int(sprite.get_height() * zk))))
            if len(self._building_scaled) > self._BUILDING_CACHE_LIMIT:
                self._building_scaled.clear()
            self._building_scaled[k] = s
        return s

    def _get_scaled_glint(self, zoom):
        zk = max(0.1, round(zoom * 10) / 10.0)
        if self._glint_zoom != zk:
            w = max(1, int(self._water_glint.get_width() * zk))
            h = max(1, int(self._water_glint.get_height() * zk))
            self._glint_scaled = pygame.transform.scale(
                self._water_glint, (w, h))
            self._glint_zoom = zk
        return self._glint_scaled

    # ------------------------------------------------------------------
    def visible_tile_range(self):
        cam = self.camera
        hw, hh = C.TILE_HALF_W, C.TILE_HALF_H
        vw, vh = cam.view_w, cam.view_h
        min_col = min_row = float("inf")
        max_col = max_row = float("-inf")
        for sx, sy in ((0, 0), (vw, 0), (0, vh), (vw, vh)):
            wx, wy = cam.screen_to_world(sx, sy)
            col = (wx / hw + wy / hh) * 0.5
            row = (wy / hh - wx / hw) * 0.5
            min_col = min(min_col, col)
            max_col = max(max_col, col)
            min_row = min(min_row, row)
            max_row = max(max_row, row)
        c0 = max(0, int(math.floor(min_col)) - 4)
        c1 = min(self.world.cols - 1, int(math.ceil(max_col)) + 4)
        r0 = max(0, int(math.floor(min_row)) - 4)
        r1 = min(self.world.rows - 1, int(math.ceil(max_row)) + 4)
        if c1 < c0 or r1 < r0:
            return None
        return c0, c1, r0, r1

    # ------------------------------------------------------------------
    def draw(self, surface, unit_manager=None, building_manager=None,
             fog=None, faction=C.FACTION_PLAYER):
        rng = self.visible_tile_range()
        if rng is None:
            return

        c0, c1, r0, r1 = rng
        world = self.world
        hh = C.TILE_HALF_H
        props_by_diag = world.props_by_diag
        units_by_diag = unit_manager.by_diagonal if unit_manager else {}

        buildings_by_diag = {}
        if building_manager is not None:
            for b in building_manager.buildings:
                if not b.alive:
                    continue
                if (fog is not None and b.owner != faction
                        and not fog.is_visible(faction, b.col, b.row)):
                    continue
                d = int(math.floor(b.front_y / hh))
                if (b.col + b.fp_w - 1 < c0 or b.col > c1
                        or b.row + b.fp_h - 1 < r0 or b.row > r1):
                    continue
                buildings_by_diag.setdefault(d, []).append(b)

        min_d = c0 + r0
        max_d = c1 + r1

        for d in range(min_d, max_d + 1):
            c_start = max(c0, d - r1)
            c_end = min(c1, d - r0)
            for col in range(c_start, c_end + 1):
                row = d - col
                self._draw_tile(surface, col, row)

            items = []
            props = props_by_diag.get(d)
            if props:
                for p in props:
                    if not p.alive:
                        continue
                    if c0 <= p.col <= c1 and r0 <= p.row <= r1:
                        wy = (p.col + p.row) * hh + p.oy
                        items.append((wy, 0, p))

            if buildings_by_diag:
                for b in buildings_by_diag.get(d, ()):
                    items.append((b.front_y, 1, b))

            if units_by_diag:
                for u in units_by_diag.get(d, ()):
                    if fog is not None and u.owner != faction:
                        col, row = u.tile_position()
                        if not fog.is_visible(faction,
                                              int(math.floor(col)),
                                              int(math.floor(row))):
                            continue
                    col, row = u.tile_position()
                    if (c0 - 1 <= col <= c1 + 1) and (r0 - 1 <= row <= r1 + 1):
                        items.append((u.y, 2, u))

            if items:
                items.sort(key=lambda it: it[0])
                for _, kind, obj in items:
                    if kind == 0:
                        self._draw_prop(surface, obj)
                    elif kind == 1:
                        self._draw_building(surface, obj)
                    else:
                        self._draw_unit(surface, obj)

    # ------------------------------------------------------------------
    def draw_fog_overlay(self, surface, fog, faction):
        rng = self.visible_tile_range()
        if rng is None:
            return
        c0, c1, r0, r1 = rng
        cam = self.camera
        zoom = cam.zoom
        hw, hh = C.TILE_HALF_W * zoom, C.TILE_HALF_H * zoom
        elev_px = C.ELEVATION_PIXELS
        elev = self.world.terrain.elevation

        # ---- Reuse a single overlay surface (allocated once) -------------
        if self._fog_overlay is None or \
                self._fog_overlay.get_size() != surface.get_size():
            self._fog_overlay = pygame.Surface(surface.get_size(),
                                               pygame.SRCALPHA)
        overlay = self._fog_overlay
        overlay.fill((0, 0, 0, 0))

        dim_col = (0, 0, 0, C.FOG_EXPLORED_ALPHA)
        unexplored_col = C.FOG_UNEXPLORED_COLOR

        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                if fog.is_visible(faction, col, row):
                    continue
                explored = fog.is_explored(faction, col, row)
                wx, wy = iso.tile_to_world(col, row)
                e = elev[row][col]
                sx, sy = cam.world_to_screen(wx, wy - e * elev_px)
                pts = iso.tile_diamond(sx, sy, hw, hh)
                if explored:
                    pygame.draw.polygon(overlay, dim_col, pts)
                else:
                    pygame.draw.polygon(overlay, unexplored_col, pts)

        surface.blit(overlay, (0, 0))

    # ------------------------------------------------------------------
    def _draw_tile(self, surface, col, row):
        cam = self.camera
        zoom = cam.zoom
        hw, hh = C.TILE_HALF_W, C.TILE_HALF_H
        elev_px = C.ELEVATION_PIXELS
        world = self.world
        terrain = world.terrain
        tiles = terrain.tiles
        elev = terrain.elevation

        t, v = tiles[row][col]
        e = elev[row][col]
        wx = (col - row) * hw
        wy = (col + row) * hh
        sx, sy = cam.world_to_screen(wx, wy - e * elev_px)

        # --- Extruded side walls for elevated tiles ---
        if e > 0:
            ne_r = elev[row][col + 1] if col + 1 < world.cols else 0
            if e > ne_r:
                self._draw_wall(surface, sx, sy, t, e - ne_r, "right")
            ne_l = elev[row + 1][col] if row + 1 < world.rows else 0
            if e > ne_l:
                self._draw_wall(surface, sx, sy, t, e - ne_l, "left")

        # --- Base tile surface, sampled from the world texture ---
                # --- Base tile or mountain sprite ---
        if t == MOUNTAIN and e >= 2:
            mtn = self._get_mountain(col, row, zoom)
            mtn_w = mtn.get_width()
            mtn_h = mtn.get_height()
            # Anchor: the sprite's (W/2, H-6) pixel lands on the tile's
            # bottom diamond vertex, i.e. at screen (sx, sy + TILE_HALF_H).
            anchor_y = mtn_h - 6 * zoom
            tx = int(sx - mtn_w * 0.5)
            ty = int(sy + C.TILE_HALF_H - anchor_y)
            surface.blit(mtn, (tx, ty))
        else:
            tile_surf = self._get_tile(t, col, row, zoom)
            tw, th = tile_surf.get_size()
            tx = int(sx - tw * 0.5)
            ty = int(sy - th * 0.5)
            surface.blit(tile_surf, (tx, ty))
        # --- Animated water shimmer ---
                # --- Animated water shimmer ---
        if t in _WATER_TYPES:
            g = self._get_scaled_glint(zoom)
            gw, gh = g.get_size()
            is_deep = (t == DEEP_WATER)
            n_glints = 1 if is_deep else 3
            for i in range(n_glints):
                phase = (col * 0.7 + row * 0.35
                         + self.water_time * 0.9 + i * 2.1)
                gx = int(sx + math.sin(phase) * hw * 0.45 - gw * 0.5)
                gy = int(sy - 4 * zoom + i * 3 * zoom
                         + math.cos(phase * 1.3) * 2 * zoom)
                surface.blit(g, (gx, gy))

        # --- Terrain transitions on the four edges ---
        if row > 0:
            nt, _ = tiles[row - 1][col]
            if nt != t and elev[row - 1][col] == e:
                sub = (col + row) % 3
                surface.blit(self._get_edge(nt, DIR_NE, zoom, sub), (tx, ty))
        if col + 1 < world.cols:
            nt, _ = tiles[row][col + 1]
            if nt != t and elev[row][col + 1] == e:
                sub = (col + row + 1) % 3
                surface.blit(self._get_edge(nt, DIR_SE, zoom, sub), (tx, ty))
        if row + 1 < world.rows:
            nt, _ = tiles[row + 1][col]
            if nt != t and elev[row + 1][col] == e:
                sub = (col + row + 2) % 3
                surface.blit(self._get_edge(nt, DIR_SW, zoom, sub), (tx, ty))
        if col > 0:
            nt, _ = tiles[row][col - 1]
            if nt != t and elev[row][col - 1] == e:
                sub = (col + row + 3) % 3
                surface.blit(self._get_edge(nt, DIR_NW, zoom, sub), (tx, ty))

        if t in _WATER_TYPES:
            self._draw_water_details(surface, sx, sy, col, row, zoom, t)
        if t == SHALLOW_WATER:
            self._draw_shoreline(surface, col, row, e, sx, sy, zoom)

    def _draw_wall(self, surface, sx, sy, tile_type, levels, side):
        cam = self.camera
        zoom = cam.zoom
        hw, hh = C.TILE_HALF_W * zoom, C.TILE_HALF_H * zoom
        wall_h = levels * C.ELEVATION_PIXELS * zoom
        base = TILE_COLORS[tile_type][1]
        if tile_type == MOUNTAIN:
            base = (108, 100, 92)
        factor = 0.60 if side == "right" else 0.46
        color = shade(base, factor)
        if side == "right":
            pts = [(sx, sy + hh), (sx + hw, sy),
                   (sx + hw, sy + wall_h), (sx, sy + hh + wall_h)]
        else:
            pts = [(sx - hw, sy), (sx, sy + hh),
                   (sx, sy + hh + wall_h), (sx - hw, sy + wall_h)]
        pygame.draw.polygon(surface, color, pts)
        # Layered strata and a narrow rim catch light on exposed ledges.
        for level in range(1, levels + 1):
            y = sy + level * C.ELEVATION_PIXELS * zoom
            if side == "right":
                start = (sx, y + hh)
                end = (sx + hw, y)
            else:
                start = (sx - hw, y)
                end = (sx, y + hh)
            pygame.draw.line(surface, shade(base, 0.72), start, end,
                             max(1, int(zoom)))
        rim = shade(base, 1.18 if side == "left" else 0.90)
        if side == "right":
            pygame.draw.line(surface, rim, (sx, sy + hh), (sx + hw, sy),
                             max(1, int(zoom)))
        else:
            pygame.draw.line(surface, rim, (sx - hw, sy), (sx, sy + hh),
                             max(1, int(zoom)))

    def _draw_water_details(self, surface, sx, sy, col, row, zoom, tile_type):
        """Add a couple of animated, tile-stable caustics over water."""
        phase = col * 0.73 + row * 1.17 + self.water_time * 1.25
        scale = max(0.55, min(zoom, 1.5))
        count = 1 if tile_type == DEEP_WATER else 2
        for i in range(count):
            pulse = 0.55 + 0.45 * math.sin(phase + i * 2.2)
            gx = sx + math.sin(phase * 0.8 + i * 2.5) * C.TILE_HALF_W * zoom * 0.48
            gy = sy + math.cos(phase * 0.65 + i * 1.7) * C.TILE_HALF_H * zoom * 0.35
            width = max(2, int((8 + pulse * 7) * scale))
            height = max(1, int(2 * scale))
            shine = (205, 232, 246) if tile_type == DEEP_WATER else (238, 250, 250)
            glint_color = shade(shine, 0.66 + pulse * 0.34)
            pygame.draw.ellipse(surface, glint_color,
                                (int(gx - width / 2), int(gy - height / 2),
                                 width, height))
            if pulse > 0.82:
                pygame.draw.circle(surface, (248, 255, 255),
                                   (int(gx), int(gy)), max(1, int(scale)))

    def _draw_shoreline(self, surface, col, row, elevation, sx, sy, zoom):
        terrain = self.world.terrain
        hw, hh = C.TILE_HALF_W * zoom, C.TILE_HALF_H * zoom
        corners = (
            ((sx, sy - hh), (sx + hw, sy), col, row - 1),
            ((sx + hw, sy), (sx, sy + hh), col + 1, row),
            ((sx, sy + hh), (sx - hw, sy), col, row + 1),
            ((sx - hw, sy), (sx, sy - hh), col - 1, row),
        )
        for edge_index, (start, end, nc, nr) in enumerate(corners):
            if not terrain.in_bounds(nc, nr):
                continue
            neighbor_type, _ = terrain.get(nc, nr)
            if neighbor_type in _WATER_TYPES or terrain.get_elevation(nc, nr) != elevation:
                continue
            phase = (col * 13 + row * 7 + edge_index * 5) % 11
            for segment in range(3):
                t0 = 0.12 + segment * 0.29 + phase * 0.002
                t1 = min(0.96, t0 + 0.12)
                p0 = (start[0] + (end[0] - start[0]) * t0,
                      start[1] + (end[1] - start[1]) * t0)
                p1 = (start[0] + (end[0] - start[0]) * t1,
                      start[1] + (end[1] - start[1]) * t1)
                pygame.draw.line(surface, (166, 218, 224), p0, p1,
                                 max(1, int(zoom)))

    # ------------------------------------------------------------------
    def _draw_ambient_shadow(self, surface, sx, sy, radius, zoom, alpha=80):
        rw = max(4, int(radius * 1.55 * zoom))
        rh = max(2, int(radius * 0.85 * zoom))
        sh = pygame.Surface((rw * 2, rh * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, alpha), sh.get_rect())
        surface.blit(sh, (int(sx - rw), int(sy - rh)))

    # ------------------------------------------------------------------
    def _draw_prop(self, surface, prop):
        if not prop.alive:
            return
        cam = self.camera
        zoom = cam.zoom
        hw, hh = C.TILE_HALF_W, C.TILE_HALF_H
        col, row = prop.col, prop.row
        e = self.world.terrain.elevation[row][col]
        wx = (col - row) * hw + prop.ox
        wy = (col + row) * hh + prop.oy - e * C.ELEVATION_PIXELS
        sx, sy = cam.world_to_screen(wx, wy)
        sprite = self._get_prop(prop, zoom)
        x = int(sx - sprite.get_width() * 0.5)

        # Every prop sprite bakes its shadow ellipse ~4 px above its
        # bottom edge. Offset the blit so that shadow lands on the tile
        # centre instead of floating above it.
        y = int(sy - sprite.get_height() + 4 * zoom)
        surface.blit(sprite, (x, y))

    # ------------------------------------------------------------------
    def _draw_unit(self, surface, unit):
        cam = self.camera
        zoom = cam.zoom
        col, row = unit.tile_position()
        c, r = int(math.floor(col)), int(math.floor(row))
        e = self.world.terrain.elevation[r][c] if self.world.in_bounds(c, r) else 0
        sx, sy = cam.world_to_screen(unit.x, unit.y - e * C.ELEVATION_PIXELS)

        # Ambient shadow (drawn first, under everything)
        self._draw_ambient_shadow(surface, sx, sy, unit.radius, zoom, alpha=75)

        # Selection ring with a subtle pulse
                # Selection ring: a soft ellipse with an inner glow, no sharp rectangle
        if unit.selected:
            pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.004)
            rw = max(6, int(unit.radius * (1.55 + 0.08 * pulse) * zoom))
            rh = max(3, int(unit.radius * 0.85 * zoom))
            # Soft outer glow
            ring = pygame.Surface((rw * 2 + 6, rh * 2 + 6), pygame.SRCALPHA)
            pygame.draw.ellipse(ring, (110, 230, 130, 60),
                                ring.get_rect(), 0)
            pygame.draw.ellipse(ring, (110, 230, 130, 180),
                                ring.get_rect(), max(2, int(2 * zoom)))
            surface.blit(ring, (int(sx - rw - 3), int(sy - rh - 3)))

        if unit.owner != C.FACTION_PLAYER:
            rw = max(5, int(unit.radius * 1.35 * zoom))
            rh = max(3, int(unit.radius * 0.75 * zoom))
            rect = pygame.Rect(sx - rw, sy - rh, rw * 2, rh * 2)
            color = C.FACTION_COLORS.get(unit.owner, C.FACTION_COLORS[C.FACTION_ENEMY])
            pygame.draw.ellipse(surface, color,
                                rect, max(1, int(1.5 * zoom)))

        sprite = self._get_unit(unit.kind, unit.facing, unit.anim_state,
                                unit.anim_phase, zoom)
        x = int(sx - sprite.get_width() * 0.5)

        # Align the sprite's visual base (its baked-in shadow ellipse) with
        # the unit's ground contact point. The shadow is at sprite pixel
        # ``h - 3``; scaling it by zoom keeps the alignment correct at any
        # zoom level. This prevents the sprite's bottom from being drawn
        # below the tile surface — which is what makes units look like
        # they sink when crossing a tile boundary.
        base_offset = 3.0 * zoom
        y = int(sy - sprite.get_height() + base_offset)
        surface.blit(sprite, (x, y))


        if unit.hit_flash > 0:
            alpha = int(200 * (unit.hit_flash / C.COMBAT_HIT_FLASH_TIME))
            r = max(4, int(unit.radius * 1.35 * zoom))
            flash = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(flash, (255, 60, 60, alpha), (r, r), r)
            surface.blit(flash, (int(sx - r), int(sy - r - 12 * zoom)))

        if self._should_draw_health_bar(unit):
            bar_w = int(C.HEALTH_BAR_WIDTH * zoom)
            bar_h = max(2, int(C.HEALTH_BAR_HEIGHT * zoom))
            bar_x = int(sx - bar_w * 0.5)
            bar_y = int(sy - sprite.get_height() + base_offset
                        - C.HEALTH_BAR_OFFSET * zoom)
            self._draw_health_bar(surface, bar_x, bar_y, bar_w, bar_h,
                                  unit.hp / unit.max_hp)
    def _should_draw_health_bar(self, unit):
        if unit.selected:
            return True
        if unit.owner == C.FACTION_ENEMY:
            return True
        if unit.hp < unit.max_hp:
            return True
        return False

    def _draw_health_bar(self, surface, x, y, w, h, frac):
        frac = max(0.0, min(1.0, frac))
        bg = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 180))
        surface.blit(bg, (x - 1, y - 1))
        if frac > 0.6:
            col = (90, 210, 100)
        elif frac > 0.3:
            col = (232, 196, 92)
        else:
            col = (220, 80, 70)
        pygame.draw.rect(surface, col, (x, y, int(w * frac), h))

    # ------------------------------------------------------------------
    def _draw_building(self, surface, building):
        cam = self.camera
        zoom = cam.zoom
        col, row = building.col, building.row
        e = self.world.terrain.elevation[row][col] if self.world.in_bounds(col, row) else 0
        world_y = building.front_y + C.TILE_HALF_H
        sx, sy = cam.world_to_screen(building.x, world_y - e * C.ELEVATION_PIXELS)

        sprite = self._get_building(building.kind, building.sprite, zoom)
        w, h = sprite.get_size()

        # Ambient shadow under the building base
        self._draw_ambient_shadow(surface, sx, sy, max(w, h) * 0.35, zoom,
                                  alpha=65)

        if building.selected:
            fw = (building.fp_w + building.fp_h) * C.TILE_HALF_W * 0.5 * zoom
            fh = (building.fp_w + building.fp_h) * C.TILE_HALF_H * 0.5 * zoom
            rect = pygame.Rect(sx - fw, sy - fh * 0.5, fw * 2, fh)
            pygame.draw.ellipse(surface, C.SELECTION_COLOR, rect,
                                max(2, int(2 * zoom)))

        if not building.complete:
            self._draw_foundation(surface, building)
            alpha = int(90 + 165 * building.progress)
            temp = sprite.copy()
            temp.set_alpha(alpha)
            surface.blit(temp, (int(sx - w * 0.5), int(sy - h)))
            self._draw_construction_progress(surface, building, sx, sy, w)
        else:
            surface.blit(sprite, (int(sx - w * 0.5), int(sy - h)))

        if building.owner != C.FACTION_PLAYER and building.complete:
            tint = sprite.copy()
            faction_color = C.FACTION_COLORS.get(
                building.owner, C.FACTION_COLORS[C.FACTION_ENEMY])
            tint.fill((*faction_color, 0), special_flags=pygame.BLEND_RGBA_ADD)
            tint.set_alpha(40)
            surface.blit(tint, (int(sx - w * 0.5), int(sy - h)))

        if self.world_fx is not None:
            self.world_fx.draw_flags_and_building_extras(surface, cam, building)

        if building.hit_flash > 0:
            alpha = int(160 * (building.hit_flash / C.COMBAT_HIT_FLASH_TIME))
            r = int(max(w, h) * 0.35)
            flash = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(flash, (255, 80, 80, alpha), (r, r), r)
            surface.blit(flash, (int(sx - r), int(sy - h * 0.6 - r)))

        if building.selected or building.hp < building.max_hp:
            bar_w = max(int(C.HEALTH_BAR_WIDTH * zoom * 1.6), w // 2)
            bar_h = max(3, int(C.HEALTH_BAR_HEIGHT * zoom))
            bar_x = int(sx - bar_w * 0.5)
            bar_y = int(sy - h - C.HEALTH_BAR_OFFSET * zoom)
            self._draw_health_bar(surface, bar_x, bar_y, bar_w, bar_h,
                                  building.hp / building.max_hp)

    def _draw_foundation(self, surface, building):
        cam = self.camera
        zoom = cam.zoom
        hw, hh = C.TILE_HALF_W * zoom, C.TILE_HALF_H * zoom
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for (c, r) in building.tiles():
            e = self.world.terrain.elevation[r][c] if self.world.in_bounds(c, r) else 0
            wx, wy = iso.tile_to_world(c, r)
            sx, sy = cam.world_to_screen(wx, wy - e * C.ELEVATION_PIXELS)
            pts = iso.tile_diamond(sx, sy, hw, hh)
            pygame.draw.polygon(overlay, (172, 168, 158, 200), pts)
            pygame.draw.polygon(overlay, C.CONSTRUCTION_OUTLINE, pts,
                                max(2, int(2 * zoom)))
        surface.blit(overlay, (0, 0))

    def _draw_construction_progress(self, surface, building, sx, sy, sprite_w):
        bw = C.CONSTRUCTION_BAR_W * self.camera.zoom
        bh = C.CONSTRUCTION_BAR_H * self.camera.zoom
        bx = int(sx - bw * 0.5)
        by = int(sy - building.sprite.get_height() * self.camera.zoom - 12)
        bg = pygame.Surface((int(bw), int(bh)), pygame.SRCALPHA)
        bg.fill((14, 16, 22, 220))
        pygame.draw.rect(bg, (60, 64, 72, 220), bg.get_rect(), 1)
        surface.blit(bg, (bx, by))
        fill_w = int((bw - 4) * building.progress)
        if fill_w > 0:
            pygame.draw.rect(surface, (232, 196, 92),
                             (bx + 2, by + 2, fill_w, int(bh - 4)))

    # ------------------------------------------------------------------
    def draw_placement_ghost(self, surface, kind, anchor_col, anchor_row, valid):
        cam = self.camera
        zoom = cam.zoom
        hw, hh = C.TILE_HALF_W * zoom, C.TILE_HALF_H * zoom
        defn = BUILDING_DEFS[kind]
        fp_w, fp_h = defn["footprint"]

        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        fill_col = (C.PLACEMENT_GHOST_FILL_VALID if valid
                    else C.PLACEMENT_GHOST_FILL_INVALID)
        line_col = (C.PLACEMENT_GHOST_VALID if valid
                    else C.PLACEMENT_GHOST_INVALID)
        for dc in range(fp_w):
            for dr in range(fp_h):
                c, r = anchor_col + dc, anchor_row + dr
                if not self.world.in_bounds(c, r):
                    continue
                e = self.world.terrain.get_elevation(c, r)
                wx, wy = iso.tile_to_world(c, r)
                sx, sy = cam.world_to_screen(wx, wy - e * C.ELEVATION_PIXELS)
                pts = iso.tile_diamond(sx, sy, hw, hh)
                pygame.draw.polygon(overlay, fill_col, pts)
                pygame.draw.polygon(overlay, line_col, pts,
                                    max(2, int(2 * zoom)))
        surface.blit(overlay, (0, 0))

        from .building_sprites import BuildingSpriteCache
        base = BuildingSpriteCache.get(kind)
        sw = max(1, int(base.get_width() * zoom))
        sh = max(1, int(base.get_height() * zoom))
        ghost = pygame.transform.smoothscale(base, (sw, sh))
        tint = (140, 240, 150) if valid else (240, 120, 110)
        tinted = ghost.copy()
        tinted.fill(tint, special_flags=pygame.BLEND_RGB_MULT)
        tinted.set_alpha(200)
        ghost.set_alpha(110)
        combined = ghost.copy()
        combined.blit(tinted, (0, 0))

        cc = anchor_col + (fp_w - 1) * 0.5
        rr = anchor_row + (fp_h - 1) * 0.5
        cx_w, cy_w = iso.tile_to_world(cc, rr)
        front_col = anchor_col + fp_w - 1
        front_row = anchor_row + fp_h - 1
        front_y = (front_col + front_row) * C.TILE_HALF_H + C.TILE_HALF_H
        e = self.world.terrain.get_elevation(int(cc), int(rr)) \
            if self.world.in_bounds(int(cc), int(rr)) else 0
        sx, sy = cam.world_to_screen(cx_w, front_y - e * C.ELEVATION_PIXELS)
        surface.blit(combined, (int(sx - sw * 0.5), int(sy - sh)))

    # ------------------------------------------------------------------
    def draw_unit_paths(self, surface, unit_manager):
        cam = self.camera
        for u in unit_manager.units:
            if u.dead:
                continue
            if u.state != UnitState.MOVING or not u.path:
                continue
            pts_world = [(u.x, u.y)] + list(u.path)
            screen_pts = []
            for (wx, wy) in pts_world:
                cf, rf = iso.world_to_tile_f(wx, wy)
                c, r = int(math.floor(cf)), int(math.floor(rf))
                e = self.world.terrain.elevation[r][c] \
                    if self.world.in_bounds(c, r) else 0
                sx, sy = cam.world_to_screen(wx, wy - e * C.ELEVATION_PIXELS)
                screen_pts.append((int(sx), int(sy)))
            if len(screen_pts) >= 2:
                pygame.draw.lines(surface, C.PATH_DEBUG_COLOR, False,
                                  screen_pts, 2)
            for (px, py) in screen_pts[1:]:
                pygame.draw.circle(surface, C.PATH_DEBUG_WAYPOINT_COLOR,
                                   (px, py), 3)

    # ------------------------------------------------------------------
    def draw_grid(self, surface):
        rng = self.visible_tile_range()
        if rng is None:
            return
        c0, c1, r0, r1 = rng
        cam = self.camera
        hw, hh = C.TILE_HALF_W * cam.zoom, C.TILE_HALF_H * cam.zoom
        color = (255, 255, 255, 40)
        line_w = max(1, int(cam.zoom))
        elev_px = C.ELEVATION_PIXELS
        elev = self.world.terrain.elevation
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                wx, wy = iso.tile_to_world(col, row)
                e = elev[row][col]
                sx, sy = cam.world_to_screen(wx, wy - e * elev_px)
                pts = iso.tile_diamond(sx, sy, hw, hh)
                pygame.draw.polygon(surface, color, pts, line_w)

    def draw_hover(self, surface, col, row):
        if not self.world.in_bounds(col, row):
            return
        cam = self.camera
        hw, hh = C.TILE_HALF_W * cam.zoom, C.TILE_HALF_H * cam.zoom
        e = self.world.terrain.elevation[row][col]
        wx, wy = iso.tile_to_world(col, row)
        sx, sy = cam.world_to_screen(wx, wy - e * C.ELEVATION_PIXELS)
        pts = iso.tile_diamond(sx, sy, hw, hh)
        pygame.draw.polygon(surface, (255, 236, 170), pts,
                            max(2, int(2 * cam.zoom)))