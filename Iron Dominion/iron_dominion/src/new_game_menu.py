"""New Game screen: pick a map, difficulty, number of opponents, team layout."""

import pygame

from . import config as C
from .ai import DIFFICULTY_EASY, DIFFICULTY_MEDIUM, DIFFICULTY_HARD
from .missions import MISSION_LIBRARY, MISSION_ORDER
from .ui import (
    Button, Fonts, draw_backdrop, draw_panel, draw_shadowed_title, draw_text,
)


_DIFFICULTIES = (
    (DIFFICULTY_EASY,   "Easy",   "Slow AI. Small army. Forgiving."),
    (DIFFICULTY_MEDIUM, "Medium", "Balanced AI. Standard play."),
    (DIFFICULTY_HARD,   "Hard",   "Aggressive AI. Attacks fast."),
)

# 1..7 opponents (player + these = total factions)
_OPPONENT_COUNTS = (1, 2, 3, 4, 5, 6, 7)

_TEAM_MODES = ("ffa", "2v2", "3v3", "4v4")

_TEAM_LABELS = {
    "ffa": ("Free for All", 1),   # (label, min_total_factions)
    "2v2": ("2v2", 4),
    "3v3": ("3v3", 6),
    "4v4": ("4v4", 8),
}


class NewGameMenu:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()

        self.title_font   = Fonts.get(38, bold=True)
        self.section_font = Fonts.get(16, bold=True)
        self.item_bold    = Fonts.get(14, bold=True)
        self.item         = Fonts.get(13)
        self.desc_font    = Fonts.get(12)
        self.button_font  = Fonts.get(18, bold=True)

        self.mission_keys = list(MISSION_ORDER)
        self.selected_mission_idx    = 0
        self.selected_difficulty_idx = 1   # Medium
        self.selected_opponent_idx   = 0   # 1 opponent
        self.selected_team_idx       = 0   # FFA

        self._mission_rects = []
        self._diff_rects    = []
        self._opp_rects     = []
        self._team_rects    = []

        self._layout(screen.get_size())

    # ------------------------------------------------------------------
    def _layout(self, size):
        sw, sh = size
        pad = 20
        gap = 16

        top_y = int(sh * 0.16)
        col_h = int(sh * 0.68)
        col_w = (sw - pad * 2 - gap * 3) // 4

        self.mission_panel = pygame.Rect(pad, top_y, col_w, col_h)
        self.diff_panel    = pygame.Rect(pad + (col_w + gap), top_y, col_w, col_h)
        self.opp_panel     = pygame.Rect(pad + 2 * (col_w + gap), top_y, col_w, col_h)
        self.team_panel    = pygame.Rect(pad + 3 * (col_w + gap), top_y, col_w, col_h)

        def make_rows(panel, n, row_h):
            rows = []
            ry = panel.y + 42
            for _ in range(n):
                rows.append(pygame.Rect(panel.x + 10, ry,
                                        panel.width - 20, row_h))
                ry += row_h + 6
            return rows

        self._mission_rects = make_rows(self.mission_panel,
                                        len(self.mission_keys), 50)
        self._diff_rects    = make_rows(self.diff_panel,
                                        len(_DIFFICULTIES), 64)
        self._opp_rects     = make_rows(self.opp_panel,
                                        len(_OPPONENT_COUNTS), 34)
        self._team_rects    = make_rows(self.team_panel,
                                        len(_TEAM_MODES), 46)

        bw, bh = 180, 46
        self.btn_back  = Button((24, sh - bh - 20, bw, bh),
                                "BACK", self.button_font)
        self.btn_start = Button((sw - bw - 24, sh - bh - 20, bw, bh),
                                "START", self.button_font)

    # ------------------------------------------------------------------
    def run(self):
        while True:
            dt = self.clock.tick(C.TARGET_FPS) / 1000.0
            if dt > C.MAX_FRAME_TIME:
                dt = C.MAX_FRAME_TIME

            result = self._handle_events()
            if result is not None:
                return result

            self._draw()
            pygame.display.flip()

    # ------------------------------------------------------------------
    def _handle_events(self):
        mouse = pygame.mouse.get_pos()
        self.btn_back.update(mouse)
        self.btn_start.update(mouse)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return ("back", None)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return ("back", None)
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return self._start_result()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)
            if self.btn_back.handle_event(event):
                return ("back", None)
            if self.btn_start.handle_event(event):
                return self._start_result()
        return None

    def _handle_click(self, pos):
        for i, r in enumerate(self._mission_rects):
            if r.collidepoint(pos):
                self.selected_mission_idx = i
                return
        for i, r in enumerate(self._diff_rects):
            if r.collidepoint(pos):
                self.selected_difficulty_idx = i
                return
        for i, r in enumerate(self._opp_rects):
            if r.collidepoint(pos):
                self.selected_opponent_idx = i
                return
        for i, r in enumerate(self._team_rects):
            if r.collidepoint(pos):
                mode = _TEAM_MODES[i]
                if self._team_mode_enabled(mode):
                    self.selected_team_idx = i
                return

    # ------------------------------------------------------------------
    def _total_factions(self):
        return _OPPONENT_COUNTS[self.selected_opponent_idx] + 1

    def _team_mode_enabled(self, mode):
        min_total = _TEAM_LABELS[mode][1]
        return self._total_factions() >= min_total

    # ------------------------------------------------------------------
    def _start_result(self):
        mission     = self.mission_keys[self.selected_mission_idx]
        difficulty  = _DIFFICULTIES[self.selected_difficulty_idx][0]
        n_enemies   = _OPPONENT_COUNTS[self.selected_opponent_idx]
        team_mode   = _TEAM_MODES[self.selected_team_idx]

        # If team mode isn't valid for the current faction count, fall
        # back to FFA instead of erroring.
        if not self._team_mode_enabled(team_mode):
            team_mode = "ffa"

        return ("start", (mission, difficulty, n_enemies, team_mode))

    # ------------------------------------------------------------------
    def _draw(self):
        screen = self.screen
        sw, sh = screen.get_size()
        draw_backdrop(screen)
        draw_shadowed_title(screen, "NEW GAME", self.title_font,
                            (sw // 2, int(sh * 0.09)))

        mouse = pygame.mouse.get_pos()

        # -------------------- MAP -------------------------------------
        draw_panel(screen, self.mission_panel)
        draw_text(screen, "MAP", self.section_font,
                  (self.mission_panel.x + 12, self.mission_panel.y + 12),
                  C.UI_TITLE_COL)
        for i, key in enumerate(self.mission_keys):
            m = MISSION_LIBRARY[key]
            r = self._mission_rects[i]
            self._draw_row(r,
                           selected=(i == self.selected_mission_idx),
                           hover=r.collidepoint(mouse),
                           title=m.name,
                           sub=m.description,
                           pad_y=5)

        # -------------------- DIFFICULTY ------------------------------
        draw_panel(screen, self.diff_panel)
        draw_text(screen, "DIFFICULTY", self.section_font,
                  (self.diff_panel.x + 12, self.diff_panel.y + 12),
                  C.UI_TITLE_COL)
        for i, (k, label, desc) in enumerate(_DIFFICULTIES):
            r = self._diff_rects[i]
            self._draw_row(r,
                           selected=(i == self.selected_difficulty_idx),
                           hover=r.collidepoint(mouse),
                           title=label,
                           sub=desc,
                           pad_y=9)

        # -------------------- OPPONENTS -------------------------------
        draw_panel(screen, self.opp_panel)
        draw_text(screen, "OPPONENTS", self.section_font,
                  (self.opp_panel.x + 12, self.opp_panel.y + 12),
                  C.UI_TITLE_COL)
        for i, n in enumerate(_OPPONENT_COUNTS):
            r = self._opp_rects[i]
            label = f"{n} opponent" + ("s" if n > 1 else "")
            self._draw_row(r,
                           selected=(i == self.selected_opponent_idx),
                           hover=r.collidepoint(mouse),
                           title=label,
                           sub=None,
                           pad_y=7)

        # -------------------- TEAMS -----------------------------------
        draw_panel(screen, self.team_panel)
        draw_text(screen, "TEAMS", self.section_font,
                  (self.team_panel.x + 12, self.team_panel.y + 12),
                  C.UI_TITLE_COL)
        for i, mode in enumerate(_TEAM_MODES):
            r = self._team_rects[i]
            enabled = self._team_mode_enabled(mode)
            label, min_total = _TEAM_LABELS[mode]

            if not enabled:
                pygame.draw.rect(screen, (18, 22, 28), r)
                pygame.draw.rect(screen, (60, 68, 78), r, 2)
                t = self.item_bold.render(label, True, (110, 116, 124))
                screen.blit(t, (r.x + 10, r.y + 5))
                s = self.desc_font.render(
                    f"needs {min_total}+ factions", True, (110, 116, 124))
                screen.blit(s, (r.x + 10, r.y + 5 + t.get_height() + 2))
            else:
                self._draw_row(r,
                               selected=(i == self.selected_team_idx),
                               hover=r.collidepoint(mouse),
                               title=label,
                               sub=None,
                               pad_y=12)

        # -------------------- BUTTONS ---------------------------------
        self.btn_back.draw(screen)
        self.btn_start.draw(screen)

        hint = Fonts.get(13).render(
            "Enter: Start    Esc: Back", True, C.UI_TEXT_DIM)
        screen.blit(hint, ((sw - hint.get_width()) // 2,
                           sh - hint.get_height() - 8))

    # ------------------------------------------------------------------
    def _draw_row(self, rect, selected, hover, title, sub=None, pad_y=6):
        if selected:
            bg, border = (54, 74, 100), C.UI_SELECTED_BORDER
        elif hover:
            bg, border = (34, 44, 58), C.UI_PANEL_BORDER_HOVER
        else:
            bg, border = (24, 30, 40), C.UI_PANEL_BORDER

        pygame.draw.rect(self.screen, bg, rect)
        pygame.draw.rect(self.screen, border, rect, 2)

        t = self.item_bold.render(title, True, C.UI_TEXT_COL)
        self.screen.blit(t, (rect.x + 10, rect.y + pad_y))
        if sub:
            s = self.desc_font.render(sub, True, C.UI_TEXT_DIM)
            self.screen.blit(
                s, (rect.x + 10, rect.y + pad_y + t.get_height() + 2))