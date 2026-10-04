"""Arcade car physics (pure Python).

The car keeps a world-space velocity.  Each step the velocity is split into a
forward part (driven by throttle/brake) and a sideways part that is damped by
"grip".  Low grip (handbrake, or cornering too hard) lets the car slide.
"""
import math
from dataclasses import dataclass


def wrap_angle(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def _toward_zero(v, amount):
    if v > 0:
        return max(0.0, v - amount)
    return min(0.0, v + amount)


@dataclass
class CarSpec:
    max_speed: float = 58.0        # m/s  (~209 km/h)
    reverse_speed: float = 14.0
    accel: float = 16.0
    brake_decel: float = 36.0
    reverse_accel: float = 12.0
    coast_decel: float = 4.0
    steer_rate: float = 1.85       # max yaw rate (rad/s)
    steer_response: float = 6.0    # how quickly the steering wheel moves
    grip: float = 7.5
    slide_grip: float = 3.2
    handbrake_grip: float = 1.4
    handbrake_decel: float = 9.0
    slip_threshold: float = 36.0   # |yaw * speed| above which grip fades
    weight: float = 1.0


class Controls:
    __slots__ = ("throttle", "brake", "steer", "handbrake")

    def __init__(self):
        self.reset()

    def reset(self):
        self.throttle = 0.0
        self.brake = 0.0
        self.steer = 0.0       # +1 = left, -1 = right
        self.handbrake = False


class CarBody:
    def __init__(self, spec):
        self.spec = spec
        self.place(0.0, 0.0, 0.0)

    def place(self, x, y, heading):
        self.x = self.prev_x = x
        self.y = self.prev_y = y
        self.heading = self.prev_heading = heading
        self.vx = self.vy = 0.0
        self.vf = 0.0           # forward speed (negative when reversing)
        self.vr = 0.0           # sideways speed
        self.steer = 0.0        # current (smoothed) steering, -1..1
        self.yaw_rate = 0.0
        self.grip = self.spec.grip
        self.long_accel = 0.0

    @property
    def speed(self):
        return math.hypot(self.vx, self.vy)

    def forward(self):
        return -math.sin(self.heading), math.cos(self.heading)

    def update(self, dt, c):
        sp = self.spec
        self.prev_x, self.prev_y, self.prev_heading = self.x, self.y, self.heading
        h = self.heading
        fx, fy = -math.sin(h), math.cos(h)
        rx, ry = fy, -fx
        vf = self.vx * fx + self.vy * fy
        vr = self.vx * rx + self.vy * ry
        start_vf = vf

        # ---- longitudinal: throttle / brake / reverse / coasting
        if c.brake > 0.05:
            if vf > 0.5:
                vf = max(0.0, vf - (sp.brake_decel / max(0.6, sp.weight ** 0.35)) * c.brake * dt)
            elif vf > -sp.reverse_speed:
                vf = max(-sp.reverse_speed, vf - sp.reverse_accel * c.brake * dt)
        elif c.throttle > 0.05:
            if vf < -0.5:
                vf = min(0.0, vf + sp.brake_decel * dt)
            else:
                ratio = min(1.0, max(0.0, vf) / sp.max_speed)
                vf += (sp.accel / max(0.6, sp.weight)) * c.throttle * (1.0 - ratio * ratio) * dt
        else:
            vf = _toward_zero(vf, (sp.coast_decel + 0.004 * vf * vf) * dt)
        if c.handbrake and abs(vf) > 1.0:
            vf = _toward_zero(vf, sp.handbrake_decel * dt)

        # keep world velocity, re-express after the heading changes
        self.vx = fx * vf + rx * vr
        self.vy = fy * vf + ry * vr

        # ---- steering (authority grows with speed, fades a little at top speed)
        rate = sp.steer_response * (1.8 if (c.steer == 0 or c.steer * self.steer < 0) else 1.0)
        step = rate * dt
        self.steer += max(-step, min(step, c.steer - self.steer))
        spd = abs(vf)
        low = max(-1.0, min(1.0, vf / 5.0))
        high = 1.0 - 0.6 * min(1.0, spd / sp.max_speed)
        yaw = self.steer * sp.steer_rate * low * high / math.sqrt(max(0.6, sp.weight))
        if c.handbrake and spd > 6.0:
            yaw *= 1.45
        self.yaw_rate = yaw
        self.heading += yaw * dt

        # ---- grip: damp the sideways velocity in the new car frame
        h = self.heading
        fx, fy = -math.sin(h), math.cos(h)
        rx, ry = fy, -fx
        vf = self.vx * fx + self.vy * fy
        vr = self.vx * rx + self.vy * ry
        if c.handbrake and spd > 3.0:
            target = sp.handbrake_grip
        else:
            over = min(1.0, max(0.0, (abs(yaw * vf) - sp.slip_threshold) / 25.0))
            target = sp.grip + (sp.slide_grip - sp.grip) * over
        self.grip += (target - self.grip) * min(1.0, 12.0 * dt)
        vr *= math.exp(-self.grip * dt)
        self.vx = fx * vf + rx * vr
        self.vy = fy * vf + ry * vr

        top = sp.max_speed * 1.03
        sp_now = math.hypot(self.vx, self.vy)
        if sp_now > top:
            k = top / sp_now
            self.vx *= k
            self.vy *= k

        self.vf, self.vr = vf, vr
        self.long_accel = (vf - start_vf) / dt if dt > 0 else 0.0
        self.x += self.vx * dt
        self.y += self.vy * dt

    def refresh_speeds(self):
        """Recompute vf / vr after an external change to the velocity."""
        fx, fy = self.forward()
        self.vf = self.vx * fx + self.vy * fy
        self.vr = self.vx * fy - self.vy * fx
