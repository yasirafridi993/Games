"""Right-side training panel.

Shown when a production building is selected. Positioned above the minimap
so its buttons never collide with minimap clicks.

A one-line diagnostic print fires when a training row is hit. Set
``DEBUG_MENU = False`` to silence it once things are working.
"""

import pygame

from . import config as C
from .building_defs import BUILDING_DEFS
from .resources import RESOURCE_COLORS
from .unit_defs import UNIT_DEFS


DEBUG_MENU = True


class TrainingMenu:
    def __init__(self, game):
        self.game = game
        self.font = pygame.font.SysFont("consolas,couriernew,monospace", 13)
        self.font_bold = pygame.font.SysFont(
            "consolas,couriernew,monospace", 14, bold=True)

        self.rects = {}
        self.hovered = None
        self.queue_rects = {}
        self.cancel_rect = None
        self._panel_rect = pygame.Rect(0, 0, 0, 0)

    # ------------------------------------------------------------------
    def active_building(self):
        b = self.game.selected_building
        if b is None:
            return None
        if not getattr(b, "alive", False):
            return None
        if not getattr(b, "complete", False):
            return None
        if getattr(b, "queue", None) is None:
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
        width = C.TRAINING_MENU_WIDTH
        row_h = C.TRAINING_MENU_ROW_H
        pad = C.BUILD_MENU_PAD

        produces = BUILDING_DEFS[b.kind].get("produces", ())
        n_rows = len(produces)

        header_h = 30
        queue_h = 34 + 8 + C.TRAINING_QUEUE_ROW_H * max(1, len(b.queue.items))
        total_h = header_h + n_rows * (row_h + pad) + queue_h + 16

        x = sw - width - C.BUILD_MENU_MARGIN
        bottom_clearance = (C.MINIMAP_SIZE + C.MINIMAP_MARGIN + 8)
        y = sh - total_h - bottom_clearance
        y = max(60, y)

        self._panel_rect = pygame.Rect(x, y, width, total_h)

        ry = y + header_h
        self.rects.clear()
        for kind in produces:
            r = pygame.Rect(x + pad, ry, width - pad * 2, row_h)
            self.rects[kind] = r
            ry += row_h + pad

        qy = ry + 6
        self.queue_rects.clear()
        self.cancel_rect = None
        for i in range(len(b.queue.items)):
            self.queue_rects[i] = pygame.Rect(
                x + pad, qy, width - pad * 2, C.TRAINING_QUEUE_ROW_H)
            qy += C.TRAINING_QUEUE_ROW_H

    # ------------------------------------------------------------------
    def hit_test_unit(self, pos):
        for kind, r in self.rects.items():
            if r.collidepoint(pos):
                if DEBUG_MENU:
                    print(f"[train] hit_test_unit: {kind} at {pos} "
                          f"(rect={r})")
                return kind
        return None

    def hit_test_queue(self, pos):
        for i, r in self.queue_rects.items():
            if r.collidepoint(pos):
                return i
        return None

    # ------------------------------------------------------------------
    def can_afford(self, unit_kind):
        return self.game.stockpile.can_afford(UNIT_DEFS[unit_kind]["cost"])

    def can_pop(self, unit_kind):
        return self.game.units.can_train_more(unit_kind, self.game.buildings)

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
            f"TRAIN — {BUILDING_DEFS[b.kind]['name']}",
            True, (206, 176, 96))
        surface.blit(header, (panel.x + 10, panel.y + 8))

        for kind in self.rects:
            r = self.rects[kind]
            defn = UNIT_DEFS[kind]
            afford = self.can_afford(kind)
            pop_ok = self.can_pop(kind)
            can = afford and pop_ok

            row_bg = pygame.Surface(r.size, pygame.SRCALPHA)
            if kind == self.hovered and can:
                row_bg.fill((70, 96, 130, 220))
            else:
                row_bg.fill((28, 34, 46, 200))
            pygame.draw.rect(row_bg, (110, 130, 160, 220),
                             row_bg.get_rect(), 1)

            name_col = (238, 240, 246) if can else (140, 140, 148)
            name_s = self.font.render(defn["name"], True, name_col)
            row_bg.blit(name_s, (22, 3))

            swatch = (150, 200, 150) if can else (90, 90, 94)
            pygame.draw.rect(row_bg, swatch, (6, 6, 8, r.height - 16))
            pygame.draw.rect(row_bg, (0, 0, 0, 150),
                             (6, 6, 8, r.height - 16), 1)

            cx = 22
            cy = 3 + name_s.get_height() + 2
            for rsrc, amt in defn["cost"].items():
                col = RESOURCE_COLORS[rsrc]
                txt = self.font.render(f"{amt}", True, name_col)
                pygame.draw.rect(row_bg, col, (cx, cy + 3, 8, 8))
                row_bg.blit(txt, (cx + 12, cy))
                cx += 12 + txt.get_width() + 8
            t_txt = self.font.render(f"{int(defn['train_time'])}s", True,
                                     (180, 190, 205) if can
                                     else (110, 110, 116))
            row_bg.blit(t_txt, (cx + 6, cy))

            surface.blit(row_bg, r.topleft)

        qy = panel.y + 30 + len(self.rects) * (
            C.TRAINING_MENU_ROW_H + C.BUILD_MENU_PAD) + 6
        qhdr = self.font_bold.render("QUEUE", True, (206, 176, 96))
        surface.blit(qhdr, (panel.x + 10, qy))

        if b.queue.items:
            prog = b.queue.current_progress()
            bar_w = panel.width - 20
            bar_h = 6
            bar_x = panel.x + 10
            bar_y = qy + 18
            pygame.draw.rect(surface, (24, 28, 36),
                             (bar_x, bar_y, bar_w, bar_h))
            pygame.draw.rect(surface, (232, 196, 92),
                             (bar_x, bar_y, int(bar_w * prog), bar_h))
            pygame.draw.rect(surface, (110, 130, 160),
                             (bar_x, bar_y, bar_w, bar_h), 1)

        for i, item in enumerate(b.queue.items):
            r = self.queue_rects.get(i)
            if r is None:
                continue
            row = pygame.Surface(r.size, pygame.SRCALPHA)
            row.fill((34, 44, 58, 200) if i == 0 else (24, 30, 40, 180))
            pygame.draw.rect(row, (110, 130, 160, 220),
                             row.get_rect(), 1)

            name = UNIT_DEFS[item.unit_kind]["name"]
            if i == 0:
                pct = int(b.queue.current_progress() * 100)
                label = f"{name}   {pct}%"
            else:
                label = f"{name}"
            txt = self.font.render(label, True, (224, 232, 242))
            row.blit(txt, (8, 4))
            surface.blit(row, r.topleft)