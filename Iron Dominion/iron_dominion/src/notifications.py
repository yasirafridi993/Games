"""Toast notifications: short, self-dismissing messages for the player.

Notifications are drawn centred near the bottom of the screen and fade out
after a fixed lifetime. Older toasts are pushed up by newer ones.
"""

import pygame

from . import config as C


_NOTIFICATION_LIFETIME = 3.2
_NOTIFICATION_FADE = 0.6


class Toast:
    __slots__ = ("text", "color", "ttl", "total")

    def __init__(self, text, color, lifetime=_NOTIFICATION_LIFETIME):
        self.text = text
        self.color = color
        self.ttl = lifetime
        self.total = lifetime


class NotificationCenter:
    def __init__(self):
        self.toasts = []
        self._font = pygame.font.SysFont(
            "consolas,couriernew,monospace", 16, bold=True)
        self._shadow = pygame.font.SysFont(
            "consolas,couriernew,monospace", 16, bold=True)
        self._pad = 10

    # ------------------------------------------------------------------
    def info(self, text):
        self._add(text, C.UI_TEXT_COL)

    def warn(self, text):
        self._add(text, C.OBJECTIVE_PENDING_COL)

    def error(self, text):
        self._add(text, C.GAME_OVER_DEFEAT_COL)

    def success(self, text):
        self._add(text, C.OBJECTIVE_DONE_COL)

    def _add(self, text, color):
        self.toasts.append(Toast(text, color))
        if len(self.toasts) > 5:
            self.toasts.pop(0)

    # ------------------------------------------------------------------
    def update(self, dt):
        alive = []
        for t in self.toasts:
            t.ttl -= dt
            if t.ttl > 0:
                alive.append(t)
        self.toasts = alive

    # ------------------------------------------------------------------
    def clear(self):
        self.toasts.clear()

    # ------------------------------------------------------------------
    def draw(self, surface):
        if not self.toasts:
            return
        sw, sh = surface.get_size()
        base_y = sh - 110
        line_h = 26

        for i, t in enumerate(reversed(self.toasts)):
            alpha = 255
            if t.ttl < _NOTIFICATION_FADE:
                alpha = int(255 * (t.ttl / _NOTIFICATION_FADE))
            alpha = max(0, min(255, alpha))

            shadow = self._shadow.render(t.text, True, (0, 0, 0))
            main = self._font.render(t.text, True, t.color)
            text_w = main.get_width()
            text_h = main.get_height()

            pad = self._pad
            w = text_w + pad * 2
            h = text_h + pad // 2

            x = (sw - w) // 2
            y = base_y - i * line_h

            panel = pygame.Surface((w, h), pygame.SRCALPHA)
            panel.fill((10, 12, 18, int(190 * alpha / 255)))
            pygame.draw.rect(panel, (*C.UI_PANEL_BORDER, alpha),
                             panel.get_rect(), 1)

            shadow.set_alpha(alpha)
            main.set_alpha(alpha)
            panel.blit(shadow, (pad + 1, pad // 4 + 1))
            panel.blit(main, (pad, pad // 4))

            surface.blit(panel, (x, y - h))