"""Car entity: physics body + controls + race bookkeeping (no rendering)."""
import math

from .physics import CarBody, CarSpec, Controls


class Car:
    def __init__(self, name, color, spec=None, is_player=False, car_id="balanced"):
        self.name = name
        self.color = color
        self.car_id = car_id
        self.is_player = is_player
        self.body = CarBody(spec or CarSpec())
        self.controls = Controls()
        self.driver = None          # AIDriver or None (human)
        self.tracker = None         # CheckpointTracker, set by Race.reset()
        self.proj = None            # last TrackPos of the car centre
        self.hint = None            # centre-line index hint for fast projection
        self.reset_state()

    def reset_state(self):
        self.finished = False
        self.finish_time = None
        self.finish_order = 0
        self.lap_times = []
        self.lap_start_time = 0.0
        self.position = 1
        self.cruise = False         # slow down after finishing
        self.wrong_way_time = 0.0
        self.stuck_time = 0.0
        self.needs_respawn = False
        self.controls.reset()

    @property
    def speed_kmh(self):
        return abs(self.body.vf) * 3.6

    @property
    def wrong_way(self):
        return self.wrong_way_time > 1.0

    @property
    def stuck(self):
        return self.stuck_time > 3.0

    def pose(self, alpha):
        """Render pose interpolated between the last two physics steps."""
        b = self.body
        return (b.prev_x + (b.x - b.prev_x) * alpha,
                b.prev_y + (b.y - b.prev_y) * alpha,
                b.prev_heading + (b.heading - b.prev_heading) * alpha)

    def update_status(self, dt):
        """Wrong-way and stuck detection (used by HUD hints and AI recovery)."""
        b, p = self.body, self.proj
        along = -math.sin(b.heading) * p.tx + math.cos(b.heading) * p.ty
        moving_dir = along * (1.0 if b.vf >= 0 else -1.0)
        if abs(b.vf) > 3.0 and moving_dir < -0.3:
            self.wrong_way_time += dt
        else:
            self.wrong_way_time = 0.0
        c = self.controls
        if abs(b.vf) < 1.5 and (c.throttle > 0.05 or c.brake > 0.05):
            self.stuck_time += dt
        else:
            self.stuck_time = 0.0
