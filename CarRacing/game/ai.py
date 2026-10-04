"""Waypoint based AI drivers (pure Python).

RacingLine builds a smoothed line (cutting corners) with a target speed for each
centre-line sample: slow for tight bends, fast on straights, with a backwards
pass so the car brakes early enough.  AIDriver steers toward a look-ahead point
on that line, regulates speed, avoids cars ahead and recovers when stuck.
"""
import math
import random

from .physics import wrap_angle

MAX_LINE_OFFSET = 7.0
LATERAL_ACCEL = 21.0       # m/s^2 an AI car is willing to corner at
BRAKE_DECEL = 24.0         # m/s^2 used for the braking pass


def _smooth(values, radius):
    n = len(values)
    out = []
    for i in range(n):
        total = 0.0
        for k in range(-radius, radius + 1):
            total += values[(i + k) % n]
        out.append(total / (2 * radius + 1))
    return out


class RacingLine:
    def __init__(self, track, max_speed, corner_skill):
        n, ds = track.n, track.ds
        self.track = track
        wide = _smooth(track.kappa, 8)
        max_offset = max(1.0, track.half_width - 3.5)
        self.offset = [max(-max_offset, min(max_offset, k * 190.0)) for k in wide]   # + = left
        self.x, self.y = [], []
        for i in range(n):
            self.x.append(track.px[i] + track.nx[i] * self.offset[i])
            self.y.append(track.py[i] + track.ny[i] * self.offset[i])
        headings = []
        for i in range(n):
            j = (i + 1) % n
            headings.append(math.atan2(-(self.x[j] - self.x[i]), self.y[j] - self.y[i]))
        kappa = [wrap_angle(headings[i] - headings[i - 1]) / ds for i in range(n)]
        kappa = _smooth(kappa, 2)
        lat = LATERAL_ACCEL * corner_skill * corner_skill
        speed = []
        for i, curvature in enumerate(kappa):
            grade = abs((track.pz[(i + 1) % n] - track.pz[i]) / max(ds, 1e-3))
            grade_factor = max(0.62, 1.0 - min(0.38, grade * 0.035))
            speed.append(min(max_speed, math.sqrt(lat / max(abs(curvature), 1e-3))) * grade_factor)
        for _ in range(3):                                  # braking pass
            for i in range(n - 1, -2, -1):
                a, b = i % n, (i + 1) % n
                speed[a] = min(speed[a], math.sqrt(speed[b] ** 2 + 2.0 * BRAKE_DECEL * ds))
        self.speed = speed


class AIDriver:
    def __init__(self, track, line, bias=0.0, aggression=1.0,
                 mistake_interval=None, mistake_duration=(0.0, 0.0), seed=0):
        self.track = track
        self.line = line
        self.bias = bias
        self.aggression = aggression
        self.mistake_interval = mistake_interval
        self.mistake_duration = mistake_duration
        self.rng = random.Random(seed)
        self.reset()

    def reset(self):
        self.avoid = 0.0
        self.mode = "drive"
        self.mode_timer = 0.0
        self.stuck = 0.0
        self.wrong = 0.0
        self.recoveries = 0
        self.recovery_clock = 0.0
        self.mistake_time = 0.0
        self.mistake_phase = 0.0
        self.mistake_cooldown = self._next_mistake()

    def _next_mistake(self):
        if self.mistake_interval is None:
            return math.inf
        return self.rng.uniform(*self.mistake_interval)

    def update(self, dt, car, cars, racing=True):
        track, line = self.track, self.line
        body, c, p = car.body, car.controls, car.proj
        n, ds = track.n, track.ds
        speed = body.vf
        fx, fy = -math.sin(body.heading), math.cos(body.heading)
        rx, ry = fy, -fx

        # target point on the racing line
        look = max(9.0, 6.0 + abs(speed) * 0.42)
        j = (p.index + int(look / ds) + 1) % n
        lane_limit = max(0.0, track.half_width - 2.5)
        lateral = max(-lane_limit, min(lane_limit, line.offset[j] + self.bias + self.avoid))
        tx = track.px[j] + track.nx[j] * lateral
        ty = track.py[j] + track.ny[j] * lateral
        err = wrap_angle(math.atan2(-(tx - body.x), ty - body.y) - body.heading)

        # target speed
        k = (p.index + 2 + int(max(0.0, speed) * 0.25 / ds)) % n
        target = line.speed[k]
        if abs(err) > 0.6:
            target *= 0.7
        if car.cruise:
            target = min(target, 24.0)

        # avoid cars ahead
        want_avoid = 0.0
        for other in cars:
            if other is car:
                continue
            dx, dy = other.body.x - body.x, other.body.y - body.y
            ahead = dx * fx + dy * fy
            side = dx * rx + dy * ry
            if 0.0 < ahead < 16.0 and abs(side) < 3.4:
                want_avoid = (3.5 if side > 0 else -3.5) * self.aggression
                if ahead < 8.0 / max(0.6, self.aggression):
                    target = min(target, max(other.body.vf, 6.0) + 3.0 * self.aggression)
        self.avoid += (want_avoid - self.avoid) * min(1.0, 3.0 * dt)

        # recovery manoeuvres
        self.recovery_clock += dt
        if self.recovery_clock > 10.0:
            self.recoveries = 0
        if self.mode == "reverse":
            self.mode_timer -= dt
            c.throttle, c.handbrake = 0.0, False
            c.brake = 1.0
            c.steer = -1.0 if err > 0 else 1.0
            if self.mode_timer <= 0.0:
                self.mode = "drive"
            return
        if racing and target > 8.0 and abs(speed) < 1.5:
            self.stuck += dt
        else:
            self.stuck = max(0.0, self.stuck - dt)
        if abs(wrap_angle(p.heading - body.heading)) > 1.9:
            self.wrong += dt
        else:
            self.wrong = 0.0
        if self.stuck > 1.5:
            self.stuck = 0.0
            self.recoveries += 1
            self.recovery_clock = 0.0
            if self.recoveries >= 3:
                car.needs_respawn = True
                self.recoveries = 0
            else:
                self.mode, self.mode_timer = "reverse", 1.2
        if self.wrong > 2.5:
            self.wrong = 0.0
            car.needs_respawn = True

        # controls
        c.handbrake = False
        c.steer = max(-1.0, min(1.0, err * 2.4 - body.yaw_rate * 0.35))
        diff = target - speed
        if diff > 0.0:
            c.throttle, c.brake = min(1.0, diff / 3.0), 0.0
        elif diff < -1.5:
            c.throttle, c.brake = 0.0, min(1.0, -diff / 6.0)
        else:
            c.throttle, c.brake = 0.0, 0.0

        if self.mistake_interval is not None:
            self.mistake_cooldown -= dt
            if self.mistake_cooldown <= 0.0 and self.mistake_time <= 0.0:
                self.mistake_time = self.rng.uniform(*self.mistake_duration)
                self.mistake_cooldown = self._next_mistake()
            if self.mistake_time > 0.0:
                self.mistake_time = max(0.0, self.mistake_time - dt)
                self.mistake_phase += dt * 5.0
                c.steer = max(-1.0, min(1.0, c.steer + math.sin(self.mistake_phase) * 0.35))
                c.throttle *= 0.55
