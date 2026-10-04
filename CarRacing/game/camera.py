"""Smooth third-person chase camera."""
import math

from panda3d.core import Point3

from .physics import wrap_angle

# (distance behind, height above ground, label)
PRESETS = ((6.5, 2.4, "CAMERA: NEAR"), (8.5, 3.2, "CAMERA: MEDIUM"), (11.0, 4.3, "CAMERA: FAR"))


class ChaseCamera:
    def __init__(self, camera_np, lens):
        self.cam = camera_np
        self.lens = lens
        self.preset = 1
        self.heading = 0.0
        self.fov = 62.0
        self.dist = PRESETS[1][0]
        self.height = PRESETS[1][1]
        self.pitch = 0.0
        self.pitch_target = 0.0
        self.shake_time = 0.0
        self.shake_strength = 0.0
        self.shake_clock = 0.0
        self.speed_phase = 0.0
        self.follow_x = None
        self.follow_y = None
        self.follow_z = None
        self.look_x = None
        self.look_y = None
        self.look_z = None

    def cycle_preset(self):
        self.preset = (self.preset + 1) % len(PRESETS)
        return PRESETS[self.preset][2]

    def reset(self, x, y, heading, elevation=0.0, snap=True):
        if snap:
            self.heading = heading
            self.dist, self.height = PRESETS[self.preset][0], PRESETS[self.preset][1]
            self.fov = 62.0
            self.follow_x = self.follow_y = self.follow_z = None
            self.look_x = self.look_y = self.look_z = None
        else:
            position = self.cam.getPos()
            self.follow_x, self.follow_y, self.follow_z = position
            self.fov = self.lens.getFov()[0]
            forward = self.cam.getQuat().getForward()
            self.look_x = position.x + forward.x * 20.0
            self.look_y = position.y + forward.y * 20.0
            self.look_z = position.z + forward.z * 20.0
        self.pitch = self.pitch_target = 0.0
        self.shake_time = self.shake_strength = 0.0
        if snap:
            self.speed_phase = 0.0
        self.update(0.0, x, y, heading, 0.0, elevation=elevation)

    def add_shake(self, impact):
        """Add a brief, damped camera impulse for a meaningful collision."""
        strength = min(0.16, max(0.0, impact - 2.0) * 0.006)
        self.shake_strength = max(self.shake_strength, strength)
        self.shake_time = max(self.shake_time, 0.22)

    def update(self, dt, x, y, heading, speed, acceleration=0.0, elevation=0.0):
        """x, y, heading: (interpolated) car pose; speed: forward speed in m/s."""
        dt = max(0.0, dt)
        # heading is smoothed so the camera swings gently through turns and hits
        self.heading += wrap_angle(heading - self.heading) * min(1.0, 4.5 * dt)
        want_dist, want_height = PRESETS[self.preset][0], PRESETS[self.preset][1]
        k = min(1.0, 3.0 * dt)
        self.dist += (want_dist - self.dist) * k
        self.height += (want_height - self.height) * k
        speed = abs(speed)
        self.pitch_target = max(-0.20, min(0.16, acceleration * 0.012))
        self.pitch += (self.pitch_target - self.pitch) * min(1.0, 2.8 * dt)
        back = self.dist + min(speed, 60.0) * 0.035
        fx, fy = -math.sin(self.heading), math.cos(self.heading)
        shake_x = shake_z = 0.0
        if self.shake_time > 0.0:
            self.shake_time = max(0.0, self.shake_time - dt)
            self.shake_clock += dt * 52.0
            fade = self.shake_time / 0.22
            shake_x = math.sin(self.shake_clock) * self.shake_strength * fade
            shake_z = math.sin(self.shake_clock * 1.37) * self.shake_strength * 0.45 * fade
            self.shake_strength *= max(0.0, 1.0 - 5.0 * dt)
        self.speed_phase += dt * (8.0 + speed * 0.35)
        vibration = 0.012 * min(speed / 60.0, 1.0) ** 2
        shake_x += math.sin(self.speed_phase) * vibration
        shake_z += math.sin(self.speed_phase * 1.37) * vibration * 0.45
        target_x = x - fx * back + shake_x
        target_y = y - fy * back
        target_z = elevation + self.height + speed * 0.008 + shake_z
        if self.follow_x is None:
            self.follow_x, self.follow_y, self.follow_z = target_x, target_y, target_z
        else:
            follow = 1.0 - math.exp(-7.0 * dt)
            self.follow_x += (target_x - self.follow_x) * follow
            self.follow_y += (target_y - self.follow_y) * follow
            self.follow_z += (target_z - self.follow_z) * follow
        self.cam.setPos(self.follow_x, self.follow_y, self.follow_z)
        # look slightly ahead of the car in its own direction of travel
        ahead = min(speed * 0.12, 7.0)
        cfx, cfy = -math.sin(self.heading), math.cos(self.heading)
        target_look_x = x + cfx * ahead
        target_look_y = y + cfy * ahead
        target_look_z = elevation + 1.2 + self.pitch
        if self.look_x is None:
            self.look_x, self.look_y, self.look_z = target_look_x, target_look_y, target_look_z
        else:
            look_follow = 1.0 - math.exp(-9.0 * dt)
            self.look_x += (target_look_x - self.look_x) * look_follow
            self.look_y += (target_look_y - self.look_y) * look_follow
            self.look_z += (target_look_z - self.look_z) * look_follow
        self.cam.lookAt(Point3(self.look_x, self.look_y, self.look_z))
        target_fov = 62.0 + min(speed, 60.0) * 0.16
        self.fov += (target_fov - self.fov) * min(1.0, 2.0 * dt)
        self.lens.setFov(self.fov)
