"""Match configuration: number of opponents, team layout, mode."""

from . import config as C  # pyright: ignore[reportMissingImports]


class MatchConfig:
    def __init__(self, num_enemies=1, team_mode="ffa"):
        self.num_enemies = max(0, min(C.MAX_FACTIONS - 1, int(num_enemies)))
        self.team_mode = team_mode       # "ffa" | "2v2" | "3v3" | "4v4"

    # ------------------------------------------------------------------
    def total_factions(self):
        return self.num_enemies + 1

    def build_faction_manager(self):
        """Build a FactionManager with the right team assignments."""
        from .factions import FactionManager
        fm = FactionManager()
        n = self.total_factions()

        if self.team_mode == "ffa" or n <= 1:
            for i in range(1, n):
                fm.add_faction(i, i, is_ai=True)
            return fm

        # Parse team_mode like "2v2", "3v3", "4v4"
        try:
            a, b = self.team_mode.split("v")
            team_size = int(a)
        except Exception:
            team_size = 1

        # Ensure enough factions for team_mode. If not, fall back to FFA.
        teams_needed = (n + team_size - 1) // team_size
        if teams_needed * team_size < n:
            for i in range(1, n):
                fm.add_faction(i, i, is_ai=True)
            return fm

        # Player is on team 0. Assign others round-robin to teams 0..k-1
        # keeping team size balanced.
                # Player is on team 0. Assign others round-robin to teams 0..k-1
        # keeping team size balanced.
                # Player is on team 0. Distribute every faction across the
        # required number of teams, filling the smallest team first.
        teams = {t: [] for t in range(teams_needed)}
        teams[0].append(0)
        for i in range(1, n):
            # Smallest team first; tie-break by lowest team id so team 0
            # gets the player's ally before we start team 1.
            smallest = min(teams, key=lambda t: (len(teams[t]), t))
            teams[smallest].append(i)

        for t_id, members in teams.items():
            for f_id in members:
                fm.add_faction(f_id, t_id, is_ai=(f_id != 0))
        return fm