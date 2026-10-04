"""Race rules and simulation loop (pure Python, independent of the renderer).

States: "idle" (menu) -> "countdown" -> "racing" -> "complete" (player finishes).
Events for the UI/audio are appended to ``self.events`` as tuples.
"""
import random

from .ai import AIDriver, RacingLine
from .car import Car
from .cars import AI_CAR_IDS, CarManager
from .checkpoint import CheckpointTracker
from .collision import collide_cars, collide_walls
from .config import (AI_DIFFICULTIES, AI_PROFILES, PHYSICS_DT,
                     PLAYER_GRID_SLOT, PLAYER_NAME, TOTAL_LAPS)
from .physics import CarSpec

AI_STEP_EVERY = 4          # AI decisions run at PHYSICS_DT * 4 (30 Hz)
MAX_FRAME_TIME = 0.1
FINISH_COAST_TIME = 0.3
FINISH_ROLLOUT_LIMIT = 2.8
AI_CAR_WEIGHTS = {
    "easy": {
        "balanced": 4.0, "sports": 1.5, "supercar": 0.8, "muscle": 1.8,
        "rally": 3.5, "lightweight": 3.2, "heavy_performance": 1.4,
    },
    "medium": {car_id: 1.0 for car_id in AI_CAR_IDS},
    "hard": {
        "balanced": 1.2, "sports": 3.8, "supercar": 4.0, "muscle": 2.4,
        "rally": 1.5, "lightweight": 1.2, "heavy_performance": 3.0,
    },
}


def _choose_opponent_cars(count, difficulty, rng=None, exclude_ids=()):
    """Pick distinct car identities, weighting stronger profiles for harder races."""
    chooser = rng or random.Random()
    available = [car_id for car_id in AI_CAR_IDS if car_id not in exclude_ids]
    if count > len(available):
        available = list(AI_CAR_IDS)
    weights = dict(AI_CAR_WEIGHTS[difficulty])
    selected = []
    for _ in range(count):
        car_id = chooser.choices(available, weights=[weights[item] for item in available], k=1)[0]
        selected.append(car_id)
        available.remove(car_id)
    return selected


