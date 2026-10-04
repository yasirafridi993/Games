"""Car Racing - a 3D arcade racing game made with Python + Panda3D.

Start the game with:   python main.py
"""
import math
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from panda3d.core import loadPrcFileData
except ImportError:
    print("Panda3D is not installed.\nInstall it with:   pip install -r requirements.txt")
    sys.exit(1)

# Must be set before ShowBase creates the window.
loadPrcFileData("", """
window-title Car Racing
win-size 1280 720
sync-video 1
framebuffer-multisample 1
multisamples 4
audio-library-name p3openal_audio
""")

from direct.gui.OnscreenText import OnscreenText                       # noqa: E402
from direct.showbase.ShowBase import ShowBase                          # noqa: E402
from panda3d.core import (ButtonHandle, ButtonRegistry, ClockObject,   # noqa: E402
                          KeyboardButton, TextNode, WindowProperties)

from audio.audio_manager import AudioManager                           # noqa: E402
from game.camera import ChaseCamera                                    # noqa: E402
from game.car_model import CarModel                                    # noqa: E402
from game.cars import car_definition                                    # noqa: E402
from game.config import DATA_DIR                                       # noqa: E402
from game.effects import VisualEffects                                 # noqa: E402
from game.progression import ProgressionStore                          # noqa: E402
from game.race import Race                                             # noqa: E402
from game.race_setup import RaceSetup                                  # noqa: E402
from game.settings import Settings                                     # noqa: E402
from game.tracks import TRACK_BY_ID, build_track                       # noqa: E402
from game.world import HORIZON, World                                  # noqa: E402
from ui import theme                                                   # noqa: E402
from ui.hud import HUD                                                 # noqa: E402
from ui.car_selection import CarSelectionScreen                       # noqa: E402
from ui.menu import MainMenu, SettingsMenu                             # noqa: E402
from ui.pause import PauseMenu                                         # noqa: E402
from ui.race_setup import RaceSetupScreen                              # noqa: E402
from ui.results import ResultsScreen                                   # noqa: E402
from ui.track_selection import TrackSelectionScreen                    # noqa: E402

RESULTS_DELAY = 3.0          # seconds between crossing the line and the results screen
MENU_ORBIT_RADIUS = 26.0


def _key(name):
    """ButtonHandle for a keyboard key name such as "w".

    Tries the dedicated keyboard helper first (str, then bytes - Panda versions differ),
    then the button registry, and ignores any answer that is the empty handle.
    """
    attempts = (lambda: KeyboardButton.asciiKey(name),
                lambda: KeyboardButton.asciiKey(name.encode("ascii")),
                lambda: ButtonRegistry.ptr().getButton(name))
    for attempt in attempts:
        try:
            handle = attempt()
            if handle is not None and handle != ButtonHandle.none():
                return handle
        except Exception:
            continue
    return ButtonRegistry.ptr().getButton(name)


