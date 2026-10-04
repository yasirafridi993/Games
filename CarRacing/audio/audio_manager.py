"""Sound effects, engine sound and music using Panda3D's audio system."""
import time

from panda3d.core import Filename

from game.config import SOUNDS_DIR

from .sound_gen import EXTENSIONS, ensure_sounds

SFX_NAMES = ("engine", "tire", "rain", "crash", "beep", "go", "finish")


class AudioManager:
    def __init__(self, loader, settings, status=None):
        self.loader = loader
        self.music_volume = settings.music_volume
        self.sfx_volume = settings.sfx_volume
        self.engine_rate = 0.8
        self._last_crash = 0.0
        self._loops_on = False
        self.weather = "day"
        ensure_sounds(SOUNDS_DIR, status)
        self.sfx = {name: self._load(name, music=False) for name in SFX_NAMES}
        self.music = self._load("music", music=True)
        for name in ("engine", "tire"):
            if self.sfx[name]:
                self.sfx[name].setLoop(True)
                self.sfx[name].setVolume(0.0)
        if self.music:
            self.music.setLoop(True)
        self.set_volumes(self.music_volume, self.sfx_volume)

    def _load(self, name, music):
        for ext in EXTENSIONS:
            path = SOUNDS_DIR / (name + ext)
            if not path.is_file():
                continue
            try:
                fn = Filename.fromOsSpecific(str(path))
                snd = self.loader.loadMusic(fn) if music else self.loader.loadSfx(fn)
                if snd is not None:
                    return snd
            except Exception as exc:
                print("Could not load sound %s: %s" % (path.name, exc))
        return None

    # ---------------------------------------------------------------- volume
    def set_volumes(self, music, sfx):
        self.music_volume, self.sfx_volume = music, sfx
        if self.music:
            self.music.setVolume(music)
        for name in ("beep", "go", "finish", "crash"):
            if self.sfx.get(name):
                self.sfx[name].setVolume(sfx)
        self._update_rain()

    # ----------------------------------------------------------------- music
    def start_music(self):
        if self.music and self.music.status() != self.music.PLAYING:
            self.music.play()

    # ------------------------------------------------------------------ loops
    def start_loops(self):
        self._loops_on = True
        for name in ("engine", "tire"):
            snd = self.sfx.get(name)
            if snd and snd.status() != snd.PLAYING:
                snd.play()
        self._update_rain()

    def stop_loops(self):
        self._loops_on = False
        for name in ("engine", "tire"):
            snd = self.sfx.get(name)
            if snd:
                snd.setVolume(0.0)
                snd.stop()
        self._update_rain()

    def set_weather(self, weather):
        self.weather = weather
        self._update_rain()

    def _update_rain(self):
        snd = self.sfx.get("rain")
        if not snd:
            return
        if self._loops_on and self.weather == "rain":
            snd.setVolume(self.sfx_volume * 0.22)
            if snd.status() != snd.PLAYING:
                snd.play()
        else:
            snd.setVolume(0.0)
            snd.stop()

    def update_engine(self, speed_ratio, throttle, dt, car_id="balanced"):
        snd = self.sfx.get("engine")
        if not snd or not self._loops_on:
            return
        r = max(0.0, min(1.0, speed_ratio))
        pitch = {
            "balanced": 1.0,
            "sports": 1.06,
            "supercar": 1.14,
            "muscle": 0.90,
            "rally": 0.96,
            "lightweight": 1.08,
            "heavy_performance": 0.92,
        }.get(car_id, 1.0)
        target = (0.72 + 0.88 * r + 0.24 * max(0.0, min(1.0, throttle))) * pitch
        self.engine_rate += (target - self.engine_rate) * min(1.0, 5.5 * dt)
        snd.setPlayRate(max(0.65, min(1.9, self.engine_rate)))
        load = max(0.0, min(1.0, throttle))
        snd.setVolume(self.sfx_volume * (0.20 + 0.25 * load + 0.20 * r))

    def update_tire(self, intensity):
        snd = self.sfx.get("tire")
        if not snd or not self._loops_on:
            return
        intensity = max(0.0, min(1.0, intensity))
        snd.setVolume(self.sfx_volume * intensity * 0.6)
        snd.setPlayRate(0.9 + 0.2 * intensity)

    # ---------------------------------------------------------- one-shot sfx
    def play(self, name):
        snd = self.sfx.get(name)
        if snd:
            snd.setVolume(self.sfx_volume)
            snd.play()

    def play_crash(self, impact):
        now = time.time()
        snd = self.sfx.get("crash")
        if not snd or now - self._last_crash < 0.25:
            return
        self._last_crash = now
        snd.setVolume(self.sfx_volume * max(0.25, min(1.0, impact / 25.0)))
        snd.play()
