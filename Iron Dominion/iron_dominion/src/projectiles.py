"""Homing projectiles (arrows) used by ranged units.

Projectiles track their target's current position. If the target dies or
disappears mid-flight, they continue toward the last known point and then
fizzle harmlessly.
"""

import math

import pygame

from . import config as C


class Projectile:
    __slots__ = (
        "x", "y", "z", "vx", "vy", "target",
        "damage", "attacker_kind", "kind",
        "ttl", "alive", "impacted",
        "last_target_xy", "trail",
        "attacker_owner",
    )

    def __init__(self, x, y, target, damage, attacker_kind, kind,
                 attacker_owner):
        self.x = float(x)
        self.y = float(y)
        self.z = C.PROJECTILE_Z_START
        self.vx = 0.0
        self.vy = 0.0
        self.target = target
        self.damage = damage
        self.attacker_kind = attacker_kind
        self.kind = kind
        self.ttl = C.PROJECTILE_TTL
        self.alive = True
        self.impacted = False
        self.last_target_xy = (float(x), float(y))
        self.trail = []
        self.attacker_owner = attacker_owner

    # ------------------------------------------------------------------
    def _target_position(self):
        t = self.target
        if t is None:
            return self.last_target_xy

        # Unit
        from .units import Unit
        if isinstance(t, Unit):
            if t.dead:
                return self.last_target_xy
            self.last_target_xy = (t.x, t.y)
            return (t.x, t.y)

        # Building
        if not getattr(t, "alive", False):
            return self.last_target_xy
        self.last_target_xy = (t.x, t.y)
        return (t.x, t.y)

    # ------------------------------------------------------------------
    def update(self, dt):
        if not self.alive:
            return

        tx, ty = self._target_position()
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)

        if dist <= C.PROJECTILE_IMPACT_RADIUS:
            self.impacted = True
            self.alive = False
            return

        nx = dx / dist
        ny = dy / dist
        step = C.PROJECTILE_SPEED * dt
        if step > dist:
            step = dist
        self.x += nx * step
        self.y += ny * step
        self.vx = nx
        self.vy = ny

        self.trail.append((self.x, self.y, self.z))
        if len(self.trail) > C.PROJECTILE_MAX_TRAIL:
            self.trail.pop(0)

        self.ttl -= dt
        if self.ttl <= 0:
            self.alive = False

    # ------------------------------------------------------------------
    def draw(self, surface, camera):
        if not self.alive:
            return
        zoom = camera.zoom

        pts = []
        for (wx, wy, wz) in self.trail:
            sx, sy = camera.world_to_screen(wx, wy - wz)
            pts.append((int(sx), int(sy)))
        sx, sy = camera.world_to_screen(self.x, self.y - self.z)
        pts.append((int(sx), int(sy)))

        ang = math.atan2(self.vy, self.vx)
        direction = (math.cos(ang), math.sin(ang))
        normal = (-direction[1], direction[0])
        faction_color = C.FACTION_COLORS.get(
            self.attacker_owner, C.FACTION_COLORS[C.FACTION_PLAYER])

        if len(pts) > 1:
            padding = max(3, int(5 * zoom))
            left = min(point[0] for point in pts) - padding
            top = min(point[1] for point in pts) - padding
            right = max(point[0] for point in pts) + padding + 1
            bottom = max(point[1] for point in pts) + padding + 1
            trail = pygame.Surface((right - left, bottom - top),
                                   pygame.SRCALPHA)
            local_pts = [(x - left, y - top) for x, y in pts]
            for i in range(1, len(local_pts)):
                strength = i / (len(local_pts) - 1)
                alpha = int(35 + strength * 125)
                pygame.draw.line(
                    trail, (220, 232, 230, alpha),
                    local_pts[i - 1], local_pts[i],
                    max(2, int(4 * zoom)))
                pygame.draw.line(
                    trail, (255, 248, 220, min(255, alpha + 45)),
                    local_pts[i - 1], local_pts[i],
                    max(1, int(zoom)))
            surface.blit(trail, (left, top))

        tip = (int(sx), int(sy))
        shaft_length = max(8, int(12 * zoom))
        shaft_start = (sx - direction[0] * shaft_length,
                       sy - direction[1] * shaft_length)
        # Dark shaft outline, warm wood core and a bright metal arrowhead.
        shaft_end = (sx - direction[0] * max(2, 3 * zoom),
                     sy - direction[1] * max(2, 3 * zoom))
        pygame.draw.line(surface, (66, 46, 30), shaft_start, shaft_end,
                         max(3, int(3 * zoom)))
        pygame.draw.line(surface, (174, 126, 72), shaft_start, shaft_end,
                         max(1, int(1.5 * zoom)))

        feather_center = (sx - direction[0] * shaft_length,
                          sy - direction[1] * shaft_length)
        feather_size = max(2, 4 * zoom)
        feathers = [
            (feather_center,
             (feather_center[0] + normal[0] * feather_size,
              feather_center[1] + normal[1] * feather_size),
             (feather_center[0] - direction[0] * feather_size,
              feather_center[1] - direction[1] * feather_size)),
            (feather_center,
             (feather_center[0] - normal[0] * feather_size,
              feather_center[1] - normal[1] * feather_size),
             (feather_center[0] - direction[0] * feather_size,
              feather_center[1] - direction[1] * feather_size)),
        ]
        for feather in feathers:
            pygame.draw.polygon(surface, (40, 34, 30), feather)
            pygame.draw.polygon(surface, faction_color, feather, 1)

        head_base = (sx - direction[0] * max(2, 3 * zoom),
                     sy - direction[1] * max(2, 3 * zoom))
        head_half_width = max(1.5, 2.5 * zoom)
        head = [
            tip,
            (head_base[0] + normal[0] * head_half_width,
             head_base[1] + normal[1] * head_half_width),
            (head_base[0] - normal[0] * head_half_width,
             head_base[1] - normal[1] * head_half_width),
        ]
        pygame.draw.polygon(surface, (72, 76, 78), head)
        pygame.draw.polygon(surface, (216, 222, 216), head, 1)
        highlight_end = (
            head_base[0] + normal[0] * head_half_width * 0.5,
            head_base[1] + normal[1] * head_half_width * 0.5)
        pygame.draw.line(surface, (255, 252, 224), tip, highlight_end,
                         max(1, int(zoom)))


class ProjectileManager:
    def __init__(self):
        self.projectiles = []

    def spawn(self, x, y, target, damage, attacker_kind, attacker_owner):
        kind = "arrow"
        p = Projectile(x, y, target, damage, attacker_kind, kind,
                       attacker_owner)
        self.projectiles.append(p)
        return p

    def update(self, dt):
        alive = []
        impacts = []
        for p in self.projectiles:
            p.update(dt)
            if p.alive:
                alive.append(p)
            elif p.impacted:
                impacts.append(p)
        self.projectiles = alive
        return impacts

    def draw(self, surface, camera):
        for p in self.projectiles:
            p.draw(surface, camera)