"""Main menu scene: New Game, Load Game, Quit."""

import pygame

from . import config as C
from .ui import Button, Fonts, draw_shadowed_title


class MainMenu:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.time = 0.0

        self.title_font = Fonts.get(72, bold=True)
        self.sub_font = Fonts.get(20)
        self.button_font = Fonts.get(22, bold=True)
        self.small_font = Fonts.get(14)
        self.version_font = Fonts.get(13)

        self._new_clicked = False
        self._load_clicked = False
        self._layout(screen.get_size())

    def _layout(self, size):
        sw, sh = size
        bw = 320
        bh = 54
        bx = (sw - bw) // 2
        by = int(sh * 0.46)
        gap = 14

        self.btn_new = Button((bx, by, bw, bh), "NEW GAME",
                              self.button_font)
        self.btn_load = Button((bx, by + bh + gap, bw, bh), "LOAD GAME",
                               self.button_font)
        self.btn_quit = Button((bx, by + 2 * (bh + gap), bw, bh), "QUIT",
                               self.button_font)
        self.buttons = [self.btn_new, self.btn_load, self.btn_quit]

    def run(self):
        while True:
            dt = self.clock.tick(C.TARGET_FPS) / 1000.0
            if dt > C.MAX_FRAME_TIME:
                dt = C.MAX_FRAME_TIME
            self.time += dt

            if not self._handle_events():
                return ("quit", None)
            if self._new_clicked:
                return ("new_game", None)
            if self._load_clicked:
                return ("load_game", None)

            self._draw()
            pygame.display.flip()

    def _handle_events(self):
        self._new_clicked = False
        self._load_clicked = False

        mouse = pygame.mouse.get_pos()
        for b in self.buttons:
            b.update(mouse)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._new_clicked = True
            for b in self.buttons:
                if b.handle_event(event):
                    if b is self.btn_new:
                        self._new_clicked = True
                    elif b is self.btn_load:
                        self._load_clicked = True
                    elif b is self.btn_quit:
                        return False
        return True

    def _draw(self):
        screen = self.screen
        sw, sh = screen.get_size()

        screen.fill(C.UI_BG)
        t = self.time
        stripe_col = (18, 22, 30)
        for i in range(-sh, sw, 60):
            x0 = i + int(t * 8) % 60
            pygame.draw.line(screen, stripe_col,
                             (x0, 0), (x0 + sh, sh), 1)

        draw_shadowed_title(screen, "IRON DOMINION",
                            self.title_font, (sw // 2, int(sh * 0.22)))
        sub = "A 2D Isometric Real-Time Strategy Game"
        r = self.sub_font.render(sub, True, C.UI_TEXT_DIM)
        screen.blit(r, ((sw - r.get_width()) // 2, int(sh * 0.22) + 46))

        for b in self.buttons:
            b.draw(screen)

        ver = self.version_font.render(
            "v0.14   |   Arrow keys / WASD in-game to pan   |   F11 fullscreen",
            True, C.UI_TEXT_DIM)
        screen.blit(ver, (12, sh - ver.get_height() - 10))
        hint = self.small_font.render(
            "Enter: New Game    Esc: Quit", True, C.UI_TEXT_DIM)
        screen.blit(hint, (sw - hint.get_width() - 12,
                           sh - hint.get_height() - 10))