"""Technology definitions, per-faction tech state, and the research queue."""

from .resources import FOOD, WOOD, STONE, IRON


# Building keys as strings to avoid an import cycle.
BLACKSMITH = "blacksmith"
MARKET = "market"


class TechDef:
    __slots__ = ("key", "name", "description", "cost", "research_time",
                 "building", "requires", "effects")

    def __init__(self, key, name, description, cost, research_time,
                 building, requires, effects):
        self.key = key
        self.name = name
        self.description = description
        self.cost = cost
        self.research_time = research_time
        self.building = building
        self.requires = tuple(requires)
        self.effects = effects


TECH_DEFS = {
    # -----------------------------------------------------------------
    # Blacksmith (military)
    # -----------------------------------------------------------------
    "forged_weapons": TechDef(
        key="forged_weapons",
        name="Forged Weapons",
        description="+2 attack for all military units",
        cost={IRON: 50},
        research_time=25.0,
        building=BLACKSMITH,
        requires=(),
        effects={"attack": 2},
    ),
    "tempered_steel": TechDef(
        key="tempered_steel",
        name="Tempered Steel",
        description="+4 additional attack (stacks)",
        cost={IRON: 120},
        research_time=50.0,
        building=BLACKSMITH,
        requires=("forged_weapons",),
        effects={"attack": 4},
    ),
    "plated_armor": TechDef(
        key="plated_armor",
        name="Plated Armor",
        description="+2 armor for all military units",
        cost={IRON: 50, WOOD: 30},
        research_time=30.0,
        building=BLACKSMITH,
        requires=(),
        effects={"armor": 2},
    ),
    "masterwork_armor": TechDef(
        key="masterwork_armor",
        name="Masterwork Armor",
        description="+3 additional armor (stacks)",
        cost={IRON: 120},
        research_time=55.0,
        building=BLACKSMITH,
        requires=("plated_armor",),
        effects={"armor": 3},
    ),
    # -----------------------------------------------------------------
    # Market (economic)
    # -----------------------------------------------------------------
    "better_tools": TechDef(
        key="better_tools",
        name="Better Tools",
        description="+25% worker gather rate",
        cost={WOOD: 100},
        research_time=30.0,
        building=MARKET,
        requires=(),
        effects={"gather_rate": 0.25},
    ),
    "improved_carts": TechDef(
        key="improved_carts",
        name="Improved Carts",
        description="+5 worker carry capacity",
        cost={WOOD: 100},
        research_time=35.0,
        building=MARKET,
        requires=(),
        effects={"carry_bonus": 5},
    ),
    "swift_pack": TechDef(
        key="swift_pack",
        name="Swift Pack",
        description="+15% movement speed for all units",
        cost={WOOD: 150, FOOD: 50},
        research_time=45.0,
        building=MARKET,
        requires=("better_tools",),
        effects={"speed_mult": 0.15},
    ),
}


_TECH_ORDER = (
    "forged_weapons", "plated_armor",
    "tempered_steel", "masterwork_armor",
    "better_tools", "improved_carts", "swift_pack",
)


def techs_for_building(building_kind):
    return [k for k in _TECH_ORDER if TECH_DEFS[k].building == building_kind]


# ---------------------------------------------------------------------------
class TechState:
    """Per-faction research progress and the resulting stat bonuses."""

    __slots__ = ("researched", "bonuses")

    def __init__(self):
        self.researched = set()
        self.bonuses = {
            "attack": 0,
            "armor": 0,
            "speed_mult": 1.0,
            "gather_rate_mult": 1.0,
            "carry_bonus": 0,
        }

    def has(self, key):
        return key in self.researched

    def is_available(self, key):
        if key in self.researched:
            return False
        for req in TECH_DEFS[key].requires:
            if req not in self.researched:
                return False
        return True

    def apply(self, key):
        if key in self.researched:
            return
        defn = TECH_DEFS[key]
        self.researched.add(key)
        for k, v in defn.effects.items():
            if k == "attack":
                self.bonuses["attack"] += v
            elif k == "armor":
                self.bonuses["armor"] += v
            elif k == "speed_mult":
                self.bonuses["speed_mult"] += v
            elif k == "gather_rate":
                self.bonuses["gather_rate_mult"] += v
            elif k == "carry_bonus":
                self.bonuses["carry_bonus"] += v


# ---------------------------------------------------------------------------
class TechItem:
    __slots__ = ("key", "time_total", "time_left")

    def __init__(self, key):
        self.key = key
        self.time_total = TECH_DEFS[key].research_time
        self.time_left = self.time_total


class TechQueue:
    __slots__ = ("building", "items")

    def __init__(self, building):
        self.building = building
        self.items = []

    # ------------------------------------------------------------------
    def can_enqueue(self):
        return len(self.items) == 0

    def enqueue(self, key):
        if not self.can_enqueue():
            return False
        self.items.append(TechItem(key))
        return True

    def cancel_last(self):
        if not self.items:
            return None
        return self.items.pop()

    # ------------------------------------------------------------------
    def update(self, dt, tech_state, unit_manager, building_manager):
        if not self.items:
            return
        item = self.items[0]
        item.time_left -= dt
        if item.time_left > 0:
            return

        tech_state.apply(item.key)
        owner = self.building.owner
        unit_manager.apply_tech_to_faction(tech_state, owner)
        building_manager.apply_tech_to_faction(tech_state, owner)
        self.items.pop(0)

    def current_progress(self):
        if not self.items:
            return 0.0
        item = self.items[0]
        if item.time_total <= 0:
            return 1.0
        return max(0.0, min(1.0, 1.0 - item.time_left / item.time_total))