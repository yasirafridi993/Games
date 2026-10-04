"""Pause menu."""
from . import theme


class PauseMenu(theme.Screen):
    def __init__(self, app, on_resume, on_restart, on_settings, on_menu):
        super().__init__(app, 0.50, (1.0, 1.25))
        p = self.panel
        theme.label(p, "PAUSED", (0, 0.43), scale=0.13, fg=theme.TEXT)
        theme.button(p, "RESUME", on_resume, (0, 0, 0.22))
        theme.button(p, "RESTART", on_restart, (0, 0, 0.04))
        theme.button(p, "SETTINGS", on_settings, (0, 0, -0.14))
        theme.button(p, "MAIN MENU", on_menu, (0, 0, -0.32))
        theme.label(p, "ESC to resume", (0, -0.51), scale=0.04, fg=theme.MUTED)
