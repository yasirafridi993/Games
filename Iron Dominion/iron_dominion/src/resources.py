"""Resource types and the player stockpile."""

FOOD = "food"
WOOD = "wood"
STONE = "stone"
IRON = "iron"

RESOURCE_ORDER = (FOOD, WOOD, STONE, IRON)

RESOURCE_NAMES = {
    FOOD: "Food",
    WOOD: "Wood",
    STONE: "Stone",
    IRON: "Iron",
}

# Order the HUD displays them in (top -> bottom)
RESOURCE_COLORS = {
    FOOD: (208, 116, 100),
    WOOD: (156, 108, 62),
    STONE: (170, 172, 178),
    IRON: (196, 152, 96),
}

STARTING_RESOURCES = {
    FOOD: 200,
    WOOD: 200,
    STONE: 100,
    IRON: 50,
}

MAX_RESOURCES = 9999


class Stockpile:
    """The player's banked resources."""

    def __init__(self):
        self.amounts = dict(STARTING_RESOURCES)

    def get(self, resource: str) -> int:
        return self.amounts.get(resource, 0)

    def add(self, resource: str, amount: int) -> None:
        if amount <= 0:
            return
        self.amounts[resource] = min(
            MAX_RESOURCES, self.amounts.get(resource, 0) + amount
        )

    def can_afford(self, cost: dict) -> bool:
        for r, amt in cost.items():
            if self.amounts.get(r, 0) < amt:
                return False
        return True

    def spend(self, cost: dict) -> bool:
        if not self.can_afford(cost):
            return False
        for r, amt in cost.items():
            self.amounts[r] = self.amounts.get(r, 0) - amt
        return True