class Race:
    def __init__(self, track, total_laps=TOTAL_LAPS, opponent_count=3, difficulty="medium",
                 player_car_id="balanced"):
        if total_laps < 1:
            raise ValueError("total_laps must be positive")
        if not 1 <= opponent_count <= len(AI_PROFILES):
            raise ValueError("opponent_count must be between 1 and %d" % len(AI_PROFILES))
        if difficulty not in AI_DIFFICULTIES:
            raise ValueError("Unknown AI difficulty: %s" % difficulty)
        self.track = track
        self.player_car_id = player_car_id
        self.total_laps = total_laps
        self.opponent_count = opponent_count
        self.difficulty = difficulty
        player_def = CarManager.get(player_car_id)
        base = CarSpec()
        player_spec = self._car_spec(base, player_def)
        self.player = Car(PLAYER_NAME, player_def.color, player_spec, is_player=True, car_id=player_def.car_id)
        self.cars = [self.player]
        player_slot = min(PLAYER_GRID_SLOT, opponent_count)
        self.slots = {self.player: player_slot}
        grid_slots = max(4, opponent_count + 1)
        free_slots = [s for s in range(grid_slots) if s != player_slot]
        difficulty_profile = AI_DIFFICULTIES[difficulty]
        ai_car_ids = _choose_opponent_cars(
            opponent_count, difficulty, exclude_ids=(player_def.car_id,))
        for index, (profile, slot) in enumerate(zip(AI_PROFILES[:opponent_count], free_slots)):
            definition = CarManager.get(ai_car_ids[index])
            spec = self._car_spec(base, definition)
            car = Car(profile["name"], definition.color, spec, car_id=definition.car_id)
            skill = definition.handling * profile["corner"] * min(1.25, definition.grip ** 0.5)
            line = RacingLine(track, spec.max_speed, skill)
            car.driver = AIDriver(
                track, line, profile["bias"], difficulty_profile["aggression"],
                difficulty_profile["mistake_interval"], difficulty_profile["mistake_duration"],
                seed=index + 1)
            self.cars.append(car)
            self.slots[car] = slot
        # autopilot that drives the player's car after the finish
        auto_line = RacingLine(track, base.max_speed * 0.8, 0.9)
        self.autopilot = AIDriver(track, auto_line, 0.0)
        self.events = []
        self.reset()

    @staticmethod
    def _car_spec(base, definition):
        return CarSpec(
            max_speed=base.max_speed * definition.speed,
            reverse_speed=base.reverse_speed,
            accel=base.accel * definition.acceleration,
            brake_decel=base.brake_decel * definition.braking,
            reverse_accel=base.reverse_accel,
            coast_decel=base.coast_decel,
            steer_rate=base.steer_rate * definition.handling * definition.steering,
            steer_response=base.steer_response * definition.steering,
            grip=base.grip * definition.grip,
            slide_grip=base.slide_grip / definition.drift,
            handbrake_grip=base.handbrake_grip / definition.drift,
            handbrake_decel=base.handbrake_decel,
            slip_threshold=base.slip_threshold / definition.drift,
            weight=definition.weight,
        )

    # ----------------------------------------------------------- lifecycle
    def reset(self):
        self.state = "idle"
        self.race_time = 0.0
        self.countdown_t = 0.0
        self.accum = 0.0
        self.alpha = 1.0
        self.tick = 0
        self.finish_count = 0
        self.all_finished = False
        self.finish_rollout_elapsed = 0.0
        self.events = []
        for car in self.cars:
            car.reset_state()
            car.lap_times = []
            car.lap_start_time = 0.0
            s, lat = self.track.grid_slot(self.slots[car])
            x, y, h = self.track.point_at(s, lat)
            car.body.place(x, y, h)
            car.proj = self.track.project(x, y)
            car.hint = car.proj.index
            car.tracker = CheckpointTracker(self.track, self.total_laps, car.proj.s)
            if car is self.player:
                car.driver = None
            elif car.driver:
                car.driver.reset()
        self._update_positions()

    def start(self):
        self.reset()
        self.state = "countdown"
        self.events.append(("countdown", 3))

    def pop_events(self):
        events, self.events = self.events, []
        return events

    @property
    def active(self):
        return self.state in ("racing", "finished")

    # -------------------------------------------------------------- update
    def update(self, dt):
        dt = min(dt, MAX_FRAME_TIME)
        if self.state == "countdown":
            before = int(self.countdown_t)
            self.countdown_t += dt
            now = int(self.countdown_t)
            if self.countdown_t >= 3.0:
                self.state = "racing"
                self.events.append(("go",))
            elif now != before:
                self.events.append(("countdown", 3 - now))
        elif self.active:
            self.accum += dt
            while self.accum >= PHYSICS_DT and self.active:
                self._step(PHYSICS_DT)
                self.accum -= PHYSICS_DT
            if not self.active:
                self.accum = 0.0
            self.alpha = self.accum / PHYSICS_DT

    def _step(self, dt):
        if self.state == "finished":
            self._step_finish_rollout(dt)
            return
        self.race_time += dt
        self.tick += 1
        ai_tick = self.tick % AI_STEP_EVERY == 0
        cars = self.cars
        for car in cars:
            if ai_tick and car.driver is not None:
                car.driver.update(dt * AI_STEP_EVERY, car, cars, True)
            car.body.update(dt, car.controls)
        for i in range(len(cars)):
            for j in range(i + 1, len(cars)):
                impact = collide_cars(cars[i], cars[j])
                if impact > 2.0:
                    self.events.append(("car_hit", cars[i], cars[j], impact))
        for car in cars:
            impact = collide_walls(car, self.track, dt)
            if impact > 2.0:
                self.events.append(("wall_hit", car, impact))
            car.proj = self.track.project(car.body.x, car.body.y, car.hint)
            car.hint = car.proj.index
            car.update_status(dt)
            if car.needs_respawn:
                self.respawn(car, to_last_gate=True)
            if not car.tracker.finished:
                for ev in car.tracker.update(car.proj.s):
                    self._on_tracker_event(car, ev)
                    if self.state in ("complete", "finished"):
                        break
            if self.state in ("complete", "finished"):
                break
        self._update_positions()
        if not self.all_finished and all(car.tracker.finished for car in cars):
            self.all_finished = True
            self.state = "complete"
            self.events.append(("race_complete",))

    def _on_tracker_event(self, car, ev):
        if ev == "checkpoint":
            self.events.append(("checkpoint", car))
        elif ev == "lap":
            car.lap_times.append(self.race_time - car.lap_start_time)
            car.lap_start_time = self.race_time
            self.events.append(("lap", car, car.tracker.laps_done + 1))
        elif ev == "finish":
            car.lap_times.append(self.race_time - car.lap_start_time)
            self.finish_count += 1
            car.finished = True
            car.finish_time = self.race_time
            car.finish_order = self.finish_count
            car.cruise = True
            if car is self.player:
                self.all_finished = True
                self.finish_rollout_elapsed = 0.0
                self.state = "finished"
                self.events.append(("race_complete",))
            self.events.append(("finish", car, car.finish_order, car.finish_time))

    def _step_finish_rollout(self, dt):
        """Let the player coast beyond the line, then brake before results appear."""
        self.finish_rollout_elapsed += dt
        body = self.player.body
        controls = self.player.controls
        controls.throttle = 0.0
        controls.steer = 0.0
        controls.handbrake = False
        controls.brake = min(1.0, max(
            0.0, (self.finish_rollout_elapsed - FINISH_COAST_TIME) / 0.65))
        body.update(dt, controls)

        if body.speed <= 0.45 or self.finish_rollout_elapsed >= FINISH_ROLLOUT_LIMIT:
            body.place(body.x, body.y, body.heading)
            controls.reset()
            self.state = "complete"

    def _update_positions(self):
        done = sorted((c for c in self.cars if c.finished), key=lambda c: c.finish_order)
        rest = sorted((c for c in self.cars if not c.finished),
                      key=lambda c: -c.tracker.progress)
        for i, car in enumerate(done + rest):
            car.position = i + 1

    # ------------------------------------------------------------ respawns
    def respawn(self, car, to_last_gate=False):
        """Put a car back on the centre line, facing the right way."""
        s = car.tracker.last_gate_s() if to_last_gate else car.proj.s
        x, y, h = self.track.point_at(s, 0.0)
        car.body.place(x, y, h)
        car.controls.reset()
        car.proj = self.track.project(x, y)
        car.hint = car.proj.index
        car.tracker.teleport(s, to_last_gate)
        car.needs_respawn = False
        car.stuck_time = car.wrong_way_time = 0.0
        if car.driver:
            car.driver.reset()

    def reset_player(self):
        if self.state == "racing":
            self.respawn(self.player, to_last_gate=True)
