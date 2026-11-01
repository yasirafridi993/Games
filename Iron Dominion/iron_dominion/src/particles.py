"""Tiny particle system used for hits, deaths and dust effects.

Particles are simple alpha-faded circles with velocity, gravity and a short
lifetime. They live in world space and are drawn after the depth-sorted
world pass, before the HUD.
"""

import math
import random

import pygame

from . import config as C
from . import iso


class Particle:
    __slots__ = ("x", "y", "z", "vx", "vy", "vz", "life", "max_life",
                 "color", "size", "gravity")

    def __init__(self, x, y, z, vx, vy, vz, life, color, size, gravity):
        self.x = x
        self.y = y
        self.z = z
        self.vx = vx
        self.vy = vy
        self.vz = vz
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.gravity = gravity

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.vz -= self.gravity * dt
        self.life -= dt
        if self.z < 0:
            self.z = 0.0
            self.vz = -self.vz * 0.35
            self.vx *= 0.55
            self.vy *= 0.55
        return self.life > 0


class ParticleManager:
    _sprite_cache = {}

    def __init__(self, world):
        self.world = world
        self.particles = []

    # ------------------------------------------------------------------
    def update(self, dt):
        alive = []
        for p in self.particles:
            if p.update(dt):
                alive.append(p)
        self.particles = alive

    # ------------------------------------------------------------------
    def _spawn_burst(self, wx, wy, count, color, speed_lo, speed_hi,
                     size_lo, size_hi, life, gravity, z=8.0):
        rng = random.Random()
        for _ in range(count):
            ang = rng.uniform(0, math.tau)
            sp = rng.uniform(speed_lo, speed_hi)
            vx = math.cos(ang) * sp
            vy = math.sin(ang) * sp
            vz = rng.uniform(25.0, 65.0)
            sz = rng.uniform(size_lo, size_hi)
            lf = life * rng.uniform(0.7, 1.15)
            self.particles.append(
                Particle(wx, wy, z, vx, vy, vz, lf, color, sz, gravity)
            )

    # ------------------------------------------------------------------
    def spawn_hit(self, wx, wy, target_kind):
        """Small spray on a unit taking damage."""
        if target_kind in ("archer", "worker"):
            color = (170, 40, 40)
        else:
            color = (200, 60, 60)
        self._spawn_burst(wx, wy, C.COMBAT_HIT_PARTICLES, color,
                          30.0, 90.0, 1.5, 3.0, 0.35, 240.0, z=18.0)
        # A couple of sparks
        self._spawn_burst(wx, wy, 3, (255, 220, 140),
                          40.0, 110.0, 1.2, 2.2, 0.22, 200.0, z=18.0)

    def spawn_building_hit(self, wx, wy):
        self._spawn_burst(wx, wy, C.COMBAT_HIT_PARTICLES, (150, 120, 90),
                          25.0, 80.0, 1.5, 3.0, 0.40, 260.0, z=20.0)

    def spawn_death(self, wx, wy, faction):
        if faction == C.FACTION_ENEMY:
            tint = (180, 70, 60)
        else:
            tint = (110, 150, 90)
        self._spawn_burst(wx, wy, C.COMBAT_DEATH_DUST, tint,
                          40.0, 130.0, 2.0, 4.0, 0.7, 260.0, z=12.0)
        # Extra dust puff
        self._spawn_burst(wx, wy, 6, (90, 80, 70),
                          15.0, 60.0, 2.5, 5.0, 0.55, 180.0, z=8.0)

    def spawn_building_death(self, wx, wy):
        self._spawn_burst(wx, wy, 30, (140, 120, 96),
                          60.0, 190.0, 2.0, 5.0, 0.95, 300.0, z=20.0)
        self._spawn_burst(wx, wy, 16, (200, 200, 200),
                          40.0, 140.0, 2.0, 4.0, 0.85, 260.0, z=26.0)

    # ------------------------------------------------------------------
    def draw(self, surface, camera):
        if not self.particles:
            return
        zoom = camera.zoom
        for p in self.particles:
            life_t = max(0.0, min(1.0, p.life / p.max_life))
            alpha = int(255 * life_t)
            if alpha < 6:
                continue
            sx, sy = camera.world_to_screen(p.x, p.y - p.z)
            r = max(1, int(p.size * zoom * (0.72 + 0.28 * life_t)))
            key = (p.color, r)
            sprite = self._sprite_cache.get(key)
            if sprite is None:
                pad = max(1, r // 3)
                diameter = r * 2 + pad * 2
                sprite = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
                center = (diameter // 2, diameter // 2)
                # Soft colored halo and a brighter, textured particle core.
                pygame.draw.circle(sprite, (*p.color, 34), center, r + pad)
                pygame.draw.ellipse(
                    sprite, (*p.color, 220),
                    (pad, pad + r // 4, r * 2, max(2, r * 2 - r // 2)))
                highlight = tuple(min(255, int(channel * 1.45 + 24))
                                  for channel in p.color)
                pygame.draw.circle(
                    sprite, (*highlight, 170),
                    (max(0, center[0] - max(1, r // 3)),
                     max(0, center[1] - max(1, r // 3))),
                    max(1, r // 3))
                if len(self._sprite_cache) >= 512:
                    self._sprite_cache.clear()
                self._sprite_cache[key] = sprite
            sprite.set_alpha(alpha)
            surface.blit(sprite, (int(sx - sprite.get_width() // 2),
                                  int(sy - sprite.get_height() // 2)))