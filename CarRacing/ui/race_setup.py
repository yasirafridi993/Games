"""Opponent count, AI behavior and lap-count selection."""
from panda3d.core import TextNode

from game.race_setup import DIFFICULTIES, LAP_COUNTS, OPPONENT_COUNTS
from game.tracks import track_definition
from game.cars import car_definition

from . import theme


class RaceSetupScreen(theme.Screen):
    def __init__(self, app, setup, on_start, on_cancel):
        super().__init__(app, 0.62, (2.5, 1.75))
        self.setup = setup
        panel = self.panel
        theme.label(panel, "RACE CONFIGURATION", (0, 0.70), scale=0.10, fg=theme.TEXT)
        theme.label(panel, "OPPONENTS", (-0.95, 0.35), scale=0.052, fg=theme.MUTED,
                    align=TextNode.ALeft)
        self.opponents_button = theme.button(panel, "", self._cycle_opponents, (0.45, 0, 0.35),
                                             width=0.8, height=0.11, text_scale=0.05)
        theme.label(panel, "AI DIFFICULTY", (-0.95, 0.08), scale=0.052, fg=theme.MUTED,
                    align=TextNode.ALeft)
        self.difficulty_button = theme.button(panel, "", self._cycle_difficulty, (0.45, 0, 0.08),
                                              width=0.8, height=0.11, text_scale=0.05)
        theme.label(panel, "LAPS", (-0.95, -0.19), scale=0.052, fg=theme.MUTED,
                    align=TextNode.ALeft)
        self.laps_button = theme.button(panel, "", self._cycle_laps, (0.45, 0, -0.19),
                                        width=0.8, height=0.11, text_scale=0.05)
        self.summary_text = theme.label(panel, "", (0, -0.48), scale=0.04, fg=theme.GOLD,
                                        may_change=True)
        theme.button(panel, "BACK TO TRACKS", on_cancel, (-0.60, 0, -0.68),
                     width=1.08, height=0.12, text_scale=0.044)
        theme.button(panel, "CONFIRM RACE", on_start, (0.60, 0, -0.68),
                     width=1.08, height=0.12, text_scale=0.044)
        self._refresh()

    @staticmethod
    def _cycle(values, current):
        return values[(values.index(current) + 1) % len(values)]

    def _cycle_opponents(self):
        self.setup.opponent_count = self._cycle(OPPONENT_COUNTS, self.setup.opponent_count)
        self._refresh()

    def _cycle_difficulty(self):
        self.setup.difficulty = self._cycle(DIFFICULTIES, self.setup.difficulty)
        self._refresh()

    def _cycle_laps(self):
        self.setup.total_laps = self._cycle(LAP_COUNTS, self.setup.total_laps)
        self._refresh()

    def _refresh(self):
        self.opponents_button["text"] = "%d" % self.setup.opponent_count
        self.difficulty_button["text"] = self.setup.difficulty.upper()
        self.laps_button["text"] = "%d" % self.setup.total_laps
        track = track_definition(self.setup.track_id)
        car = car_definition(self.setup.car_id)
        self.summary_text.setText("%s  |  %s  |  %d OPPONENTS  |  %d LAPS" %
                                  (track.name, car.name, self.setup.opponent_count, self.setup.total_laps))

    def show(self):
        self._refresh()
        super().show()
