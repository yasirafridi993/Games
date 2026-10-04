"""Validated settings for a single race."""
from dataclasses import dataclass

from .cars import CAR_BY_ID
from .config import DEFAULT_TRACK_ID

OPPONENT_COUNTS = tuple(range(1, 8))
DIFFICULTIES = ("easy", "medium", "hard")
LAP_COUNTS = (1, 2, 3, 5, 10)


@dataclass
class RaceSetup:
    track_id: str = DEFAULT_TRACK_ID
    opponent_count: int = 3
    difficulty: str = "medium"
    total_laps: int = 3
    car_id: str = "balanced"

    def validate(self, track_ids, car_ids=None):
        if self.track_id not in track_ids:
            raise ValueError("Unknown track: %s" % self.track_id)
        valid_cars = car_ids if car_ids is not None else CAR_BY_ID
        if self.car_id not in valid_cars:
            raise ValueError("Unknown car: %s" % self.car_id)
        if self.opponent_count not in OPPONENT_COUNTS:
            raise ValueError("Opponent count must be between 1 and 7")
        if self.difficulty not in DIFFICULTIES:
            raise ValueError("Unknown difficulty: %s" % self.difficulty)
        if self.total_laps not in LAP_COUNTS:
            raise ValueError("Unsupported lap count: %s" % self.total_laps)
