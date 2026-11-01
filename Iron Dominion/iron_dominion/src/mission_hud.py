"""Mission HUD: start banner + live objective tracker."""

import pygame

from . import config as C


class MissionHud:
    def __init__(self, game):
        self.game = game
        self.font = pygame.font.SysFont("consolas,couriernew,monospace", 15)
        self.small = pygame.font.SysFont("consolas,couriernew,monospace", 13)
        self.bold = pygame.font.SysFont(
            "consolas,couriernew,monospace", 15, bold=True)
        self.banner_title = pygame.font.SysFont(
            "consolas,couriernew,monospace", 40, bold=True)
        self.banner_sub = pygame.font.SysFont(
            "consolas,couriernew,monospace", 18)

    # ------------------------------------------------------------------
    def draw(self, surface):
        self._draw_objective_panel(surface)
        if self.game.mission_banner_timer > 0:
            self._draw_banner(surface)

    # ------------------------------------------------------------------
    def _draw_objective_panel(self, surface):
        # Objective list sits below the info panel; the info panel is
        # about 220 px tall at font size 15, so start at y = 250.
        lines = []
        for obj in self.game.objectives:
            head = f"{obj.marker()} {obj.text}"
            lines.append(("head", head,
                          C.OBJECTIVE_DONE_COL if obj.complete
                          else C.OBJECTIVE_TEXT_COL))
            prog = obj.progress_text(self.game)
            if prog and not obj.complete:
                lines.append(("prog", f"     {prog}",
                              C.OBJECTIVE_PROGRESS_COL))

        if not lines:
            return

        rendered = []
        for _tag, txt, col in lines:
            f = self.small if _tag == "prog" else self.font
            rendered.append(f.render(txt, True, col))

        w = max(s.get_width() for s in rendered) + 20
        h = sum(s.get_height() for s in rendered) + 16
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill(C.OBJECTIVE_PANEL_BG)
        pygame.draw.rect(panel, C.OBJECTIVE_PANEL_BORDER,
                         panel.get_rect(), 1)
        y = 8
        for s in rendered:
            panel.blit(s, (10, y))
            y += s.get_height()

        # Mission title + elapsed time above the objectives
        title = self.bold.render(
            f"{self.game.mission.name}   "
            f"{_fmt_time(self.game.mission_elapsed)}",
            True, C.MISSION_BANNER_TITLE_COL)
        title_h = title.get_height() + 8
        full_w = max(w, title.get_width() + 20)
        full_h = h + title_h
        full = pygame.Surface((full_w, full_h), pygame.SRCALPHA)
        full.fill(C.OBJECTIVE_PANEL_BG)
        pygame.draw.rect(full, C.OBJECTIVE_PANEL_BORDER,
                         full.get_rect(), 1)
        full.blit(title, (10, 4))
        full.blit(panel, (0, title_h))

        surface.blit(full, (10, 250))

    # ------------------------------------------------------------------
    def _draw_banner(self, surface):
        ttl = self.game.mission.name.upper()
        desc = self.game.mission.description

        ttl_s = self.banner_title.render(ttl, True, C.MISSION_BANNER_TITLE_COL)
        desc_s = self.banner_sub.render(desc, True, C.MISSION_BANNER_TEXT_COL)

        pad = 22
        w = max(ttl_s.get_width(), desc_s.get_width()) + pad * 2
        h = ttl_s.get_height() + desc_s.get_height() + pad * 2 + 6

        # Fade the banner out over the last second
        t = self.game.mission_banner_timer
        alpha = 255
        if t < 1.0:
            alpha = int(255 * t)
        alpha = max(0, min(255, alpha))

        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((10, 12, 18, int(200 * alpha / 255)))
        pygame.draw.rect(panel, (*C.OBJECTIVE_PANEL_BORDER, alpha),
                         panel.get_rect(), 2)

        ttl_s.set_alpha(alpha)
        desc_s.set_alpha(alpha)

        x = (w - ttl_s.get_width()) // 2
        panel.blit(ttl_s, (x, pad))
        x = (w - desc_s.get_width()) // 2
        panel.blit(desc_s, (x, pad + ttl_s.get_height() + 6))

        sw, sh = surface.get_size()
        surface.blit(panel, ((sw - w) // 2, int(sh * 0.28)))


def _fmt_time(seconds):
    s = int(max(0.0, seconds))
    return f"{s // 60}:{s % 60:02d}"