"""Modular catalog of player and AI vehicle identities and performance."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CarDefinition:
    car_id: str
    name: str
    category: str
    description: str
    color: tuple
    speed: float
    acceleration: float
    braking: float
    handling: float
    steering: float
    grip: float
    weight: float
    drift: float
    body_style: str
    accent_color: tuple = (1.0, 1.0, 1.0)
    livery: str = "double"


CARS = (
    CarDefinition("balanced", "Apex GT", "Balanced", "Predictable all-rounder for every circuit.",
                 (0.04, 0.28, 0.98), 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00,
                 "coupe", (0.88, 0.94, 1.0), "double"),
    CarDefinition("sports", "Vortex S", "Sports", "Fast response with strong acceleration and top speed.",
                 (0.96, 0.04, 0.055), 1.10, 1.12, 1.02, 1.06, 1.08, 1.02, 0.94, 1.06,
                 "sports", (1.0, 0.78, 0.18), "single"),
    CarDefinition("supercar", "Tempest X", "Supercar", "Explosive pace and sharp, demanding steering.",
                 (1.0, 0.48, 0.025), 1.22, 1.18, 1.08, 1.02, 1.16, 0.98, 0.92, 1.10,
                 "supercar", (0.08, 0.10, 0.14), "offset"),
    CarDefinition("muscle", "Ironclad V8", "Muscle", "Heavy launch power, built to own long straights.",
                 (0.04, 0.72, 0.20), 1.04, 1.16, 1.14, 0.82, 0.78, 0.92, 1.18, 1.24,
                 "muscle", (0.96, 0.94, 0.84), "twin"),
    CarDefinition("rally", "Ridgeback RS", "Rally", "High grip and forgiving control for rough, technical roads.",
                 (0.98, 0.28, 0.04), 0.96, 1.02, 1.08, 1.16, 1.04, 1.22, 1.02, 0.82,
                 "rally", (0.08, 0.22, 0.42), "rally"),
    CarDefinition("lightweight", "Swiftline", "Lightweight", "Nimble cornering with quick steering and lower speed.",
                 (0.02, 0.68, 0.90), 0.91, 1.06, 0.94, 1.20, 1.24, 1.10, 0.78, 0.88,
                 "lightweight", (0.06, 0.18, 0.28), "pinstripe"),
    CarDefinition("heavy_performance", "Titan R", "Heavy Performance", "Stable, powerful grand tourer with measured turn-in.",
                 (0.56, 0.18, 0.92), 1.08, 1.08, 1.18, 0.92, 0.82, 1.14, 1.24, 0.90,
                 "heavy", (1.0, 0.68, 0.25), "grand_tourer"),
)

CAR_BY_ID = {car.car_id: car for car in CARS}
AI_CAR_IDS = tuple(car.car_id for car in CARS)


def car_definition(car_id):
    try:
        return CAR_BY_ID[car_id]
    except KeyError:
        raise ValueError("Unknown car: %s" % car_id)


class CarManager:
    """Single source of truth for selectable cars and AI vehicle identities."""

    definitions = CARS
    by_id = CAR_BY_ID

    @classmethod
    def get(cls, car_id):
        return car_definition(car_id)
