"""Unit definitions: stats, cost, train time, producer building, combat data.

Attack ranges are in **world pixels** now (Phase 8). A melee unit needs the
distance between its centre and the target's centre to be less than
``attack_range + target.radius``.
"""

from .resources import FOOD, WOOD, STONE, IRON

WORKER = "worker"
SWORDSMAN = "swordsman"
SPEARMAN = "spearman"
ARCHER = "archer"
CAVALRY = "cavalry"

MILITARY_KINDS = (SWORDSMAN, SPEARMAN, ARCHER, CAVALRY)
RANGED_KINDS = (ARCHER,)


UNIT_DEFS = {
    # -------------------------------------------------------------------
    WORKER: {
        "name": "Worker",
        "max_hp": 40,
        "speed": 90.0,
        "radius": 9,
        "sprite_size": (26, 34),
        "damage": 4,
        "armor": 0,
        "attack_range": 30.0,
        "attack_cooldown": 1.6,
        "aggro_range": 0.0,
        "train_time": 12.0,
        "cost": {FOOD: 5},
        "pop_cost": 1,
        "projectile": None,
    },
    # -------------------------------------------------------------------
    SWORDSMAN: {
        "name": "Swordsman",
        "max_hp": 200,
        "speed": 70.0,
        "radius": 11,
        "sprite_size": (26, 36),
        "damage": 20,
        "armor": 13,
        "attack_range": 42.0,
        "attack_cooldown": 1.15,
        "aggro_range": 220.0,
        "train_time": 18.0,
        "cost": {FOOD: 40, IRON: 10},
        "pop_cost": 1,
        "projectile": None,
    },
    # -------------------------------------------------------------------
    SPEARMAN: {
        "name": "Spearman",
        "max_hp": 180,
        "speed": 72.0,
        "radius": 10,
        "sprite_size": (26, 40),
        "damage": 18,
        "armor": 8,
        "attack_range": 58.0,
        "attack_cooldown": 1.35,
        "aggro_range": 240.0,
        "train_time": 16.0,
        "cost": {FOOD: 20, WOOD: 10},
        "pop_cost": 1,
        "projectile": None,
    },
    # -------------------------------------------------------------------
    ARCHER: {
        "name": "Archer",
        "max_hp": 160,
        "speed": 76.0,
        "radius": 10,
        "sprite_size": (26, 36),
        "damage": 12,
        "armor": 5,
        "attack_range": 250.0,
        "attack_cooldown": 1.45,
        "aggro_range": 320.0,
        "train_time": 10.0,
        "cost": {FOOD: 10, WOOD: 10},
        "pop_cost": 1,
        "projectile": "arrow",
    },
    # -------------------------------------------------------------------
    CAVALRY: {
        "name": "Cavalry",
        "max_hp": 240,
        "speed": 120.0,
        "radius": 13,
        "sprite_size": (38, 48),
        "damage": 25,
        "armor": 13,
        "attack_range": 46.0,
        "attack_cooldown": 1.55,
        "aggro_range": 280.0,
        "train_time": 20.0,
        "cost": {FOOD: 50, IRON: 10},
        "pop_cost": 2,
        "projectile": None,
    },
}


# ---------------------------------------------------------------------------
# Counter table: (attacker, target) -> damage multiplier
# ---------------------------------------------------------------------------
COUNTER_TABLE = {
    # Anti-cavalry dominates cavalry
    (SPEARMAN, CAVALRY): 2.0,
    (CAVALRY, SPEARMAN): 0.5,

    # Cavalry closes on archers and cuts them down
    (CAVALRY, ARCHER): 2.0,
    (ARCHER, CAVALRY): 0.6,

    # Archers punish slow infantry
    (ARCHER, SWORDSMAN): 1.5,
    (ARCHER, SPEARMAN): 1.4,

    # Swordsmen close on archers
    (SWORDSMAN, ARCHER): 1.3,

    # Same-tier infantry is even
    (SWORDSMAN, SPEARMAN): 0.95,
    (SPEARMAN, SWORDSMAN): 0.95,
}


def counter_multiplier(attacker_kind, target_kind):
    return COUNTER_TABLE.get((attacker_kind, target_kind), 1.0)


def cost_string(kind):
    c = UNIT_DEFS[kind]["cost"]
    if not c:
        return "-"
    return "  ".join(f"{v} {k}" for k, v in c.items())


def train_time(kind):
    return UNIT_DEFS[kind]["train_time"]