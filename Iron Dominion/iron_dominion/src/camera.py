"""Scrolling / zooming camera operating in isometric world space."""

import math

from . import config as C


class Camera:
    """A 2D camera with smooth panning, mouse-anchored zoom and map clamping."""

    def __init__(self, view_w: int, view_h: int, bounds):
        self.view_w = float(view_w)
        self.view_h = float(view_h)

        self.min_x = self.max_x = 0.0
        self.min_y = self.max_y = 0.0
        self.set_bounds(bounds)

        self.x = (self.min_x + self.max_x) * 0.5
        self.y = (self.min_y + self.max_y) * 0.5
        self.zoom = 1.0

        self.vel_x = 0.0
        self.vel_y = 0.0

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def set_bounds(self, bounds) -> None:
        self.min_x, self.max_x, self.min_y, self.max_y = bounds

    def set_viewport(self, w: int, h: int) -> None:
        self.view_w = float(max(1, w))
        self.view_h = float(max(1, h))
        self.clamp()

    def center_on(self, wx: float, wy: float) -> None:
        self.x = wx
        self.y = wy
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.clamp()

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------
    def world_to_screen(self, wx: float, wy: float):
        return (
            (wx - self.x) * self.zoom + self.view_w * 0.5,
            (wy - self.y) * self.zoom + self.view_h * 0.5,
        )

    def screen_to_world(self, sx: float, sy: float):
        return (
            (sx - self.view_w * 0.5) / self.zoom + self.x,
            (sy - self.view_h * 0.5) / self.zoom + self.y,
        )

    # ------------------------------------------------------------------
    # Direct manipulation
    # ------------------------------------------------------------------
    def pan_screen(self, dx: float, dy: float) -> None:
        """Pan the camera by a *screen-space* delta (used by middle-drag)."""
        self.x += dx / self.zoom
        self.y += dy / self.zoom
        self.clamp()

    def zoom_by(self, factor: float, anchor=None) -> None:
        """Multiply the zoom level, keeping ``anchor`` (screen px) fixed."""
        if anchor is None:
            anchor = (self.view_w * 0.5, self.view_h * 0.5)

        wx, wy = self.screen_to_world(anchor[0], anchor[1])
        new_zoom = max(C.ZOOM_MIN, min(C.ZOOM_MAX, self.zoom * factor))
        if abs(new_zoom - self.zoom) < 1e-6:
            return
        self.zoom = new_zoom

        # Re-derive the camera centre so that (wx, wy) stays under the anchor.
        self.x = wx - (anchor[0] - self.view_w * 0.5) / self.zoom
        self.y = wy - (anchor[1] - self.view_h * 0.5) / self.zoom
        self.clamp()

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------
    def update(self, dt: float, target_vx: float = 0.0, target_vy: float = 0.0) -> None:
        """Smoothly approach ``target_vx`` / ``target_vy`` and integrate."""
        k = 1.0 - math.exp(-C.CAMERA_SMOOTHING * dt)
        self.vel_x += (target_vx - self.vel_x) * k
        self.vel_y += (target_vy - self.vel_y) * k

        if abs(self.vel_x) < 0.5:
            self.vel_x = 0.0
        if abs(self.vel_y) < 0.5:
            self.vel_y = 0.0

        self.x += self.vel_x * dt
        self.y += self.vel_y * dt
        self.clamp()

    # ------------------------------------------------------------------
    # Bounds
    # ------------------------------------------------------------------
    def clamp(self) -> None:
        half_w = self.view_w * 0.5 / self.zoom
        half_h = self.view_h * 0.5 / self.zoom

        if self.max_x - self.min_x <= half_w * 2.0:
            self.x = (self.min_x + self.max_x) * 0.5
        else:
            self.x = max(self.min_x + half_w, min(self.max_x - half_w, self.x))

        if self.max_y - self.min_y <= half_h * 2.0:
            self.y = (self.min_y + self.max_y) * 0.5
        else:
            self.y = max(self.min_y + half_h, min(self.max_y - half_h, self.y))