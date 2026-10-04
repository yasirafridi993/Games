"""Load / save user settings (data/settings.json)."""
import json

from .config import DATA_DIR, SETTINGS_FILE
from .graphics import WEATHER_LEVELS

DEFAULTS = {"music_volume": 0.5, "sfx_volume": 0.8, "quality": "medium", "weather": "day"}
QUALITY_LEVELS = ("low", "medium", "high")


class Settings:
    def __init__(self, path=SETTINGS_FILE):
        self.path = path
        self.music_volume = DEFAULTS["music_volume"]
        self.sfx_volume = DEFAULTS["sfx_volume"]
        self.quality = DEFAULTS["quality"]
        self.weather = DEFAULTS["weather"]
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.music_volume = min(1.0, max(0.0, float(data.get("music_volume", self.music_volume))))
            self.sfx_volume = min(1.0, max(0.0, float(data.get("sfx_volume", self.sfx_volume))))
            quality = data.get("quality", self.quality)
            self.quality = quality if quality in QUALITY_LEVELS else DEFAULTS["quality"]
            weather = data.get("weather", self.weather)
            self.weather = weather if weather in WEATHER_LEVELS else DEFAULTS["weather"]
        except (OSError, ValueError, TypeError, AttributeError):
            pass  # missing or corrupt file: keep defaults

    def save(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"music_volume": round(self.music_volume, 2),
                           "sfx_volume": round(self.sfx_volume, 2),
                           "quality": self.quality,
                           "weather": self.weather}, f, indent=2)
        except OSError as exc:
            print("Could not save settings:", exc)