class CarRacingApp(ShowBase):
    def __init__(self):
        super().__init__()
        self.disableMouse()
        self.setBackgroundColor(*HORIZON)
        self.camLens.setNearFar(1.0, 2500)
        self.camLens.setFov(60)

        theme.init_font(self.loader)
        loading = OnscreenText(text="LOADING...", pos=(0, 0), scale=0.12, fg=(1, 1, 1, 1),
                               font=theme.font(), shadow=(0, 0, 0, 0.8))
        self.graphicsEngine.renderFrame()
        self.graphicsEngine.renderFrame()

        self.settings = Settings()
        self.race_setup = RaceSetup()
        self.race_setup.validate(TRACK_BY_ID)
        self.progression = ProgressionStore()
        self.track = build_track(self.race_setup.track_id)
        self.race = Race(self.track, self.race_setup.total_laps,
                         self.race_setup.opponent_count, self.race_setup.difficulty,
                         self.race_setup.car_id)
        self.world = World(self.render, self.loader, self.track, self.settings.quality,
                           self.settings.weather, len(self.race.cars))
        self.setBackgroundColor(*self.world.horizon)
        self.models = {}
        self._create_car_models()
        self.effects = VisualEffects(
            self.render, self.settings.quality, weather=self.settings.weather)
        self.chase = ChaseCamera(self.camera, self.camLens)
        self.audio = AudioManager(self.loader, self.settings)

        # UI (created in draw order: HUD first, overlays on top)
        self.hud = HUD(self, self.race, self.track)
        self.main_menu = MainMenu(self, self.open_race_setup, self.open_settings, self.userExit)
        self.race_setup_screen = RaceSetupScreen(
            self, self.race_setup, self.start_race, self.open_track_selection)
        self.car_selection_screen = CarSelectionScreen(
            self, self.race_setup, self.open_track_selection, self.close_race_setup)
        self.track_selection_screen = TrackSelectionScreen(
            self, self.race_setup, self.progression, self.open_race_options, self.back_to_garage)
        self.settings_menu = SettingsMenu(self, self.settings, self.apply_settings, self.close_settings)
        self.pause_menu = PauseMenu(self, self.resume, self.start_race, self.open_settings, self.to_main_menu)
        self.results = ResultsScreen(self, self.start_race, self.open_race_setup, self.to_main_menu)
        loading.destroy()

        self.keys = {name: _key(name) for name in ("w", "a", "s", "d")}
        self.fps_visible = False
        self.accept("escape", self.on_escape)
        self.accept("r", self.on_reset_car)
        self.accept("c", self.on_cycle_camera)
        self.accept("f3", self.toggle_fps)
        self.accept("f11", self.toggle_fullscreen)

        self.state = "menu"
        self.orbit_angle = 0.6
        self.results_timer = None
        self._settings_return_state = None
        self.apply_settings()
        self.audio.start_music()
        self.enter_menu()
        self.taskMgr.add(self.update, "update")

    # ------------------------------------------------------------ helpers
    def _create_car_models(self):
        for car in self.race.cars:
            model = CarModel(self.render, car.color, car_definition(car.car_id))
            if not car.is_player:
                self._add_name_tag(model, car.name)
            self.models[car] = model

    @staticmethod
    def _add_name_tag(model, name):
        tag = TextNode("tag")
        tag.setText(name)
        tag.setAlign(TextNode.ACenter)
        tag.setTextColor(1, 1, 1, 1)
        tag.setShadow(0.05, 0.05)
        tag.setShadowColor(0, 0, 0, 1)
        node = model.root.attachNewNode(tag)
        node.setPos(0, 0, 2.9)
        node.setScale(0.9)
        node.setBillboardPointEye()
        node.setLightOff()

    def apply_settings(self):
        """Apply audio, quality, and weather settings without touching race rules."""
        self.audio.set_volumes(self.settings.music_volume, self.settings.sfx_volume)
        self.audio.set_weather(self.settings.weather)
        if (self.world.quality != self.settings.quality
                or self.world.requested_weather != self.settings.weather):
            self.world.destroy()
            self.world = World(
                self.render, self.loader, self.track, self.settings.quality,
                self.settings.weather, len(self.race.cars))
            self.setBackgroundColor(*self.world.horizon)
        else:
            self.world.apply_quality(self.settings.quality, self.settings.weather)
        if self.effects.quality != self.settings.quality:
            self.effects.destroy()
            self.effects = VisualEffects(
                self.render, self.settings.quality, weather=self.settings.weather)
        else:
            self.effects.set_weather(self.settings.weather)
        for model in self.models.values():
            model.set_blob(not self.world.shadows_enabled)

    def toggle_fps(self):
        self.fps_visible = not self.fps_visible
        self.setFrameRateMeter(self.fps_visible)

    def toggle_fullscreen(self):
        props = WindowProperties()
        full = self.win.getProperties().getFullscreen()
        if full:
            props.setFullscreen(False)
            props.setSize(1280, 720)
        else:
            pipe = self.pipe
            props.setSize(pipe.getDisplayWidth(), pipe.getDisplayHeight())
            props.setFullscreen(True)
        self.win.requestProperties(props)

    # ------------------------------------------------------- state changes
    def enter_menu(self):
        self.state = "menu"
        self.results_timer = None
        self.audio.stop_loops()
        self.race.reset()
        self.hud.hide()
        self.race_setup_screen.hide()
        self.car_selection_screen.hide()
        self.track_selection_screen.hide()
        self.pause_menu.hide()
        self.results.hide()
        self.settings_menu.hide()
        self.main_menu.show()
        self.camLens.setFov(55)

    def to_main_menu(self):
        self.enter_menu()

    def open_race_setup(self):
        self.state = "garage"
        self.main_menu.hide()
        self.settings_menu.hide()
        self.pause_menu.hide()
        self.results.hide()
        self.car_selection_screen.show()

    def close_race_setup(self):
        self.car_selection_screen.hide()
        self.track_selection_screen.hide()
        self.race_setup_screen.hide()
        self.main_menu.show()
        self.state = "menu"

    def open_track_selection(self):
        self.car_selection_screen.hide()
        self.race_setup_screen.hide()
        self.track_selection_screen.show()
        self.state = "track_select"

    def open_race_options(self):
        self.track_selection_screen.hide()
        self.race_setup_screen.show()
        self.state = "setup"

    def back_to_garage(self):
        self.track_selection_screen.hide()
        self.car_selection_screen.show()
        self.state = "garage"

    def open_settings(self):
        self._settings_return_state = self.state
        if self.state == "menu":
            self.main_menu.hide()
        elif self.state == "paused":
            self.pause_menu.hide()
        self.state = "settings"
        self.settings_menu.show()

    def close_settings(self):
        self.settings_menu.hide()
        self.car_selection_screen.hide()
        self.track_selection_screen.hide()
        return_state = self._settings_return_state
        self._settings_return_state = None
        if return_state == "paused":
            self.pause_menu.show()
            self.state = "paused"
        else:
            self.main_menu.show()
            self.state = "menu"

    def start_race(self):
        self.race_setup.validate(TRACK_BY_ID)
        self.main_menu.hide()
        self.race_setup_screen.hide()
        self.pause_menu.hide()
        self.results.hide()
        self.settings_menu.hide()
        if self.track.track_id != self.race_setup.track_id:
            self.track = build_track(self.race_setup.track_id)
        self.hud.destroy()
        for model in self.models.values():
            model.destroy()
        self.effects.destroy()
        self.race = Race(self.track, self.race_setup.total_laps,
                         self.race_setup.opponent_count, self.race_setup.difficulty,
                         self.race_setup.car_id)
        if (self.world.track is not self.track or self.world.grid_size != len(self.race.cars)
                or self.world.quality != self.settings.quality
                or self.world.requested_weather != self.settings.weather):
            self.world.destroy()
            self.world = World(
                self.render, self.loader, self.track, self.settings.quality,
                self.settings.weather, len(self.race.cars))
            self.setBackgroundColor(*self.world.horizon)
        self.models = {}
        self._create_car_models()
        self.effects = VisualEffects(
            self.render, self.settings.quality, weather=self.settings.weather)
        self.hud = HUD(self, self.race, self.track)
        self.chase = ChaseCamera(self.camera, self.camLens)
        self.apply_settings()
        self.race.start()
        self.results_timer = None
        player = self.race.player
        x, y, h = player.pose(1.0)
        self.chase.reset(x, y, h, self.track.height_at(player.proj.s), snap=False)
        self.hud.show()
        self.audio.start_loops()
        self.state = "playing"

    def pause(self):
        self.state = "paused"
        self.audio.stop_loops()
        self.pause_menu.show()

    def resume(self):
        self.pause_menu.hide()
        self.audio.start_loops()
        self.state = "playing"

    def show_results(self):
        race, player = self.race, self.race.player
        order = sorted(race.cars, key=lambda c: (not c.finished, c.finish_order if c.finished else c.position))
        standings = []
        for place, car in enumerate(order, start=1):
            t = theme.format_time(car.finish_time) if car.finished else None
            standings.append((place, car.name, t, car.is_player))
        record = self.progression.track_record(self.track.track_id)
        self.results.set_result(
            player.position, len(race.cars), theme.format_time(player.finish_time), standings,
            self.race_setup, self.track.name, player.lap_times,
            record.get("best_time"), record.get("best_lap"))
        self.audio.stop_loops()
        self.hud.hide()
        self.results.show()
        self.state = "results"

    # -------------------------------------------------------------- input
    def on_escape(self):
        if self.state == "playing":
            self.pause()
        elif self.state == "paused":
            self.resume()
        elif self.state == "settings":
            self.settings.save()
            self.close_settings()
        elif self.state == "setup":
            self.open_track_selection()
        elif self.state == "track_select":
            self.back_to_garage()
        elif self.state == "garage":
            self.close_race_setup()

    def on_reset_car(self):
        if self.state == "playing" and self.race.state == "racing":
            self.race.reset_player()
            x, y, h = self.race.player.pose(1.0)
            self.chase.reset(x, y, h)
            self.hud.message("CAR RESET", 1.0, theme.MUTED, priority=1)

    def on_cycle_camera(self):
        if self.state in ("playing", "paused", "results"):
            self.hud.flash_camera(self.chase.cycle_preset())

    def read_input(self):
        down = self.mouseWatcherNode.isButtonDown
        k = self.keys
        c = self.race.player.controls
        c.throttle = 1.0 if (down(k["w"]) or down(KeyboardButton.up())) else 0.0
        c.brake = 1.0 if (down(k["s"]) or down(KeyboardButton.down())) else 0.0
        left = down(k["a"]) or down(KeyboardButton.left())
        right = down(k["d"]) or down(KeyboardButton.right())
        c.steer = (1.0 if left else 0.0) - (1.0 if right else 0.0)
        c.handbrake = bool(down(KeyboardButton.space()))

    # ---------------------------------------------------------- game loop
    def update(self, task):
        dt = min(ClockObject.getGlobalClock().getDt(), 0.1)
        if self.state in ("menu", "setup", "garage", "track_select") or (
                self.state == "settings" and self._settings_return_state != "paused"):
            self.orbit_camera(dt)
            self.sync_models(dt)
            if self.state == "garage":
                self.car_selection_screen.update(dt)
        elif self.state == "settings":
            self.world.update(self.camera.getPos().getXy(), self.camera.getPos(), dt)
        elif self.state in ("playing", "results"):
            self.play(dt)
        elif self.state == "paused":
            self.world.update(self.camera.getPos().getXy(), self.camera.getPos(), dt)
        return task.cont

    def orbit_camera(self, dt):
        self.orbit_angle += dt * 0.2
        s = self.track.length - 18.0
        cx, cy, _ = self.track.point_at(s, 0.0)
        elevation = self.track.height_at(s)
        a = self.orbit_angle
        pos = (cx + math.cos(a) * MENU_ORBIT_RADIUS, cy + math.sin(a) * MENU_ORBIT_RADIUS,
               elevation + 6.5 + 1.5 * math.sin(a * 0.7))
        self.camera.setPos(*pos)
        self.camera.lookAt(cx, cy, elevation + 1.0)
        self.world.update((cx, cy), self.camera.getPos(), dt)

    def play(self, dt):
        race, player = self.race, self.race.player
        if race.state == "racing" and player.driver is None and self.state == "playing":
            self.read_input()
        race.update(dt)
        self.handle_events(race.pop_events())
        self.sync_models(dt)

        x, y, h = player.pose(race.alpha)
        self.chase.update(dt, x, y, h, player.body.vf, player.body.long_accel,
                          self.track.height_at(player.proj.s))
        self.world.update((x, y), self.camera.getPos(), dt)
        self.effects.update(self.race.cars, self.track, dt)

        if self.state == "playing":
            self.update_audio(dt)
            self.hud.update(dt)
            if self.results_timer is not None:
                self.results_timer -= dt
                if self.results_timer <= 0.0:
                    self.results_timer = None
                    self.show_results()

    def sync_models(self, dt):
        alpha = self.race.alpha
        for car, model in self.models.items():
            x, y, h = car.pose(alpha)
            c = car.controls
            braking = c.brake > 0.05 and car.body.vf > 0.5
            elevation = self.track.height_at(car.proj.s) if car.proj else 0.0
            model.update(x, y, h, car.body, braking, dt, elevation)

    def update_audio(self, dt):
        player = self.race.player
        body, c = player.body, player.controls
        ratio = abs(body.vf) / body.spec.max_speed
        self.audio.update_engine(ratio, c.throttle, dt, player.car_id)
        skid = max(0.0, (abs(body.vr) - 3.0) / 10.0)
        if c.brake > 0.05 and body.vf > 12.0:
            skid = max(skid, 0.45)
        if c.handbrake and abs(body.vf) > 8.0:
            skid = max(skid, 0.8)
        self.audio.update_tire(skid)

    def handle_events(self, events):
        race, player = self.race, self.race.player
        for ev in events:
            kind = ev[0]
            if kind == "countdown":
                self.hud.countdown(str(ev[1]))
                self.audio.play("beep")
            elif kind == "go":
                self.hud.countdown("GO!", go=True)
                self.audio.play("go")
            elif kind == "lap" and ev[1] is player:
                lap = ev[2]
                if lap == race.total_laps:
                    self.hud.message("FINAL LAP", 2.2, theme.GOLD, priority=2)
                else:
                    self.hud.message("LAP %d / %d" % (lap, race.total_laps), 2.0, theme.TEXT, priority=2)
            elif kind == "checkpoint" and ev[1] is player:
                self.hud.message("CHECKPOINT", 0.7, theme.MUTED, priority=0)
            elif kind == "finish" and ev[1] is player:
                self.audio.play("finish")
                self.hud.message("FINISHED!   P%d" % ev[2], RESULTS_DELAY, theme.GOLD, priority=3, sticky=True)
            elif kind == "race_complete":
                best_lap = min(player.lap_times) if player.lap_times else None
                winner = min(race.cars, key=lambda car: car.finish_order)
                self.progression.record_race(
                    self.track.track_id, player.finish_time, best_lap, winner is player)
                self.hud.message("RACE COMPLETE", RESULTS_DELAY, theme.GOLD, priority=3, sticky=True)
                self.results_timer = RESULTS_DELAY
            elif kind == "wall_hit" and ev[1] is player:
                self.audio.play_crash(ev[2])
                self.chase.add_shake(ev[2])
                elevation = self.track.height_at(player.proj.s) if player.proj else 0.0
                self.effects.emit_sparks(player.body.x, player.body.y, elevation + 0.1, ev[2])
            elif kind == "car_hit" and (ev[1] is player or ev[2] is player):
                self.audio.play_crash(ev[3])
                self.chase.add_shake(ev[3])
                elevation = self.track.height_at(player.proj.s) if player.proj else 0.0
                self.effects.emit_sparks(player.body.x, player.body.y, elevation + 0.1, ev[3])


def log_crash():
    """Write the traceback next to settings.json so players can report problems."""
    text = traceback.format_exc()
    print(text, file=sys.stderr)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "error.log").write_text(text, encoding="utf-8")
        print("A copy of this error was saved to", DATA_DIR / "error.log", file=sys.stderr)
    except OSError:
        pass


def main():
    try:
        app = CarRacingApp()
        app.run()
    except KeyboardInterrupt:
        pass
    except SystemExit:
        raise
    except Exception:
        log_crash()
        sys.exit(1)


if __name__ == "__main__":
    main()
