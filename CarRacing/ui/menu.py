"""Main menu and settings screen."""
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame, DirectSlider
from panda3d.core import TextNode

from game.graphics import WEATHER_LEVELS
from game.settings import QUALITY_LEVELS

from . import theme


class MainMenu:
    """Title screen drawn on top of the 3D scene (the camera orbits the starting grid)."""

    def __init__(self, app, on_start, on_settings, on_exit):
        self.root = DirectFrame(parent=app.aspect2d, frameColor=(0, 0, 0, 0), frameSize=(-4, 4, -2, 2),
                                state=DGG.NORMAL)
        panel = DirectFrame(parent=self.root, frameColor=(0.03, 0.04, 0.08, 0.62),
                            frameSize=(-0.62, 0.62, -0.55, 0.80), pos=(0, 0, 0))
        DirectFrame(parent=panel, frameColor=theme.ACCENT, frameSize=(-0.62, 0.62, 0.788, 0.80))
        theme.label(panel, "CAR", (0, 0.50), scale=0.20, fg=theme.TEXT)
        theme.label(panel, "RACING", (0, 0.33), scale=0.20, fg=theme.ACCENT)
        theme.button(panel, "RACE SETUP", on_start, (0, 0, 0.08))
        theme.button(panel, "SETTINGS", on_settings, (0, 0, -0.10))
        theme.button(panel, "EXIT", on_exit, (0, 0, -0.28))
        theme.label(panel, "Choose your track and race settings", (0, -0.46), scale=0.045, fg=theme.MUTED)
        theme.label(self.root,
                    "W accelerate    S brake / reverse    A D steer    SPACE handbrake    "
                    "R reset car    C camera    ESC pause",
                    (0, -0.92), scale=0.042, fg=theme.MUTED)
        self.root.hide()

    @property
    def visible(self):
        return not self.root.isHidden()

    def show(self):
        self.root.show()

    def hide(self):
        self.root.hide()


class SettingsMenu(theme.Screen):
    def __init__(self, app, settings, on_change, on_back):
        super().__init__(app, 0.62, (1.9, 1.55))
        self.settings = settings
        self.on_change = on_change
        self.on_back = on_back
        self._ready = False
        p = self.panel
        theme.label(p, "GRAPHICS & AUDIO", (0, 0.61), scale=0.09, fg=theme.TEXT)

        self.music_slider, self.music_value = self._slider_row(
            "MUSIC VOLUME", 0.36, settings.music_volume, self._music_changed)
        self.sfx_slider, self.sfx_value = self._slider_row(
            "SOUND EFFECTS", 0.12, settings.sfx_volume, self._sfx_changed)

        theme.label(p, "GRAPHICS QUALITY", (-0.78, -0.12), scale=0.05, fg=theme.MUTED,
                    align=TextNode.ALeft)
        self.quality_button = theme.button(p, "", self._cycle_quality, (0.38, 0, -0.10),
                                           width=0.72, height=0.10, text_scale=0.05)
        theme.label(p, "VISUAL PRESET", (-0.78, -0.36), scale=0.05, fg=theme.MUTED,
                    align=TextNode.ALeft)
        self.weather_button = theme.button(p, "", self._cycle_weather, (0.38, 0, -0.34),
                                           width=0.72, height=0.10, text_scale=0.05)
        self.quality_description = theme.label(
            p, "Low: lean  |  Medium: balanced  |  High: sharper shadows and detail\n"
               "Weather presets are visual only; rain does not change grip.",
            (0, -0.54), scale=0.033, fg=theme.MUTED)
        theme.button(p, "BACK", self._back, (0, 0, -0.68), width=0.6, height=0.11)
        self._refresh()
        self._ready = True

    def _slider_row(self, title, z, value, command):
        p = self.panel
        theme.label(p, title, (-0.62, z + 0.025), scale=0.05, fg=theme.MUTED, align=TextNode.ALeft)
        slider = DirectSlider(parent=p, range=(0.0, 1.0), value=value, pageSize=0.1, command=command,
                              pos=(0.20, 0, z + 0.04), frameSize=(-0.34, 0.34, -0.012, 0.012),
                              frameColor=(0.25, 0.28, 0.36, 1), relief=DGG.FLAT,
                              thumb_relief=DGG.FLAT, thumb_frameColor=theme.ACCENT,
                              thumb_frameSize=(-0.02, 0.02, -0.045, 0.045))
        text = theme.label(p, "", (0.64, z + 0.02), scale=0.05, fg=theme.TEXT, align=TextNode.ARight,
                           may_change=True)
        return slider, text

    def _refresh(self):
        s = self.settings
        self.music_value.setText("%d%%" % round(s.music_volume * 100))
        self.sfx_value.setText("%d%%" % round(s.sfx_volume * 100))
        self.quality_button["text"] = s.quality.upper()
        self.weather_button["text"] = s.weather.upper()

    def _music_changed(self):
        if self._ready:
            self.settings.music_volume = round(float(self.music_slider["value"]), 2)
            self._changed()

    def _sfx_changed(self):
        if self._ready:
            self.settings.sfx_volume = round(float(self.sfx_slider["value"]), 2)
            self._changed()

    def _cycle_quality(self):
        i = QUALITY_LEVELS.index(self.settings.quality) if self.settings.quality in QUALITY_LEVELS else 1
        self.settings.quality = QUALITY_LEVELS[(i + 1) % len(QUALITY_LEVELS)]
        self._changed()

    def _cycle_weather(self):
        i = WEATHER_LEVELS.index(self.settings.weather) if self.settings.weather in WEATHER_LEVELS else 0
        self.settings.weather = WEATHER_LEVELS[(i + 1) % len(WEATHER_LEVELS)]
        self._changed()

    def _changed(self):
        self._refresh()
        self.on_change()

    def _back(self):
        self.settings.save()
        self.on_back()
