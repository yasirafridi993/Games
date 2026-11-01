"""Right-side research panel shown when a Blacksmith or Market is selected.

The class is named ``ResearchMenu``; the module is ``tech_menu`` to match
the earlier phase naming. It is positioned above the minimap so its buttons
never collide with minimap clicks.
"""

import pygame

from . import config as C
from .building_defs import BUILDING_DEFS
from .resources import RESOURCE_COLORS
from .tech import TECH_DEFS, techs_for_building


class ResearchMenu:
    def __init__(self, game):
        self.game = game
        self.font = pygame.font.SysFont("consolas,couriernew,monospace", 13)
        self.font_small = pygame.font.SysFont(
            "consolas,couriernew,monospace", 11)
        self.font_bold = pygame.font.SysFont(
            "consolas,couriernew,monospace", 14, bold=True)

        self.rects = {}
        self.hovered = None
        self._panel_rect = pygame.Rect(0, 0, 0, 0)

    # ------------------------------------------------------------------
    def active_building(self):
        b = self.game.selected_building
        if b is None or not b.alive or not b.complete:
            return None
        if b.research_queue is None:
            return None
        return b

    def is_active(self):
        return self.active_building() is not None

    # ------------------------------------------------------------------
    def layout(self, surface):
        b = self.active_building()
        if b is None:
            return

        sw = surface.get_width()
        sh = surface.get_height()
        width = C.RESEARCH_MENU_WIDTH
        row_h = C.RESEARCH_MENU_ROW_H
        pad = C.BUILD_MENU_PAD

        techs = techs_for_building(b.kind)
        header_h = 30
        progress_h = 26 if b.research_queue.items else 0
        total_h = header_h + len(techs) * (row_h + pad) + progress_h + 14

        x = sw - width - C.BUILD_MENU_MARGIN
        # Sit ABOVE the minimap so clicks never overlap.
        bottom_clearance = (C.MINIMAP_SIZE + C.MINIMAP_MARGIN + 8)
        y = sh - total_h - bottom_clearance
        y = max(60, y)

        self._panel_rect = pygame.Rect(x, y, width, total_h)

        ry = y + header_h
        self.rects.clear()
        for key in techs:
            r = pygame.Rect(x + pad, ry, width - pad * 2, row_h)
            self.rects[key] = r
            ry += row_h + pad

    # ------------------------------------------------------------------
    def hit_test_tech(self, pos):
        for key, r in self.rects.items():
            if r.collidepoint(pos):
                return key
        return None

    # ------------------------------------------------------------------
    def can_afford(self, key):
        return self.game.stockpile.can_afford(TECH_DEFS[key].cost)

    def is_researched(self, key):
        ts = self.game.tech_states.get(C.FACTION_PLAYER)
        return ts is not None and ts.has(key)

    def is_available(self, key):
        ts = self.game.tech_states.get(C.FACTION_PLAYER)
        return ts is not None and ts.is_available(key)

    # ------------------------------------------------------------------
    def draw(self, surface):
        b = self.active_building()
        if b is None:
            return
        self.layout(surface)

        panel = self._panel_rect
        bg = pygame.Surface(panel.size, pygame.SRCALPHA)
        bg.fill((14, 18, 26, 210))
        pygame.draw.rect(bg, (92, 112, 142, 220), bg.get_rect(), 1)
        surface.blit(bg, panel.topleft)

        header = self.font_bold.render(
            f"RESEARCH — {BUILDING_DEFS[b.kind]['name']}",
            True, (206, 176, 96))
        surface.blit(header, (panel.x + 10, panel.y + 8))

        hovered = self.hovered
        ts = self.game.tech_states.get(C.FACTION_PLAYER)

        for key in techs_for_building(b.kind):
            r = self.rects.get(key)
            if r is None:
                continue
            defn = TECH_DEFS[key]
            researched = ts is not None and ts.has(key)
            available = ts is not None and ts.is_available(key)
            afford = self.can_afford(key)
            selectable = available and afford

            row_bg = pygame.Surface(r.size, pygame.SRCALPHA)
            if key == hovered and selectable:
                row_bg.fill((70, 96, 130, 220))
            elif researched:
                row_bg.fill((28, 48, 34, 200))
            elif not available:
                row_bg.fill((24, 26, 30, 190))
            else:
                row_bg.fill((28, 34, 46, 200))
            pygame.draw.rect(row_bg, (110, 130, 160, 220),
                             row_bg.get_rect(), 1)

            swatch = (150, 200, 150) if selectable else (
                (100, 180, 120) if researched else (90, 90, 94))
            pygame.draw.rect(row_bg, swatch, (6, 6, 8, r.height - 16))
            pygame.draw.rect(row_bg, (0, 0, 0, 150),
                             (6, 6, 8, r.height - 16), 1)

            name_col = ((238, 240, 246) if selectable else
                        ((190, 240, 200) if researched else (140, 140, 148)))
            name_s = self.font.render(defn.name, True, name_col)
            row_bg.blit(name_s, (22, 4))

            desc_col = (180, 190, 205) if selectable else (110, 110, 116)
            desc_s = self.font_small.render(defn.description, True, desc_col)
            row_bg.blit(desc_s, (22, 4 + name_s.get_height() + 2))

            cy = 4 + name_s.get_height() + 2 + desc_s.get_height() + 2
            cx = 22
            if researched:
                done_s = self.font_small.render("DONE", True, (140, 220, 150))
                row_bg.blit(done_s, (cx, cy))
            elif not available:
                missing = [req for req in defn.requires
                           if ts is None or not ts.has(req)]
                req_txt = ", ".join(missing)
                lock_s = self.font_small.render(
                    f"Requires: {req_txt}", True, (200, 140, 130))
                row_bg.blit(lock_s, (cx, cy))
            else:
                for rsrc, amt in defn.cost.items():
                    col = RESOURCE_COLORS[rsrc]
                    txt = self.font_small.render(f"{amt}", True, name_col)
                    pygame.draw.rect(row_bg, col, (cx, cy + 3, 7, 7))
                    row_bg.blit(txt, (cx + 10, cy))
                    cx += 10 + txt.get_width() + 8
                t_txt = self.font_small.render(
                    f"{int(defn.research_time)}s", True,
                    (180, 190, 205) if selectable else (110, 110, 116))
                row_bg.blit(t_txt, (cx + 6, cy))

            surface.blit(row_bg, r.topleft)

        if b.research_queue.items:
            qy = panel.bottom - 26
            prog = b.research_queue.current_progress()
            bar_w = panel.width - 20
            bar_h = 6
            bar_x = panel.x + 10
            pygame.draw.rect(surface, (24, 28, 36),
                             (bar_x, qy, bar_w, bar_h))
            pygame.draw.rect(surface, (232, 196, 92),
                             (bar_x, qy, int(bar_w * prog), bar_h))
            pygame.draw.rect(surface, (110, 130, 160),
                             (bar_x, qy, bar_w, bar_h), 1)
            cur = b.research_queue.items[0]
            label = self.font_small.render(
                f"Researching: {TECH_DEFS[cur.key].name}",
                True, (206, 176, 96))
            surface.blit(label, (panel.x + 10, qy - 14))