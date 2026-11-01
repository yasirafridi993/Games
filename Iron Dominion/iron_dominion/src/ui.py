"""Shared UI widgets: buttons, panels, and small helpers."""

import pygame

from . import config as C


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
class Fonts:
    _cache = {}

    @classmethod
    def get(cls, size, bold=False):
        key = (size, bold)
        f = cls._cache.get(key)
        if f is None:
            f = pygame.font.SysFont("consolas,couriernew,monospace",
                                    size, bold=bold)
            cls._cache[key] = f
        return f


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------
class Button:
    __slots__ = ("rect", "text", "font", "enabled",
                 "hover", "clicked_once", "data")

    def __init__(self, rect, text, font, enabled=True, data=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.enabled = enabled
        self.hover = False
        self.clicked_once = False
        self.data = data

    # ------------------------------------------------------------------
    def update(self, mouse_pos):
        self.hover = self.enabled and self.rect.collidepoint(mouse_pos)

    def handle_event(self, event):
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.clicked_once = True
                return False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.clicked_once and self.rect.collidepoint(event.pos):
                self.clicked_once = False
                return True
            self.clicked_once = False
        return False

    # ------------------------------------------------------------------
    def draw(self, surface):
        rect = self.rect
        if not self.enabled:
            bg = C.UI_BUTTON_BG_DISABLED
            border = C.UI_BUTTON_BORDER
            text_col = C.UI_BUTTON_TEXT_DISABLED
        elif self.hover or self.clicked_once:
            bg = C.UI_BUTTON_BG_HOVER
            border = C.UI_BUTTON_BORDER_HOVER
            text_col = C.UI_BUTTON_TEXT
        else:
            bg = C.UI_BUTTON_BG
            border = C.UI_BUTTON_BORDER
            text_col = C.UI_BUTTON_TEXT

        pygame.draw.rect(surface, bg, rect)
        pygame.draw.rect(surface, border, rect, 2)

        ts = self.font.render(self.text, True, text_col)
        tx = rect.x + (rect.width - ts.get_width()) // 2
        ty = rect.y + (rect.height - ts.get_height()) // 2
        surface.blit(ts, (tx, ty))


# ---------------------------------------------------------------------------
# Panels + text helpers
# ---------------------------------------------------------------------------
def draw_panel(surface, rect, bg=None, border=None, border_w=1):
    if bg is None:
        bg = C.UI_PANEL_BG
    if border is None:
        border = C.UI_PANEL_BORDER
    pygame.draw.rect(surface, bg, rect)
    if border_w > 0:
        pygame.draw.rect(surface, border, rect, border_w)


def draw_text(surface, text, font, pos, color=None, align="topleft"):
    if color is None:
        color = C.UI_TEXT_COL
    s = font.render(text, True, color)
    r = s.get_rect()
    setattr(r, align, pos)
    surface.blit(s, r)
    return r


def draw_shadowed_title(surface, text, font, center, color=None):
    if color is None:
        color = C.UI_TITLE_COL
    sh = font.render(text, True, (0, 0, 0))
    main = font.render(text, True, color)
    cx, cy = center
    rect = main.get_rect(center=(cx, cy))
    surface.blit(sh, (rect.x + 3, rect.y + 3))
    surface.blit(main, rect)


def draw_backdrop(surface, color=None):
    if color is None:
        color = C.UI_BG
    surface.fill(color)
    # Subtle vignette: a darker frame around the edges.
    w, h = surface.get_size()
    band = 40
    for i in range(band):
        alpha = int(60 * (1.0 - i / band))
        if alpha <= 0:
            continue
        col = (0, 0, 0, alpha)
        pygame.draw.rect(surface, col, (0, i, w, 1))
        pygame.draw.rect(surface, col, (0, h - 1 - i, w, 1))
        pygame.draw.rect(surface, col, (i, 0, 1, h))
        pygame.draw.rect(surface, col, (w - 1 - i, 0, 1, h))