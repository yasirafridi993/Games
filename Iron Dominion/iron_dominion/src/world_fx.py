"""Animated world effects: chimney smoke and waving flags.

Water animation lives in the renderer (it's a per-tile pass), but smoke
and flags are handled here as a small dedicated system so their code
stays isolated from terrain and buildings.
"""

import math
import random

import pygame

from . import config as C
from .building_defs import (
    TOWN_CENTER, HOUSE, BARRACKS, ARCHERY_RANGE, STABLE, STORAGE,
    FARM, TOWER, BLACKSMITH, MARKET,
)


# ---------------------------------------------------------------------------
# Anchors
# ---------------------------------------------------------------------------
# Flag anchors:  (fx, fy, pole_pixel_height_in_base_sprite)
#   fx / fy are fractions of the sprite's width / height measured from the
#   sprite's top-left corner.
_FLAG_ANCHORS = {
    TOWN_CENTER: (0.800, 0.560, 46),
    TOWER:       (0.500, 0.290, 42),
}

# Smoke anchors:  (fx, fy)  — top of the chimney in sprite-fraction coords.
_SMOKE_ANCHORS = {
    TOWN_CENTER:   (0.606, 0.480),
    HOUSE:         (0.670, 0.456),
    BLACKSMITH:    (0.669, 0.426),
    STORAGE:       (0.560, 0.480),
    BARRACKS:      (0.560, 0.440),
    ARCHERY_RANGE: (0.500, 0.470),
    STABLE:        (0.540, 0.450),
}


