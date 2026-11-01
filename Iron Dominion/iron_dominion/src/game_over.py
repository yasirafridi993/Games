"""Full-screen victory / defeat overlay."""

import pygame

from . import config as C


class GameOverOverlay:
    def __init__(self, game):
        self.game = game
        self.big = pygame.font.SysFont(
            "consolas,couriernew,monospace", 64, bold=True)
        self.mid = pygame.font.SysFont(
            "consolas,couriernew,monospace", 22)
        self.small = pygame.font.SysFont(
            "consolas,couriernew,monospace", 16)

    def draw(self, surface):
        state = self.game.mission_state
        if state not in ("victory", "defeat"):
            return

        sw, sh = surface.get_size()
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill(C.GAME_OVER_OVERLAY)
        surface.blit(overlay, (0, 0))

        if state == "victory":
            title_txt = "VICTORY"
            title_col = C.GAME_OVER_VICTORY_COL
        else:
            title_txt = "DEFEAT"
            title_col = C.GAME_OVER_DEFEAT_COL

        title = self.big.render(title_txt, True, title_col)
        shadow = self.big.render(title_txt, True, (0, 0, 0))
        tx = (sw - title.get_width()) // 2
        ty = int(sh * 0.30)
        surface.blit(shadow, (tx + 3, ty + 3))
        surface.blit(title, (tx, ty))

        name = self.mid.render(
            f"{self.game.mission.name}  —  "
            f"{_fmt_time(self.game.mission_elapsed)}",
            True, C.GAME_OVER_TEXT_COL)
        surface.blit(name, ((sw - name.get_width()) // 2,
                            ty + title.get_height() + 10))

        # Objective summary
        lines = []
        for obj in self.game.objectives:
            mark = "[x]" if obj.complete else "[ ]"
            col = (C.OBJECTIVE_DONE_COL if obj.complete
                   else C.OBJECTIVE_TEXT_COL)
            lines.append((f"{mark} {obj.text}", col))

        y = ty + title.get_height() + 60
        for txt, col in lines:
            s = self.small.render(txt, True, col)
            surface.blit(s, ((sw - s.get_width()) // 2, y))
            y += s.get_height() + 4

        hint = self.small.render(
            "R: restart this mission    |    N: next mission    |    Esc: quit",
            True, C.GAME_OVER_HINT_COL)
        surface.blit(hint, ((sw - hint.get_width()) // 2,
                            sh - hint.get_height() - 40))


def _fmt_time(seconds):
    s = int(max(0.0, seconds))
    return f"{s // 60}:{s % 60:02d}"