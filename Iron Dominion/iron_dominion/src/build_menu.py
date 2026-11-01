"""Right-side build panel.

Positioned above the minimap so its buttons never collide with minimap clicks.
"""

import pygame

from . import config as C
from .building_defs import BUILDABLE_ORDER, BUILDING_DEFS
from .resources import RESOURCE_COLORS


class BuildMenu:
    def __init__(self, game):
        self.game = game
        self.font = pygame.font.SysFont("consolas,couriernew,monospace", 13)
        self.font_bold = pygame.font.SysFont(
            "consolas,couriernew,monospace", 14, bold=True)

        self.rects = {}
        self.hovered = None
        self._panel_rect = pygame.Rect(0, 0, 0, 0)

    # ------------------------------------------------------------------
    def layout(self, surface):
        sw = surface.get_width()
        sh = surface.get_height()
        width = C.BUILD_MENU_WIDTH
        row_h = C.BUILD_MENU_ROW_H
        pad = C.BUILD_MENU_PAD

        n = len(BUILDABLE_ORDER)
        total_h = n * (row_h + pad) + pad + 24

        x = sw - width - C.BUILD_MENU_MARGIN
        bottom_clearance = (C.MINIMAP_SIZE + C.MINIMAP_MARGIN + 8)
        y = sh - total_h - bottom_clearance
        y = max(60, y)

        self._panel_rect = pygame.Rect(x, y, width, total_h)

        ry = y + 28
        self.rects.clear()
        for kind in BUILDABLE_ORDER:
            r = pygame.Rect(x + pad, ry, width - pad * 2, row_h)
            self.rects[kind] = r
            ry += row_h + pad

    # ------------------------------------------------------------------
    def hit_test(self, pos):
        for kind, r in self.rects.items():
            if r.collidepoint(pos):
                return kind
        return None

    # ------------------------------------------------------------------
    def can_afford(self, kind):
        return self.game.stockpile.can_afford(BUILDING_DEFS[kind]["cost"])

    # ------------------------------------------------------------------
    def draw(self, surface):
        self.layout(surface)

        panel = self._panel_rect
        bg = pygame.Surface(panel.size, pygame.SRCALPHA)
        bg.fill((14, 18, 26, 210))
        pygame.draw.rect(bg, (92, 112, 142, 220), bg.get_rect(), 1)
        surface.blit(bg, panel.topleft)

        title = self.font_bold.render("BUILD", True, (206, 176, 96))
        surface.blit(title, (panel.x + 12, panel.y + 8))

        hovered = self.hovered
        for kind in BUILDABLE_ORDER:
            r = self.rects[kind]
            defn = BUILDING_DEFS[kind]
            affordable = self.can_afford(kind)

            row_bg = pygame.Surface(r.size, pygame.SRCALPHA)
            if kind == hovered:
                row_bg.fill((70, 96, 130, 220))
            else:
                row_bg.fill((28, 34, 46, 200))
            pygame.draw.rect(row_bg, (110, 130, 160, 220),
                             row_bg.get_rect(), 1)

            icon_col = (150, 140, 120) if affordable else (80, 80, 84)
            pygame.draw.rect(row_bg, icon_col, (6, 8, 8, r.height - 16))
            pygame.draw.rect(row_bg, (0, 0, 0, 150),
                             (6, 8, 8, r.height - 16), 1)

            name_col = (238, 240, 246) if affordable else (140, 140, 148)
            name_s = self.font.render(defn["name"], True, name_col)
            row_bg.blit(name_s, (22, 4))

            cx = 22
            cy = 4 + name_s.get_height() + 2
            for rsrc, amt in defn["cost"].items():
                col = RESOURCE_COLORS[rsrc]
                txt = self.font.render(
                    f"{amt}", True,
                    (238, 240, 246) if affordable else (140, 140, 148))
                pygame.draw.rect(row_bg, col, (cx, cy + 3, 8, 8))
                row_bg.blit(txt, (cx + 12, cy))
                cx += 12 + txt.get_width() + 8
            if not defn["cost"]:
                txt = self.font.render("-", True, name_col)
                row_bg.blit(txt, (cx, cy))

            surface.blit(row_bg, r.topleft)