# ---------------------------------------------------------------------------
class WorldFx:
    def __init__(self, world, buildings):
        self.world = world
        self.buildings = buildings

        self.time = 0.0
        self.smoke_particles = []
        self._smoke_timers = {}     # id(building) -> seconds until next emit
        self._smoke_sprites = {}
        self._rng = random.Random(0x5A1CE)

    # ------------------------------------------------------------------
    def update(self, dt):
        self.time += dt

        # Emit smoke from every completed building that has a chimney.
        active_chimneys = set()
        for b in self.buildings.buildings:
            if not b.alive or not b.complete:
                continue
            anchor = _SMOKE_ANCHORS.get(b.kind)
            if anchor is None:
                continue

            key = id(b)
            active_chimneys.add(key)
            t = self._smoke_timers.get(key, 0.0) - dt
            if t <= 0:
                # Frequent staggered puffs make the chimney plume continuous.
                t = 0.32 + (key % 100) / 500.0
                self._emit_smoke(b, anchor)
            self._smoke_timers[key] = t
        self._smoke_timers = {
            key: timer for key, timer in self._smoke_timers.items()
            if key in active_chimneys
        }

        # Advance particles
        alive = []
        for p in self.smoke_particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["z"] += p["vz"] * dt
            # Slow the rise over time
            p["vz"] = max(4.0, p["vz"] - 5.0 * dt)
            p["life"] -= dt
            if p["life"] > 0:
                alive.append(p)
        self.smoke_particles = alive

    # ------------------------------------------------------------------
    def _emit_smoke(self, building, anchor):
        fx, fy = anchor
        w = building.sprite.get_width()
        h = building.sprite.get_height()
        front_wy = building.front_y + C.TILE_HALF_H
        sprite_top_wy = front_wy - h

        ax = building.x + (fx - 0.5) * w
        ay = sprite_top_wy + fy * h
        elevation = self.world.terrain.get_elevation(
            building.col, building.row)

        for _ in range(2):
            self.smoke_particles.append({
                "x": ax + self._rng.uniform(-4, 4),
                "y": ay + self._rng.uniform(-3, 3),
                "z": elevation * C.ELEVATION_PIXELS,
                "vx": self._rng.uniform(-5, 5),
                "vy": self._rng.uniform(-2.5, 2.5),
                "vz": self._rng.uniform(22, 32),
                "life": self._rng.uniform(2.2, 3.0),
                "max_life": 3.0,
                "size": self._rng.uniform(5.5, 8.5),
                "owner": building.owner,
                "col": building.col,
                "row": building.row,
            })

    # ------------------------------------------------------------------
    def draw_flags_and_building_extras(self, surface, camera, building):
        """Called from the renderer right after each building sprite."""
        if not building.alive or not building.complete:
            return
        entry = _FLAG_ANCHORS.get(building.kind)
        if entry is None:
            return

        fx, fy, pole_h_base = entry
        w = building.sprite.get_width()
        h = building.sprite.get_height()
        front_wy = building.front_y + C.TILE_HALF_H
        sprite_top_wy = front_wy - h

        bx = building.x + (fx - 0.5) * w
        by = sprite_top_wy + fy * h
        sx, sy = camera.world_to_screen(bx, by)
        zoom = camera.zoom

        pole_h = pole_h_base * zoom
        cloth_w = 26 * zoom
        cloth_h = 14 * zoom
        cloth_color = C.FACTION_COLORS.get(
            building.owner, C.FACTION_COLORS[C.FACTION_ENEMY])
        cloth_shadow = tuple(int(channel * 0.48) for channel in cloth_color)
        cloth_highlight = tuple(
            min(255, int(channel * 1.28)) for channel in cloth_color)

        # Pole
        pygame.draw.line(surface, (72, 52, 32),
                         (sx, sy - pole_h), (sx, sy),
                         max(1, int(1.5 * zoom)))
        pygame.draw.line(surface, (120, 90, 60),
                         (sx + 1, sy - pole_h), (sx + 1, sy),
                         max(1, int(0.5 * zoom)))

        # Waving cloth — sample a travelling sine along the length
        steps = 9
        phase = self.time * 3.6
        pts_top = []
        pts_bot = []
        for k in range(steps):
            kt = k / (steps - 1)
            px = sx + 1 + cloth_w * kt
            # Waviness grows with distance from the pole
            wave = math.sin(phase - kt * 3.2) * 2.5 * kt * zoom
            py_top = sy - pole_h + wave
            py_bot = py_top + cloth_h * (1.0 - 0.15 * kt)
            pts_top.append((px, py_top))
            pts_bot.append((px, py_bot))

        pts = pts_top + list(reversed(pts_bot))
        pygame.draw.polygon(surface, cloth_color, pts)
        pygame.draw.polygon(surface, cloth_shadow, pts, max(1, int(zoom)))
        # Bright top edge for a cloth highlight
        pygame.draw.lines(surface, cloth_highlight, False, pts_top,
                          max(1, int(zoom)))
        # Gold emblem
        ex = sx + cloth_w * 0.35
        ey = sy - pole_h + cloth_h * 0.55
        pygame.draw.circle(surface, (206, 168, 76),
                           (int(ex), int(ey)), max(1, int(2 * zoom)))
        pygame.draw.circle(surface, (150, 108, 42),
                           (int(ex), int(ey)), max(1, int(2 * zoom)), 1)

    # ------------------------------------------------------------------
    def draw_smoke(self, surface, camera, fog=None,
                   faction=C.FACTION_PLAYER):
        """Called once per frame, after the world pass, before UI."""
        if not self.smoke_particles:
            return
        zoom = camera.zoom
        for p in self.smoke_particles:
            if (p["owner"] != faction and fog is not None
                    and not fog.is_visible(faction, p["col"], p["row"])):
                continue
            sx, sy = camera.world_to_screen(p["x"], p["y"] - p["z"])
            life_t = max(0.0, min(1.0, p["life"] / p["max_life"]))
            age_t = 1.0 - life_t
            fade_in = min(1.0, age_t * 7.0 + 0.25)
            alpha = int(142 * life_t * fade_in)
            if alpha <= 4:
                continue
            # Plumes expand and drift gently as they rise from the chimney.
            drift = math.sin(self.time * 1.8 + p["x"] * 0.01) * 2.0 * zoom
            size = max(2, int(p["size"] * (1.0 + age_t * 1.8) * zoom))
            radius = max(2, size // 2)
            puff = self._smoke_sprites.get(radius)
            if puff is None:
                diameter = radius * 2 + 4
                puff = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
                center = diameter // 2
                pygame.draw.circle(puff, (74, 76, 82, 24),
                                   (center, center), radius + 2)
                pygame.draw.circle(puff, (124, 128, 134, 46),
                                   (center, center), radius)
                pygame.draw.ellipse(
                    puff, (194, 198, 202, 72),
                    (center - radius // 2, center - radius // 2,
                     max(2, radius), max(2, radius * 2 // 3)))
                if len(self._smoke_sprites) >= 64:
                    self._smoke_sprites.clear()
                self._smoke_sprites[radius] = puff
            puff.set_alpha(alpha)
            surface.blit(puff, (int(sx - puff.get_width() * 0.5 + drift),
                                int(sy - puff.get_height() * 0.5)))