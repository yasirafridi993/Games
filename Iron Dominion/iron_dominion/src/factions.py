"""Faction and team management.

Faction IDs are 0..MAX_FACTIONS-1 (0 = player). Factions that share a
team ID are allies: they don't attack each other and win/lose together.
"""
from . import config as C  # pyright: ignore[reportMissingImports]

class FactionManager:
    def __init__(self):
        # {faction_id: team_id}
        self.team_of = {0: 0}
        self.num_factions = 1
        # Per-faction "is AI" flag
        self.is_ai = {0: False}

    # ------------------------------------------------------------------
    def add_faction(self, faction_id, team_id, is_ai=True):
        self.team_of[faction_id] = team_id
        self.is_ai[faction_id] = is_ai
        self.num_factions = max(self.num_factions, faction_id + 1)

    def factions(self):
        return sorted(self.team_of.keys())

    def ai_factions(self):
        return [f for f in self.factions() if self.is_ai.get(f)]

    # ------------------------------------------------------------------
    def team(self, faction_id):
        return self.team_of.get(faction_id, faction_id)

    def are_allied(self, a, b):
        if a is None or b is None:
            return False
        if a == b:
            return True
        return self.team(a) == self.team(b)

    def are_hostile(self, a, b):
        if a is None or b is None:
            return False
        return not self.are_allied(a, b)

    # ------------------------------------------------------------------
    def enemies_of(self, faction_id):
        return [f for f in self.factions()
                if self.are_hostile(faction_id, f)]

    def allies_of(self, faction_id):
        return [f for f in self.factions()
                if self.are_allied(faction_id, f)]

    def teams(self):
        """Return dict {team_id: [factions]}."""
        out = {}
        for f in self.factions():
            out.setdefault(self.team(f), []).append(f)
        return out

    # ------------------------------------------------------------------
    def victory_team(self):
        """If only one team has living factions, return that team; else None.
        `alive_check(faction) -> bool` is supplied by the caller."""
        return None  # overwritten by caller-specific logic