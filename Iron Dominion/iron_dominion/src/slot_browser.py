"""Save / Load slot browser.

Usage
-----
    result = SlotBrowser(screen, mode="save").run()
    # returns:
    #   ("slot", N)  -> user picked slot N
    #   ("cancel", None)

The caller is responsible for actually performing the save or load.
"""

import time

import pygame

from . import config as C
from . import savegame
from .ui import Button, Fonts, draw_backdrop, draw_shadowed_title


class SlotBrowser:
    def __init__(self, screen, mode="save"):
        assert mode in ("save", "load")
        self.screen = screen
        self.mode = mode
        self.clock = pygame.time.Clock()

        self.title_font = Fonts.get(38, bold=True)
        self.section_font = Fonts.get(18, bold=True)
        self.item_bold = Fonts.get(15, bold=True)
        self.item = Fonts.get(14)
        self.small = Fonts.get(12)
        self.button_font = Fonts.get(18, bold=True)

        # Slot data refreshed every frame while visible
        self._slot_rects = []
        self._layout(screen.get_size())

    # ------------------------------------------------------------------
    def _layout(self, size):
        sw, sh = size
        panel_w = 620
        panel_h = 480
        px = (sw - panel_w) // 2
        py = (sh - panel_h) // 2

        self.panel = pygame.Rect(px, py, panel_w, panel_h)

        pad = 14
        row_h = 46
        row_gap = 4
        list_x = px + pad
        list_top = py + 50
        list_w = panel_w - pad * 2

        self._slot_rects = []
        for i in range(savegame.MAX_SLOTS):
            r = pygame.Rect(list_x, list_top + i * (row_h + row_gap),
                            list_w, row_h)
            self._slot_rects.append(r)

        bw = 140
        bh = 42
        self.btn_cancel = Button((px + panel_w - bw - 12,
                                  py + panel_h - bh - 12, bw, bh),
                                 "CANCEL", self.button_font)

    # ------------------------------------------------------------------
    def run(self):
        while True:
            dt = self.clock.tick(C.TARGET_FPS) / 1000.0
            if dt > C.MAX_FRAME_TIME:
                dt = C.MAX_FRAME_TIME

            action, slot = self._handle_events()
            if action == "cancel":
                return ("cancel", None)
            if action == "slot":
                return ("slot", slot)

            self._draw()
            pygame.display.flip()

    # ------------------------------------------------------------------
    def _handle_events(self):
        slots = savegame.list_slots()
        mouse = pygame.mouse.get_pos()
        self.btn_cancel.update(mouse)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return ("cancel", None)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return ("cancel", None)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Delete with right-click is handled below; left-click selects
                for i, r in enumerate(self._slot_rects):
                    if r.collidepoint(event.pos):
                        info = slots[i]
                        if self.mode == "load" and info is None:
                            # Empty slot in load mode: nothing to do
                            continue
                        return ("slot", i + 1)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                for i, r in enumerate(self._slot_rects):
                    if r.collidepoint(event.pos):
                        if slots[i] is not None:
                            savegame.delete_slot(i + 1)
                        break

            if self.btn_cancel.handle_event(event):
                return ("cancel", None)
        return (None, None)

    # ------------------------------------------------------------------
    def _draw(self):
        screen = self.screen
        sw, sh = screen.get_size()

        draw_backdrop(screen)

        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, (0, 0))

        # Panel
        pygame.draw.rect(screen, C.UI_PANEL_BG, self.panel)
        pygame.draw.rect(screen, C.UI_PANEL_BORDER, self.panel, 2)

        title = "SAVE GAME" if self.mode == "save" else "LOAD GAME"
        draw_shadowed_title(screen, title, self.title_font,
                            (self.panel.centerx,
                             self.panel.y + 26))

        slots = savegame.list_slots()
        mouse = pygame.mouse.get_pos()

        for i, r in enumerate(self._slot_rects):
            info = slots[i]
            hover = r.collidepoint(mouse)
            empty = info is None
            is_corrupt = (info is not None and info.get("corrupt"))

            if empty:
                bg = (20, 24, 30)
                border = (60, 68, 78)
            elif is_corrupt:
                bg = (48, 26, 26)
                border = (140, 70, 70)
            elif hover:
                bg = (34, 44, 58)
                border = C.UI_PANEL_BORDER_HOVER
            else:
                bg = (24, 30, 40)
                border = C.UI_PANEL_BORDER

            pygame.draw.rect(screen, bg, r)
            pygame.draw.rect(screen, border, r, 2)

            # Slot number badge
            badge = pygame.Rect(r.x + 6, r.y + 6, 34, r.height - 12)
            pygame.draw.rect(screen, (14, 18, 24), badge)
            pygame.draw.rect(screen, C.UI_PANEL_BORDER, badge, 1)
            num_s = self.item_bold.render(str(i + 1), True, C.UI_TEXT_COL)
            screen.blit(num_s, (badge.x + (badge.width - num_s.get_width()) // 2,
                                badge.y + (badge.height - num_s.get_height()) // 2))

            if empty:
                s = self.item.render("Empty", True, C.UI_TEXT_DIM)
                screen.blit(s, (r.x + 52, r.y + (r.height - s.get_height()) // 2))
            elif is_corrupt:
                s = self.item.render("(corrupt - press RMB to delete)",
                                     True, (220, 130, 120))
                screen.blit(s, (r.x + 52, r.y + (r.height - s.get_height()) // 2))
            else:
                name = info["mission_name"]
                diff = info["difficulty"].upper()
                el = _fmt_time(info["elapsed"])
                when = _fmt_ts(info["saved_at"])

                line1 = self.item_bold.render(f"{name}  [{diff}]",
                                              True, C.UI_TEXT_COL)
                line2 = self.small.render(f"{el} elapsed    "
                                          f"saved {when}",
                                          True, C.UI_TEXT_DIM)
                screen.blit(line1, (r.x + 52, r.y + 5))
                screen.blit(line2, (r.x + 52, r.y + 5 + line1.get_height() + 2))

        # Cancel button
        self.btn_cancel.draw(screen)

        # Hint bar
        hint = ("Left-click: select    Right-click: delete save    "
                "Esc: cancel")
        hint_s = self.small.render(hint, True, C.UI_TEXT_DIM)
        screen.blit(hint_s,
                    (self.panel.centerx - hint_s.get_width() // 2,
                     self.panel.bottom - hint_s.get_height() - 8))


def _fmt_time(seconds):
    s = int(max(0.0, seconds))
    return f"{s // 60}:{s % 60:02d}"


def _fmt_ts(ts):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return "-"