"""In-game pause overlay: Resume / Save / Restart / Main Menu / Quit."""

import pygame

from . import config as C
from .ui import Button, Fonts, draw_shadowed_title


class PauseMenu:
    def __init__(self, screen):
        self.screen = screen
        self.title_font = Fonts.get(48, bold=True)
        self.button_font = Fonts.get(20, bold=True)

        self._layout(screen.get_size())

    def _layout(self, size):
        sw, sh = size
        bw = 320
        bh = 46
        bx = (sw - bw) // 2
        by = int(sh * 0.30)
        gap = 12

        self.btn_resume = Button((bx, by, bw, bh), "RESUME",
                                 self.button_font)
        self.btn_save = Button((bx, by + (bh + gap), bw, bh),
                               "SAVE GAME", self.button_font)
        self.btn_restart = Button((bx, by + 2 * (bh + gap), bw, bh),
                                  "RESTART MISSION", self.button_font)
        self.btn_menu = Button((bx, by + 3 * (bh + gap), bw, bh),
                               "MAIN MENU", self.button_font)
        self.btn_quit = Button((bx, by + 4 * (bh + gap), bw, bh),
                               "QUIT GAME", self.button_font)
        self.buttons = [self.btn_resume, self.btn_save, self.btn_restart,
                        self.btn_menu, self.btn_quit]

    def update_hover(self):
        mouse = pygame.mouse.get_pos()
        for b in self.buttons:
            b.update(mouse)

    def handle_event(self, event):
        """Return None or one of:
        'resume', 'save', 'restart', 'main_menu', 'quit'."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "resume"

        for b in self.buttons:
            if b.handle_event(event):
                if b is self.btn_resume:
                    return "resume"
                if b is self.btn_save:
                    return "save"
                if b is self.btn_restart:
                    return "restart"
                if b is self.btn_menu:
                    return "main_menu"
                if b is self.btn_quit:
                    return "quit"
        return None

    def draw(self, surface):
        sw, sh = surface.get_size()
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        draw_shadowed_title(surface, "PAUSED", self.title_font,
                            (sw // 2, int(sh * 0.20)))

        for b in self.buttons:
            b.draw(surface)

        hint = Fonts.get(13).render(
            "Esc: Resume    F5: Quicksave    F9: Quickload",
            True, C.UI_TEXT_DIM)
        surface.blit(hint, ((sw - hint.get_width()) // 2,
                            sh - hint.get_height() - 12))