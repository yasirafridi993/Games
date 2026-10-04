"""In-race HUD: lap / position / speed / time, countdown, messages and a mini-map."""
from direct.gui.DirectGui import DirectFrame
from panda3d.core import CardMaker, LineSegs, TextNode, TransparencyAttrib

from . import theme

MAP_SIZE = 0.40          # longest side of the mini-map (aspect2d units)


class HUD:
    def __init__(self, app, race, track):
        self.app = app
        self.race = race
        self.track = track
        self.root = app.aspect2d.attachNewNode("hud")
        self._cache = {}

        # ---- info panel (top-left), same lines as the spec
        corner = app.a2dTopLeft.attachNewNode("hud-left")
        self.panel_np = corner
        DirectFrame(parent=corner, frameColor=(0.02, 0.03, 0.06, 0.55),
                    frameSize=(0, 0.82, -0.38, 0), pos=(0.04, 0, -0.04))
        DirectFrame(parent=corner, frameColor=theme.ACCENT, frameSize=(0, 0.012, -0.38, 0), pos=(0.04, 0, -0.04))
        theme.label(corner, "RACE TELEMETRY", (0.09, -0.055), scale=0.038,
                    fg=theme.MUTED, align=TextNode.ALeft)
        self.lines = {}
        line_colors = {"lap": theme.GOLD, "pos": theme.TEXT, "time": theme.MUTED}
        for i, key in enumerate(("lap", "pos", "time")):
            self.lines[key] = theme.label(corner, "", (0.09, -0.15 - i * 0.09),
                                          scale=0.062, fg=line_colors[key],
                                          align=TextNode.ALeft, may_change=True)

        # Dedicated top-right speed instrument: large numeric readout and a
        # compact segmented tachometer-style bar sized to fit standard windows.
        self.speed_panel = app.a2dTopRight.attachNewNode("hud-speedometer")
        DirectFrame(parent=self.speed_panel, frameColor=(0.02, 0.03, 0.06, 0.76),
                    frameSize=(-1.02, 0, -0.49, 0), pos=(-0.04, 0, -0.04))
        DirectFrame(parent=self.speed_panel, frameColor=theme.ACCENT,
                    frameSize=(-1.02, -1.008, -0.49, 0), pos=(-0.04, 0, -0.04))
        theme.label(self.speed_panel, "SPEED", (-0.91, -0.075), scale=0.043,
                    fg=theme.MUTED, align=TextNode.ALeft)
        self.speed_text = theme.label(self.speed_panel, "000", (-0.92, -0.245),
                                      scale=0.18, fg=(0.48, 0.88, 1.0, 1.0),
                                      align=TextNode.ALeft, may_change=True)
        theme.label(self.speed_panel, "KM/H", (-0.20, -0.218), scale=0.045,
                    fg=theme.TEXT, align=TextNode.ARight)
        self.speed_segments = []
        segment_count = 20
        segment_width = 0.029
        segment_gap = 0.012
        for index in range(segment_count):
            x = -0.91 + index * (segment_width + segment_gap)
            height = 0.025 + 0.025 * ((index % 5) == 4)
            segment = DirectFrame(
                parent=self.speed_panel,
                frameColor=(0.20, 0.25, 0.30, 0.60),
                frameSize=(0, segment_width, -height, 0),
                pos=(x, 0, -0.34))
            self.speed_segments.append(segment)
        self.speed_ratio = 0.0
        self.speed_text_value = None

        # ---- centre texts
        self.countdown_text = theme.label(self.root, "", (0, 0.18), scale=0.36, fg=theme.TEXT, may_change=True)
        self.message_text = theme.label(app.a2dTopCenter, "", (0, -0.20), scale=0.085, fg=theme.TEXT,
                                        may_change=True)
        self.wrong_text = theme.label(self.root, "WRONG WAY", (0, 0.52), scale=0.14, fg=theme.ACCENT)
        self.hint_text = theme.label(app.a2dBottomCenter, "STUCK?  PRESS R TO RESET YOUR CAR",
                                     (0, 0.14), scale=0.055, fg=theme.GOLD)
        self.cam_text = theme.label(app.a2dBottomRight, "", (-0.05, 0.08), scale=0.045, fg=theme.MUTED,
                                    align=TextNode.ARight, may_change=True)
        self.countdown_t = 99.0
        self.countdown_go = False
        self.message_t = 99.0
        self.message_dur = 1.0
        self.message_priority = 0
        self.message_sticky = False
        self.cam_t = 99.0
        self._build_minimap()
        self.hide()

    # ------------------------------------------------------------- mini-map
    def _build_minimap(self):
        t = self.track
        xs, ys = t.px, t.py
        self.min_x, self.max_x, self.min_y, self.max_y = min(xs), max(xs), min(ys), max(ys)
        extent = max(self.max_x - self.min_x, self.max_y - self.min_y)
        self.map_scale = MAP_SIZE / extent
        self.map_cx = (self.min_x + self.max_x) / 2.0
        self.map_cy = (self.min_y + self.max_y) / 2.0
        self.map_np = self.app.a2dBottomLeft.attachNewNode("minimap")
        half_w = (self.max_x - self.min_x) * self.map_scale / 2.0
        half_h = (self.max_y - self.min_y) * self.map_scale / 2.0
        self.map_np.setPos(0.08 + half_w + 0.03, 0, 0.08 + half_h + 0.03)
        bg = CardMaker("map-bg")
        bg.setFrame(-half_w - 0.03, half_w + 0.03, -half_h - 0.03, half_h + 0.03)
        bg_np = self.map_np.attachNewNode(bg.generate())
        bg_np.setColor(0.02, 0.03, 0.06, 0.55)
        bg_np.setTransparency(TransparencyAttrib.MAlpha)
        ls = LineSegs("map-line")
        ls.setThickness(3.0)
        ls.setColor(0.85, 0.88, 0.95, 1)
        for i in range(0, t.n + 1, 2):
            j = i % t.n
            x, z = self._to_map(t.px[j], t.py[j])
            if i == 0:
                ls.moveTo(x, 0, z)
            else:
                ls.drawTo(x, 0, z)
        x0, z0 = self._to_map(t.px[0], t.py[0])
        ls.drawTo(x0, 0, z0)
        self.map_np.attachNewNode(ls.create())
        self.dots = {}
        for car in self.race.cars:
            size = 0.017 if car.is_player else 0.012
            cm = CardMaker("dot")
            cm.setFrame(-size, size, -size, size)
            dot = self.map_np.attachNewNode(cm.generate())
            dot.setColor(*car.color, 1)
            self.dots[car] = dot
        # the player's dot is drawn last so it stays on top
        self.dots[self.race.player].reparentTo(self.map_np)

    def _to_map(self, x, y):
        return (x - self.map_cx) * self.map_scale, (y - self.map_cy) * self.map_scale

    # ----------------------------------------------------------- visibility
    def show(self):
        self.root.show()
        self.panel_np.show()
        self.speed_panel.show()
        self.map_np.show()
        self.cam_text.show()
        self.reset()

    def hide(self):
        self.root.hide()
        self.panel_np.hide()
        self.speed_panel.hide()
        self.map_np.hide()
        self.message_text.hide()
        self.cam_text.hide()
        self.hint_text.hide()

    def destroy(self):
        self.root.removeNode()
        self.panel_np.removeNode()
        self.speed_panel.removeNode()
        self.map_np.removeNode()
        for text in (self.message_text, self.wrong_text, self.hint_text, self.cam_text):
            text.destroy()

    def reset(self):
        self._cache.clear()
        self.speed_ratio = 0.0
        self.speed_text_value = 0
        self.speed_text.setText("000")
        self.countdown_text.setText("")
        self.message_text.setText("")
        self.message_sticky = False
        self.message_priority = 0
        self.countdown_t = 99.0
        self.message_t = 99.0
        self.wrong_text.hide()
        self.hint_text.hide()
        self.cam_text.setText("")

    # -------------------------------------------------------------- overlays
    def countdown(self, text, go=False):
        self.countdown_text.setText(text)
        self.countdown_t = 0.0
        self.countdown_go = go

    def message(self, text, seconds=1.6, colour=theme.TEXT, priority=0, sticky=False):
        """Short banner at the top of the screen. Higher priority messages are not overwritten."""
        if self.message_t < self.message_dur and priority < self.message_priority:
            return
        self.message_text.setText(text)
        self.message_text.setFg(colour)
        self.message_t = 0.0
        self.message_dur = seconds
        self.message_priority = priority
        self.message_sticky = sticky
        self.message_text.show()

    def flash_camera(self, text):
        self.cam_text.setText(text)
        self.cam_t = 0.0

    # ---------------------------------------------------------------- update
    def _set(self, key, text):
        if self._cache.get(key) != text:
            self._cache[key] = text
            self.lines[key].setText(text)

    def update(self, dt):
        race, player = self.race, self.race.player
        total = race.total_laps
        self._set("lap", "LAP: %d / %d" % (player.tracker.lap, total))
        self._set("pos", "POSITION: %d / %d" % (player.position, len(race.cars)))
        kmh = int(round(player.speed_kmh))
        if kmh != self.speed_text_value:
            self.speed_text_value = kmh
            self.speed_text.setText("%03d" % kmh)
        t = player.finish_time if player.finished else race.race_time
        self._set("time", "TIME: " + theme.format_time(t))
        target_ratio = min(1.0, max(0.0, player.speed_kmh / (player.body.spec.max_speed * 3.6)))
        self.speed_ratio += (target_ratio - self.speed_ratio) * min(1.0, dt * 8.0)
        active_segments = round(self.speed_ratio * len(self.speed_segments))
        for index, segment in enumerate(self.speed_segments):
            if index < active_segments:
                color = ((0.16, 0.78, 0.98, 1.0) if index < 14
                         else (1.0, 0.56, 0.16, 1.0) if index < 18
                         else (0.98, 0.20, 0.16, 1.0))
            else:
                color = (0.20, 0.25, 0.30, 0.60)
            segment["frameColor"] = color

        # countdown animation
        if self.countdown_t < 1.2:
            self.countdown_t += dt
            k = self.countdown_t
            pop = 1.0 + 0.5 * max(0.0, 1.0 - k * 4.0)
            limit = 0.55 if self.countdown_go else 0.8
            alpha = 1.0 if k < limit else max(0.0, 1.0 - (k - limit) * 4.0)
            colour = theme.GOLD if self.countdown_go else theme.TEXT
            self.countdown_text.setScale(0.36 * pop)
            self.countdown_text.setFg((colour[0], colour[1], colour[2], alpha))
            if alpha <= 0.0:
                self.countdown_text.setText("")
                self.countdown_t = 99.0

        # top banner
        if self.message_t < self.message_dur and not self.message_sticky:
            self.message_t += dt
            if self.message_t >= self.message_dur:
                self.message_text.setText("")
        elif self.message_t >= self.message_dur and not self.message_sticky:
            self.message_priority = 0

        # camera label
        if self.cam_t < 1.5:
            self.cam_t += dt
            if self.cam_t >= 1.5:
                self.cam_text.setText("")

        # warnings
        racing = race.state == "racing"
        if racing and player.wrong_way:
            if int(race.race_time * 3) % 2 == 0:
                self.wrong_text.show()
            else:
                self.wrong_text.hide()
        else:
            self.wrong_text.hide()
        if racing and player.stuck:
            self.hint_text.show()
        else:
            self.hint_text.hide()

        # mini-map dots
        for car, dot in self.dots.items():
            x, z = self._to_map(car.body.x, car.body.y)
            dot.setPos(x, 0, z)
