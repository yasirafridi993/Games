"""2D collision handling (pure Python).

Each car is approximated by three circles along its length.  Barriers are
handled analytically: the lateral distance of every circle from the centre line
is clamped, so a car can never leave the track or tunnel through a wall.
"""
import math

from .physics import wrap_angle

CAR_RADIUS = 1.05
CIRCLE_OFFSETS = (-1.3, 0.0, 1.3)
WALL_BOUNCE = 0.15
CAR_BOUNCE = 0.30


def collide_walls(car, track, dt):
    """Push the car back inside the barriers. Returns impact speed (m/s)."""
    body = car.body
    impact = 0.0
    limit = track.wall_dist - CAR_RADIUS
    touching = False
    for off in CIRCLE_OFFSETS:
        fx, fy = -math.sin(body.heading), math.cos(body.heading)
        p = track.project(body.x + fx * off, body.y + fy * off, car.hint)
        over = abs(p.lateral) - limit
        if over <= 0.0:
            continue
        touching = True
        side = 1.0 if p.lateral > 0 else -1.0
        ox, oy = p.nx * side, p.ny * side          # outward wall normal
        body.x -= ox * (over + 0.01)
        body.y -= oy * (over + 0.01)
        vn = body.vx * ox + body.vy * oy
        if vn > 0.0:
            body.vx -= (1.0 + WALL_BOUNCE) * vn * ox
            body.vy -= (1.0 + WALL_BOUNCE) * vn * oy
            scrub = min(0.25, 0.04 + 0.01 * vn)
            body.vx *= 1.0 - scrub
            body.vy *= 1.0 - scrub
            impact = max(impact, vn)
        # steer the nose back along the track so the car slides instead of sticking
        if body.vf > 2.0:
            diff = wrap_angle(p.heading - body.heading)
            if abs(diff) < 1.8:
                body.heading += diff * min(1.0, 2.5 * dt)
    if touching:
        # scraping friction along the wall
        k = max(0.0, 1.0 - 0.8 * dt)
        body.vx *= k
        body.vy *= k
        body.refresh_speeds()
    return impact


def collide_cars(a, b):
    """Resolve a car-car collision. Returns approach speed (0 if no contact)."""
    A, B = a.body, b.body
    dx, dy = A.x - B.x, A.y - B.y
    if dx * dx + dy * dy > 36.0:
        return 0.0
    afx, afy = -math.sin(A.heading), math.cos(A.heading)
    bfx, bfy = -math.sin(B.heading), math.cos(B.heading)
    best = None
    for oa in CIRCLE_OFFSETS:
        ax, ay = A.x + afx * oa, A.y + afy * oa
        for ob in CIRCLE_OFFSETS:
            bx, by = B.x + bfx * ob, B.y + bfy * ob
            ddx, ddy = ax - bx, ay - by
            dist = math.hypot(ddx, ddy)
            overlap = 2.0 * CAR_RADIUS - dist
            if overlap > 0.0 and (best is None or overlap > best[0]):
                if dist < 1e-6:
                    ddx, ddy, dist = 1.0, 0.0, 1.0
                best = (overlap, ddx / dist, ddy / dist)
    if best is None:
        return 0.0
    overlap, nx, ny = best
    push = overlap * 0.5 + 0.01
    A.x += nx * push
    A.y += ny * push
    B.x -= nx * push
    B.y -= ny * push
    vn = (A.vx - B.vx) * nx + (A.vy - B.vy) * ny
    if vn < 0.0:
        j = -(1.0 + CAR_BOUNCE) * vn * 0.5
        A.vx += j * nx
        A.vy += j * ny
        B.vx -= j * nx
        B.vy -= j * ny
        A.refresh_speeds()
        B.refresh_speeds()
        return -vn
    return 0.0
