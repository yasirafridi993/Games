"""Track browser with a 2D layout preview and local time records."""
from panda3d.core import LineSegs

from game.tracks import TRACKS, build_track
from . import theme


class TrackSelectionScreen(theme.Screen):
    def __init__(self, app, setup, progression, on_next, on_back):
        super().__init__(app, 0.60, (3.1, 2.0))
        self.setup, self.progression = setup, progression
        self.on_next, self.on_back = on_next, on_back
        self.index = next((i for i, track in enumerate(TRACKS) if track.track_id == setup.track_id), 0)
        self.preview_nodes = []
        p = self.panel
        theme.label(p, "SELECT TRACK", (0, 0.80), scale=0.11, fg=theme.TEXT)
        self.preview_root = p.attachNewNode("track-layout-preview")
        self.name = theme.label(p, "", (0.77, 0.49), scale=0.073, fg=theme.ACCENT,
                                may_change=True)
        self.details = theme.label(p, "", (0.77, 0.19), scale=0.042, fg=theme.TEXT,
                                   may_change=True)
        self.description = theme.label(p, "", (0.77, -0.16), scale=0.036, fg=theme.MUTED,
                                       may_change=True)
        self.records = theme.label(p, "", (0.77, -0.43), scale=0.038, fg=theme.GOLD,
                                   may_change=True)
        theme.button(p, "PREVIOUS TRACK", self._previous, (-0.78, 0, -0.63),
                     width=1.0, height=0.105, text_scale=0.038)
        theme.button(p, "NEXT TRACK", self._next, (0.0, 0, -0.63),
                     width=0.88, height=0.105, text_scale=0.038)
        theme.button(p, "SELECT TRACK", self._select, (0.78, 0, -0.63),
                     width=1.0, height=0.105, text_scale=0.038)
        theme.button(p, "BACK TO GARAGE", on_back, (0, 0, -0.80),
                     width=1.2, height=0.10, text_scale=0.04)
        self._refresh()

    def _previous(self):
        self.index = (self.index - 1) % len(TRACKS)
        self._refresh()

    def _next(self):
        self.index = (self.index + 1) % len(TRACKS)
        self._refresh()

    def _select(self):
        self.setup.track_id = TRACKS[self.index].track_id
        self.on_next()

    def _refresh(self):
        definition = TRACKS[self.index]
        track = build_track(definition.track_id)
        difficulty = "*" * track.difficulty + "-" * (5 - track.difficulty)
        difficulty_name = ("EASY", "MEDIUM", "HARD", "EXTREME")[track.difficulty - 1]
        length = "Short" if track.length < 1300 else "Medium" if track.length < 1900 else "Long"
        self.name.setText(definition.name)
        self.details.setText("TYPE  %s\nDIFFICULTY  %s\nLENGTH  %s  |  %.1f km\nATMOSPHERE  %s" %
                             (definition.track_type, difficulty_name + " " + difficulty, length,
                              track.length / 1000.0, definition.weather.upper()))
        self.description.setText(definition.description)
        record = self.progression.track_record(definition.track_id)
        best_lap = theme.format_time(record["best_lap"]) if record.get("best_lap") else "--:--.--"
        best_race = theme.format_time(record["best_time"]) if record.get("best_time") else "--:--.--"
        self.records.setText("BEST LAP  %s\nBEST RACE  %s" % (best_lap, best_race))
        self._draw_track(track)

    def _draw_track(self, track):
        for node in self.preview_nodes:
            node.removeNode()
        self.preview_nodes.clear()
        width = max(track.px) - min(track.px)
        height = max(track.py) - min(track.py)
        scale = 0.50 / max(width, height, 1.0)
        center_x, center_y = (max(track.px) + min(track.px)) / 2, (max(track.py) + min(track.py)) / 2
        for thickness, color in ((7.0, (0.22, 0.25, 0.31, 1)),
                                 (2.4, (0.92, 0.94, 0.98, 1))):
            lines = LineSegs("track-preview")
            lines.setThickness(thickness)
            lines.setColor(*color)
            for i in range(0, track.n + 1, 3):
                j = i % track.n
                x = (track.px[j] - center_x) * scale
                z = (track.py[j] - center_y) * scale
                if i == 0:
                    lines.moveTo(x, 0, z)
                else:
                    lines.drawTo(x, 0, z)
            lines.drawTo((track.px[0] - center_x) * scale, 0,
                         (track.py[0] - center_y) * scale)
            node = self.preview_root.attachNewNode(lines.create())
            node.setPos(-0.80, 0, 0.10)
            node.setDepthTest(False)
            node.setDepthWrite(False)
            self.preview_nodes.append(node)

    def show(self):
        self._refresh()
        super().show()

    def destroy(self):
        for node in self.preview_nodes:
            node.removeNode()
        self.preview_root.removeNode()
