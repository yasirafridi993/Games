"""Isometric <-> world <-> screen coordinate helpers.

Conventions used across the whole project
-----------------------------------------
* Tile coordinates are integers ``(col, row)``.
* "World space" is measured in pixels at zoom 1.0 and is *not* scrolled or
  zoomed. The origin ``(0, 0)`` is the centre of tile ``(0, 0)``.
* "Screen space" is the final pixel position inside the game window.

For a tile ``(col, row)`` the world-space centre is::

    wx = (col - row) * TILE_HALF_W
    wy = (col + row) * TILE_HALF_H

This produces the classic 2:1 isometric diamond layout.
"""

import math

from . import config as C

__all__ = [
    "tile_to_world",
    "world_to_tile_f",
    "world_to_tile",
    "tile_diamond",
]


def tile_to_world(col: float, row: float):
    """Return the world-space centre of a (possibly fractional) tile."""
    return ((col - row) * C.TILE_HALF_W, (col + row) * C.TILE_HALF_H)


def world_to_tile_f(wx: float, wy: float):
    """Return fractional ``(col, row)`` for a world-space point."""
    hw = C.TILE_HALF_W
    hh = C.TILE_HALF_H
    col = (wx / hw + wy / hh) * 0.5
    row = (wy / hh - wx / hw) * 0.5
    return col, row


def world_to_tile(wx: float, wy: float):
    """Return the integer tile containing a world-space point."""
    col, row = world_to_tile_f(wx, wy)
    return int(math.floor(col)), int(math.floor(row))


def tile_diamond(cx: float, cy: float, half_w: float, half_h: float):
    """Return the four corner points of an isometric diamond.

    ``cx`` / ``cy`` is the diamond centre, ``half_w`` / ``half_h`` its
    half extents (already zoom-scaled).
    """
    return [
        (cx, cy - half_h),
        (cx + half_w, cy),
        (cx, cy + half_h),
        (cx - half_w, cy),
    ]