"""Definitions for every constructible building."""

from .resources import FOOD, WOOD, STONE, IRON

TOWN_CENTER = "town_center"
HOUSE = "house"
BARRACKS = "barracks"
ARCHERY_RANGE = "archery_range"
STABLE = "stable"
STORAGE = "storage"
FARM = "farm"
TOWER = "tower"
BLACKSMITH = "blacksmith"
MARKET = "market"

BUILDABLE_ORDER = (
    HOUSE, FARM, STORAGE,
    BARRACKS, ARCHERY_RANGE, STABLE, TOWER,
    BLACKSMITH, MARKET,
)

BUILDING_DEFS = {
    TOWN_CENTER: {
        "name": "Town Center",
        "cost": {},
        "max_hp": 1500,
        "footprint": (3, 3),
        "build_time": 0.0,
        "pop_bonus": 10,
        "sprite_size": (260, 232),
        "description": "Base centre. Drop-off + Worker training.",
        "buildable": False,
        "is_dropoff": True,
        "produces": ("worker",),
        "researches": (),
    },
    HOUSE: {
        "name": "House",
        "cost": {WOOD: 30},
        "max_hp": 400,
        "footprint": (2, 2),
        "build_time": 15.0,
        "pop_bonus": 5,
        "sprite_size": (168, 158),
        "description": "+5 population",
        "buildable": True,
        "is_dropoff": False,
        "produces": (),
        "researches": (),
    },
    FARM: {
        "name": "Farm",
        "cost": {WOOD: 60},
        "max_hp": 250,
        "footprint": (3, 3),
        "build_time": 18.0,
        "pop_bonus": 0,
        "sprite_size": (256, 120),
        "description": "Slowly generates Food.",
        "buildable": True,
        "is_dropoff": False,
        "produces": (),
        "researches": (),
    },
    STORAGE: {
        "name": "Resource Storage",
        "cost": {WOOD: 100},
        "max_hp": 600,
        "footprint": (2, 2),
        "build_time": 18.0,
        "pop_bonus": 0,
        "sprite_size": (176, 158),
        "description": "Extra drop-off point.",
        "buildable": True,
        "is_dropoff": True,
        "produces": (),
        "researches": (),
    },
    BARRACKS: {
        "name": "Barracks",
        "cost": {WOOD: 150},
        "max_hp": 900,
        "footprint": (3, 3),
        "build_time": 25.0,
        "pop_bonus": 0,
        "sprite_size": (240, 210),
        "description": "Trains Swordsmen and Spearmen.",
        "buildable": True,
        "is_dropoff": False,
        "produces": ("swordsman", "spearman"),
        "researches": (),
    },
    ARCHERY_RANGE: {
        "name": "Archery Range",
        "cost": {WOOD: 150, STONE: 50},
        "max_hp": 900,
        "footprint": (3, 2),
        "build_time": 25.0,
        "pop_bonus": 0,
        "sprite_size": (222, 186),
        "description": "Trains Archers.",
        "buildable": True,
        "is_dropoff": False,
        "produces": ("archer",),
        "researches": (),
    },
    STABLE: {
        "name": "Stable",
        "cost": {WOOD: 175},
        "max_hp": 900,
        "footprint": (3, 2),
        "build_time": 28.0,
        "pop_bonus": 0,
        "sprite_size": (222, 186),
        "description": "Trains Cavalry.",
        "buildable": True,
        "is_dropoff": False,
        "produces": ("cavalry",),
        "researches": (),
    },
    TOWER: {
        "name": "Defensive Tower",
        "cost": {WOOD: 100, STONE: 50},
        "max_hp": 800,
        "footprint": (1, 1),
        "build_time": 20.0,
        "pop_bonus": 0,
        "sprite_size": (96, 172),
        "description": "Ranged defensive structure.",
        "buildable": True,
        "is_dropoff": False,
        "produces": (),
        "researches": (),
    },
    BLACKSMITH: {
        "name": "Blacksmith",
        "cost": {WOOD: 150, STONE: 50},
        "max_hp": 800,
        "footprint": (3, 2),
        "build_time": 24.0,
        "pop_bonus": 0,
        "sprite_size": (220, 192),
        "description": "Researches military attack and armor upgrades.",
        "buildable": True,
        "is_dropoff": False,
        "produces": (),
        "researches": ("forged_weapons", "plated_armor",
                       "tempered_steel", "masterwork_armor"),
    },
    MARKET: {
        "name": "Market",
        "cost": {WOOD: 150, FOOD: 50},
        "max_hp": 700,
        "footprint": (3, 2),
        "build_time": 22.0,
        "pop_bonus": 0,
        "sprite_size": (232, 176),
        "description": "Researches economic upgrades.",
        "buildable": True,
        "is_dropoff": False,
        "produces": (),
        "researches": ("better_tools", "improved_carts", "swift_pack"),
    },
}


def cost_string(kind):
    c = BUILDING_DEFS[kind]["cost"]
    if not c:
        return "Free"
    return "  ".join(f"{amt} {r}" for r, amt in c.items())


def produces(kind):
    return BUILDING_DEFS[kind].get("produces", ())


def researches(kind):
    return BUILDING_DEFS[kind].get("researches", ())