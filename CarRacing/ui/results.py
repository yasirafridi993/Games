"""Race results screen."""
from panda3d.core import TextNode

from . import theme


class ResultsScreen(theme.Screen):
    def __init__(self, app, on_again, on_setup, on_menu):
        super().__init__(app, 0.55, (2.8, 2.3))
        p = self.panel
        theme.label(p, "RACE FINISHED", (0, 0.98), scale=0.11, fg=theme.TEXT)
        self.position_text = theme.label(p, "", (0, 0.80), scale=0.075, fg=theme.GOLD, may_change=True)
        self.time_text = theme.label(p, "", (0, 0.66), scale=0.06, fg=theme.TEXT, may_change=True)
        self.details_text = theme.label(p, "", (0, 0.53), scale=0.039, fg=theme.MUTED, may_change=True)
        theme.label(p, "STANDINGS", (0, 0.41), scale=0.042, fg=theme.MUTED)
        self.rows = []
        for i in range(8):
            z = 0.32 - i * 0.078
            name = theme.label(p, "", (-1.0, z), scale=0.043, align=TextNode.ALeft, may_change=True)
            when = theme.label(p, "", (1.0, z), scale=0.043, align=TextNode.ARight, may_change=True)
            self.rows.append((name, when))
        self.lap_text = theme.label(p, "", (0, -0.39), scale=0.032, fg=theme.MUTED, may_change=True)
        self.record_text = theme.label(p, "", (0, -0.56), scale=0.037, fg=theme.GOLD, may_change=True)
        theme.button(p, "RACE AGAIN", on_again, (-0.91, 0, -0.91),
                     width=0.70, height=0.11, text_scale=0.041)
        theme.button(p, "CHANGE SETUP", on_setup, (0, 0, -0.91),
                     width=0.78, height=0.11, text_scale=0.041)
        theme.button(p, "MAIN MENU", on_menu, (0.91, 0, -0.91),
                     width=0.70, height=0.11, text_scale=0.041)

    def set_result(self, position, total, time_str, standings, setup, track_name, lap_times,
                   best_time, best_lap):
        """standings: list of (place, name, time_str_or_None, is_player) in finishing order."""
        position_text = "WINNER!  1 / %d" % total if position == 1 else "POSITION: %d / %d" % (position, total)
        self.position_text.setText(position_text)
        self.time_text.setText("TIME: " + time_str)
        self.details_text.setText(
            "%s  |  LAPS: %d/%d  |  %d OPPONENTS  |  %s" %
            (track_name, setup.total_laps, setup.total_laps, setup.opponent_count, setup.difficulty.upper()))
        for i, (name, when) in enumerate(self.rows):
            if i < len(standings):
                place, car_name, t, is_player = standings[i]
                colour = theme.GOLD if is_player else theme.TEXT
                name.setText("%d.  %s" % (place, car_name))
                name.setFg(colour)
                when.setText(t if t else "racing...")
                when.setFg(colour if t else theme.MUTED)
            else:
                name.setText("")
                when.setText("")
        split_lines = []
        for start in range(0, len(lap_times), 5):
            values = " / ".join(theme.format_time(value) for value in lap_times[start:start + 5])
            split_lines.append("LAP TIMES: " + values if start == 0 else "             " + values)
        self.lap_text.setText("\n".join(split_lines))
        best_time_text = theme.format_time(best_time) if best_time is not None else "--:--.--"
        best_lap_text = theme.format_time(best_lap) if best_lap is not None else "--:--.--"
        self.record_text.setText("BEST RACE: %s   BEST LAP: %s" % (best_time_text, best_lap_text))
