"""Shared look and feel for every menu screen (DirectGUI)."""
import os

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import Filename, TextNode

from game.config import ASSETS_DIR

TEXT = (0.96, 0.97, 1.0, 1.0)
MUTED = (0.68, 0.72, 0.80, 1.0)
ACCENT = (0.95, 0.22, 0.20, 1.0)
GOLD = (1.0, 0.82, 0.25, 1.0)
PANEL = (0.025, 0.035, 0.06, 0.90)
BTN = (0.08, 0.11, 0.16, 0.98)
BTN_HOVER = (0.95, 0.22, 0.12, 1.0)
BTN_PRESS = (0.62, 0.12, 0.08, 1.0)
BTN_OFF = (0.10, 0.10, 0.12, 0.6)

_font = None


def init_font(loader):
    """Pick a nicer font if one is available; fall back to Panda's default."""
    global _font
    candidates = [ASSETS_DIR / "fonts" / "ui.ttf"]
    windir = os.environ.get("WINDIR")
    if windir:
        candidates.append(os.path.join(windir, "Fonts", "segoeuib.ttf"))
        candidates.append(os.path.join(windir, "Fonts", "arialbd.ttf"))
    for path in candidates:
        try:
            if os.path.isfile(str(path)):
                font = loader.loadFont(Filename.fromOsSpecific(str(path)))
                if font is not None and font.isValid():
                    font.setPixelsPerUnit(90)
                    font.setPageSize(512, 512)
                    _font = font
                    return
        except Exception as exc:
            print("Could not load font %s: %s" % (path, exc))
    _font = TextNode.getDefaultFont()


def font():
    return _font if _font is not None else TextNode.getDefaultFont()


def format_time(seconds):
    """mm:ss.cc (e.g. 01:24.52)."""
    seconds = max(0.0, seconds)
    minutes = int(seconds // 60)
    return "%02d:%05.2f" % (minutes, seconds - minutes * 60)


def label(parent, text, pos, scale=0.07, fg=TEXT, align=TextNode.ACenter, may_change=False, shadow=True):
    return OnscreenText(text=text, parent=parent, pos=pos, scale=scale, fg=fg, font=font(),
                        align=align, mayChange=may_change,
                        shadow=(0, 0, 0, 0.8) if shadow else None)


def button(parent, text, command, pos, width=0.9, height=0.125, text_scale=0.064):
    return DirectButton(
        parent=parent, text=text, text_scale=text_scale, text_fg=TEXT, text_font=font(),
        text_pos=(0, -text_scale * 0.32), text_shadow=(0, 0, 0, 0.6),
        frameSize=(-width / 2, width / 2, -height / 2, height / 2),
        frameColor=(BTN, BTN_PRESS, BTN_HOVER, BTN_OFF), relief=DGG.FLAT,
        command=command, pos=pos, pressEffect=0, rolloverSound=None, clickSound=None)


class Screen:
    """A full-window overlay with a centred panel.  Subclasses add widgets to self.panel."""

    def __init__(self, app, dim, panel_size):
        self.app = app
        # a big frame in state NORMAL also swallows clicks so nothing behind it can be pressed
        self.root = DirectFrame(parent=app.aspect2d, frameColor=(0, 0, 0, dim),
                                frameSize=(-4, 4, -2, 2), state=DGG.NORMAL)
        w, h = panel_size
        self.panel = DirectFrame(parent=self.root, frameColor=PANEL,
                                 frameSize=(-w / 2, w / 2, -h / 2, h / 2), pos=(0, 0, 0))
        self.accent = DirectFrame(parent=self.panel, frameColor=ACCENT,
                                  frameSize=(-w / 2, w / 2, h / 2 - 0.012, h / 2))
        self.root.hide()

    @property
    def visible(self):
        return not self.root.isHidden()

    def show(self):
        self.root.show()

    def hide(self):
        self.root.hide()
