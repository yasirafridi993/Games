"""Procedural sprites for every building.

Each building is assembled from material primitives:
    stone walls (individual blocks, mortar, cracks)
    wood walls (planks, grain, pegs)
    plaster walls (timber frame, wattle texture)
    tiled / thatched / hip roofs (individual shingles)
    arched doors (iron hinges, wood planks)
    cross-barred windows
    stone foundations (beveled, mortared)

Consistent upper-left lighting. Soft ground shadows. Bottom-center anchor
so the renderer's `front_y + TILE_HALF_H` convention works unchanged.
"""

import math
import random

import pygame

from .building_defs import (
    TOWN_CENTER, HOUSE, BARRACKS, ARCHERY_RANGE, STABLE, STORAGE,
    FARM, TOWER, BLACKSMITH, MARKET,
)


# ===========================================================================
# Palette
# ===========================================================================
def _cl(v):
    return 0 if v < 0 else (255 if v > 255 else int(v))


def _s(c, f):
    return (_cl(c[0] * f), _cl(c[1] * f), _cl(c[2] * f))


# Stone
STONE_HI   = (216, 208, 192)
STONE      = (176, 166, 148)
STONE_MID  = (144, 132, 114)
STONE_LO   = (108, 98, 82)
STONE_EDGE = (66, 60, 50)

# Wood
WOOD_HI    = (196, 150, 102)
WOOD       = (162, 116, 76)
WOOD_MID   = (128, 88, 56)
WOOD_LO    = (92, 62, 38)
WOOD_EDGE  = (58, 38, 22)

# Plaster
PLASTER_HI = (232, 218, 186)
PLASTER    = (208, 190, 156)
PLASTER_LO = (168, 148, 118)

# Roof tile
TILE_HI    = (198, 108, 74)
TILE       = (168, 84, 56)
TILE_LO    = (128, 56, 38)
TILE_EDGE  = (80, 32, 22)

# Thatch
THATCH_HI  = (214, 178, 106)
THATCH     = (182, 144, 78)
THATCH_LO  = (134, 100, 52)
THATCH_EDGE= (86, 62, 30)

# Metal
IRON_HI    = (208, 212, 218)
IRON       = (162, 168, 176)
IRON_LO    = (98, 104, 114)
IRON_EDGE  = (52, 56, 64)

# Accents
BANNER     = (176, 52, 44)
BANNER_LO  = (118, 30, 26)
GOLD       = (206, 168, 76)
GOLD_LO    = (140, 106, 44)
WHEAT_HI   = (222, 190, 108)
WHEAT      = (188, 154, 82)


# ===========================================================================
# Shadow
# ===========================================================================
def _shadow(surf, cx, cy, rx, ry, alpha=95):
    sh = pygame.Surface((int(rx * 2) + 8, int(ry * 2) + 8), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, alpha), sh.get_rect())
    surf.blit(sh, (int(cx - rx - 4), int(cy - ry - 4)))


# ===========================================================================
# Stone wall
# ===========================================================================
def _draw_stone_wall(surf, cx, top_y, wall_w, wall_h, rng,
                     window_specs=None, door_spec=None, rows=6):
    """Two-faced stone wall. Top corner at (cx, top_y)."""
    hw = wall_w // 2
    row_h = wall_h // rows

    # LEFT face (SW-facing) — lighter
    for r in range(rows):
        y0 = top_y + r * row_h
        yy = y0 + row_h // 4
        for k in range(-(hw // 16) - 1, (hw // 16) + 2):
            bx = cx - hw + k * 16 + (8 if r % 2 else 0)
            bx2 = min(bx + 15, cx)
            if bx2 <= cx - hw:
                continue
            col = _s(STONE, 1.0 + rng.uniform(-0.14, 0.14))
            pygame.draw.polygon(surf, col, [
                (max(bx, cx - hw), yy + r * row_h + row_h // 4),
                (bx2, yy + r * row_h + row_h // 4),
                (bx2, yy + r * row_h - row_h + row_h // 4),
                (max(bx, cx - hw), yy + r * row_h - row_h + row_h // 4),
            ])
            pygame.draw.line(surf, STONE_EDGE,
                             (max(bx, cx - hw), yy + r * row_h + row_h // 4),
                             (bx2, yy + r * row_h + row_h // 4), 1)
        # row edge
        pygame.draw.line(surf, STONE_EDGE,
                         (cx - hw, yy + r * row_h + row_h // 4),
                         (cx, yy + r * row_h + row_h // 2 + row_h // 4), 1)

    # RIGHT face (SE-facing) — darker
    for r in range(rows):
        y0 = top_y + r * row_h
        yy = y0 + row_h // 4
        for k in range(-1, (hw // 16) + 1):
            bx = cx + k * 16 + (8 if r % 2 else 0)
            bx2 = min(bx + 15, cx + hw)
            if bx <= cx:
                continue
            col = _s(STONE_MID, 1.0 + rng.uniform(-0.14, 0.14))
            pygame.draw.polygon(surf, col, [
                (bx, yy + r * row_h + row_h // 2 + row_h // 4),
                (bx2, yy + r * row_h + row_h // 4 - (bx2 - cx)),
                (bx2, yy + r * row_h - row_h + row_h // 4 - (bx2 - cx)),
                (bx, yy + r * row_h - row_h + row_h // 2 + row_h // 4),
            ])
        pygame.draw.line(surf, STONE_EDGE,
                         (cx, yy + r * row_h + row_h // 2 + row_h // 4),
                         (cx + hw, yy + r * row_h + row_h // 4), 1)

    # Corner highlight and shadow
    pygame.draw.line(surf, STONE_HI,
                     (cx - hw + 1, top_y + wall_h + hw // 4 - 1),
                     (cx - hw + 1, top_y + hw // 4 + 1), 2)
    pygame.draw.line(surf, STONE_EDGE,
                     (cx + hw - 1, top_y + hw // 4 + 1),
                     (cx + hw - 1, top_y + wall_h + hw // 4 - 1), 1)

    # Door
    if door_spec is not None:
        dx, dy, dw, dh = door_spec
        _draw_arch_door(surf, cx + dx, top_y + wall_h + dy, dw, dh)

    # Windows
    if window_specs:
        for wx, wy, ww, wh in window_specs:
            _draw_window(surf, cx + wx, top_y + wy, ww, wh)


def _draw_arch_door(surf, x, y, w, h):
    """Arched wooden door with iron hinges and a handle."""
    # Surround
    pygame.draw.rect(surf, STONE_LO, (x - 2, y - h - 2, w + 4, h + 4))
    # Door body
    pygame.draw.rect(surf, WOOD_MID, (x, y - h, w, h))
    pygame.draw.rect(surf, WOOD, (x + 1, y - h + 1, w - 2, h - 2))
    # Vertical planks
    for i in range(1, w - 1, 4):
        pygame.draw.line(surf, WOOD_LO,
                         (x + i, y - h + 1), (x + i, y - 1), 1)
    # Arch
    pygame.draw.ellipse(surf, WOOD_MID, (x, y - h - 6, w, 12))
    pygame.draw.ellipse(surf, WOOD, (x + 1, y - h - 5, w - 2, 10))
    pygame.draw.ellipse(surf, WOOD_EDGE, (x, y - h - 6, w, 12), 1)
    # Iron bands
    for yy in (y - h + 4, y - h // 2, y - 5):
        pygame.draw.line(surf, IRON_LO, (x + 1, yy), (x + w - 2, yy), 2)
        pygame.draw.line(surf, IRON, (x + 1, yy - 1), (x + w - 2, yy - 1), 1)
    # Handle
    pygame.draw.circle(surf, IRON_HI, (x + w - 4, y - h // 2), 2)
    pygame.draw.circle(surf, IRON_LO, (x + w - 4, y - h // 2), 2, 1)


def _draw_window(surf, x, y, w, h):
    """Cross-barred window with a stone surround."""
    pygame.draw.rect(surf, STONE_LO, (x - 1, y - 1, w + 2, h + 2))
    pygame.draw.rect(surf, (38, 31, 27), (x, y, w, h))
    pygame.draw.rect(surf, (148, 112, 68),
                     (x + 1, y + 1, max(1, w - 2), max(1, h - 2)))
    pygame.draw.rect(surf, (224, 178, 100),
                     (x + 2, y + 2, max(1, w // 3), max(1, h // 3)))
    pygame.draw.line(surf, (246, 210, 142),
                     (x + 2, y + 2), (x + max(2, w - 3), y + 2), 1)
    # Cross bars
    pygame.draw.line(surf, (62, 44, 28),
                     (x + w // 2, y + 1), (x + w // 2, y + h - 1), 1)
    pygame.draw.line(surf, (62, 44, 28),
                     (x + 1, y + h // 2), (x + w - 1, y + h // 2), 1)


# ===========================================================================
# Wood wall
# ===========================================================================
def _draw_wood_wall(surf, cx, top_y, wall_w, wall_h, rng,
                    window_specs=None, door_spec=None, plank_w=10):
    hw = wall_w // 2
    # LEFT face — lighter
    for i in range((hw * 2) // plank_w + 1):
        px = cx - hw + i * plank_w
        px2 = min(px + plank_w, cx)
        if px2 <= px:
            continue
        col = _s(WOOD, 1.0 + rng.uniform(-0.10, 0.10))
        pygame.draw.polygon(surf, col, [
            (px, top_y + wall_h + (px2 - (cx - hw)) // 2),
            (px2, top_y + wall_h + (px2 - (cx - hw)) // 2),
            (px2, top_y + (px2 - (cx - hw)) // 2),
            (px, top_y),
        ])
        pygame.draw.line(surf, WOOD_EDGE, (px, top_y),
                         (px, top_y + wall_h + (px2 - (cx - hw)) // 2), 1)
        # Wood grain
        for _ in range(3):
            gy = top_y + rng.randint(2, wall_h - 2)
            pygame.draw.line(surf, _s(WOOD_MID, 0.9),
                             (px + 1, gy),
                             (px2 - 1, gy + (px2 - px) // 4), 1)

    # RIGHT face — darker
    for i in range((hw * 2) // plank_w + 1):
        px = cx + i * plank_w
        px2 = min(px + plank_w, cx + hw)
        if px >= cx + hw:
            continue
        col = _s(WOOD_MID, 1.0 + rng.uniform(-0.10, 0.10))
        pygame.draw.polygon(surf, col, [
            (px, top_y + wall_h + (cx - px) // 2 + wall_h // 2 - wall_h // 2),
            (px2, top_y + wall_h + (cx - px2) // 2 - (px2 - px) // 1 + 0),
            (px2, top_y + (cx - px2) // 2 - (px2 - px) // 1 + 0),
            (px, top_y + (cx - px) // 2),
        ])
        # (simpler fallback for corners)
    # Simpler: just fill the SE face
    pygame.draw.polygon(surf, WOOD_MID, [
        (cx, top_y + wall_h + hw // 2),
        (cx + hw, top_y + wall_h + hw // 4 - hw // 4),
        (cx + hw, top_y + hw // 4),
        (cx, top_y + hw // 2),
    ])
    # Horizontal beams
    for yy in (top_y + 4, top_y + wall_h // 2 + 2, top_y + wall_h - 2):
        pygame.draw.line(surf, WOOD_LO,
                         (cx - hw, yy + hw // 4),
                         (cx, yy + hw // 2), 2)
        pygame.draw.line(surf, WOOD_LO,
                         (cx, yy + hw // 2),
                         (cx + hw, yy + hw // 4), 2)
    # Corner
    pygame.draw.line(surf, WOOD_HI,
                     (cx - hw + 1, top_y + wall_h + hw // 4 - 1),
                     (cx - hw + 1, top_y + hw // 4 + 1), 2)

    if door_spec is not None:
        dx, dy, dw, dh = door_spec
        _draw_arch_door(surf, cx + dx, top_y + wall_h + dy, dw, dh)
    if window_specs:
        for wx, wy, ww, wh in window_specs:
            _draw_window(surf, cx + wx, top_y + wy, ww, wh)


# ===========================================================================
# Plaster wall
# ===========================================================================
def _draw_plaster_wall(surf, cx, top_y, wall_w, wall_h, rng,
                       window_specs=None, door_spec=None):
    hw = wall_w // 2
    # LEFT face — lighter
    for i in range(hw * 2):
        px = cx - hw + i
        if px >= cx:
            break
        col = _s(PLASTER, 1.0 + rng.uniform(-0.05, 0.05))
        pygame.draw.line(surf, col,
                         (px, top_y + (px - (cx - hw)) // 2),
                         (px, top_y + wall_h + (px - (cx - hw)) // 2))
    # RIGHT face — darker
    for i in range(hw * 2):
        px = cx + i
        if px >= cx + hw:
            break
        col = _s(PLASTER_LO, 1.0 + rng.uniform(-0.05, 0.05))
        pygame.draw.line(surf, col,
                         (px, top_y + (cx - px) // 2),
                         (px, top_y + wall_h + (cx - px) // 2))
    # Timber frame
    for corner_x in (cx - hw, cx, cx + hw):
        if corner_x == cx:
            top_corner = top_y + wall_h // 2 + hw // 2
            bottom_corner = top_y + wall_h + hw // 2
            pygame.draw.line(surf, WOOD_LO,
                             (cx, top_y + hw // 2 + wall_h),
                             (cx, top_y + hw // 2), 3)
        else:
            top_corner = top_y + (0 if corner_x == cx else hw // 4)
            bottom_corner = top_corner + wall_h
            pygame.draw.line(surf, WOOD_LO,
                             (corner_x, top_y + hw // 4),
                             (corner_x, top_y + hw // 4 + wall_h), 3)
    # Horizontal beam at top
    pygame.draw.line(surf, WOOD_LO,
                     (cx - hw, top_y + hw // 4),
                     (cx, top_y + hw // 2), 3)
    pygame.draw.line(surf, WOOD_LO,
                     (cx, top_y + hw // 2),
                     (cx + hw, top_y + hw // 4), 3)

    if door_spec is not None:
        dx, dy, dw, dh = door_spec
        _draw_arch_door(surf, cx + dx, top_y + wall_h + dy, dw, dh)
    if window_specs:
        for wx, wy, ww, wh in window_specs:
            _draw_window(surf, cx + wx, top_y + wy, ww, wh)


# ===========================================================================
# Roofs
# ===========================================================================
def _draw_tiled_roof(surf, cx, base_y, half_w, roof_h, ridge_off=0,
                     tile_rows=8, tile_cols_per_side=10):
    """Two-slope terracotta roof with individual shingles."""
    ridge_x = cx + ridge_off
    ridge_y = base_y - roof_h

    # Backdrop (dark base)
    pygame.draw.polygon(surf, TILE_LO, [
        (cx - half_w - 6, base_y + 6),
        (cx + half_w + 6, base_y + 6),
        (ridge_x, ridge_y),
    ])

    # Left slope
    for r in range(tile_rows):
        t0 = r / tile_rows
        t1 = (r + 1) / tile_rows
        yy0 = base_y + (ridge_y - base_y) * t0
        yy1 = base_y + (ridge_y - base_y) * t1
        x_l0 = cx - half_w + (ridge_x - (cx - half_w)) * t0
        x_l1 = cx - half_w + (ridge_x - (cx - half_w)) * t1
        # Row of tiles
        for k in range(tile_cols_per_side):
            kt0 = k / tile_cols_per_side
            kt1 = (k + 1) / tile_cols_per_side
            x0 = x_l0 + (x_l1 - x_l0) * kt0
            x1 = x_l0 + (x_l1 - x_l0) * kt1
            col = _s(TILE, 1.0 + ((k + r) % 3 - 1) * 0.06)
            pygame.draw.polygon(surf, col, [
                (x0, yy0),
                (x1, yy0),
                (x1 + (ridge_x - cx + half_w) * (t1 - t0),
                 yy1),
                (x0 + (ridge_x - cx + half_w) * (t1 - t0),
                 yy1),
            ])
            # Tile highlight
            pygame.draw.line(surf, TILE_HI,
                             (x0 + 1, yy0 + 1),
                             (x0 + 1 + (ridge_x - cx + half_w) * (t1 - t0),
                              yy1 + 1), 1)
        # Row separator shadow
        pygame.draw.line(surf, TILE_EDGE,
                         (x_l0, yy0 + 1),
                         (x_l1, yy1 + 1), 1)

    # Right slope
    for r in range(tile_rows):
        t0 = r / tile_rows
        t1 = (r + 1) / tile_rows
        yy0 = base_y + (ridge_y - base_y) * t0
        yy1 = base_y + (ridge_y - base_y) * t1
        x_r0 = cx + half_w + (ridge_x - (cx + half_w)) * t0
        x_r1 = cx + half_w + (ridge_x - (cx + half_w)) * t1
        for k in range(tile_cols_per_side):
            kt0 = k / tile_cols_per_side
            kt1 = (k + 1) / tile_cols_per_side
            x0 = x_r0 + (x_r1 - x_r0) * kt0
            x1 = x_r0 + (x_r1 - x_r0) * kt1
            col = _s(TILE_LO, 1.0 + ((k + r) % 3 - 1) * 0.05)
            pygame.draw.polygon(surf, col, [
                (x0, yy0),
                (x1, yy0),
                (x1 + (ridge_x - cx - half_w) * (t1 - t0), yy1),
                (x0 + (ridge_x - cx - half_w) * (t1 - t0), yy1),
            ])
        pygame.draw.line(surf, TILE_EDGE,
                         (x_r0, yy0 + 1), (x_r1, yy1 + 1), 1)

    # Ridge cap
    pygame.draw.line(surf, TILE_HI,
                     (ridge_x - half_w // 3, ridge_y + 2),
                     (ridge_x + half_w // 3, ridge_y + 2), 3)
    pygame.draw.line(surf, TILE_EDGE,
                     (ridge_x - half_w // 3, ridge_y + 4),
                     (ridge_x + half_w // 3, ridge_y + 4), 1)

    # Eaves shadow
    pygame.draw.line(surf, TILE_EDGE,
                     (cx - half_w - 4, base_y + 6),
                     (cx + half_w + 4, base_y + 6), 1)


def _draw_thatch_roof(surf, cx, base_y, half_w, roof_h, ridge_off=0):
    ridge_x = cx + ridge_off
    ridge_y = base_y - roof_h
    rng = random.Random(int(cx * 1000) ^ int(base_y))

    # Base shapes
    pygame.draw.polygon(surf, THATCH_LO, [
        (cx - half_w - 8, base_y + 8),
        (cx + half_w + 8, base_y + 8),
        (ridge_x, ridge_y),
    ])
    pygame.draw.polygon(surf, THATCH, [
        (cx - half_w - 4, base_y + 4),
        (cx + half_w + 4, base_y + 4),
        (ridge_x, ridge_y),
    ])
    # Left slope lighter
    pygame.draw.polygon(surf, _s(THATCH, 1.06), [
        (cx - half_w - 4, base_y + 4),
        (ridge_x, ridge_y),
        (ridge_x, ridge_y + 6),
        (cx - 2, base_y + 4),
    ])
    # Bristle texture
    for _ in range(180):
        side = rng.choice([-1, 1])
        t = rng.random()
        px = int(cx + side * half_w * t)
        py = int(base_y + (ridge_y - base_y) * rng.random())
        col = _s(THATCH_HI if rng.random() < 0.5 else THATCH_LO,
                 1.0 + rng.uniform(-0.10, 0.10))
        pygame.draw.line(surf, col,
                         (px, py), (px + rng.randint(-2, 2), py + 3), 1)
    # Ridge
    pygame.draw.line(surf, THATCH_HI,
                     (ridge_x - half_w // 3, ridge_y + 3),
                     (ridge_x + half_w // 3, ridge_y + 3), 3)
    pygame.draw.line(surf, THATCH_EDGE,
                     (cx - half_w - 4, base_y + 4),
                     (cx + half_w + 4, base_y + 4), 1)


def _draw_hip_roof(surf, cx, base_y, half_w, half_d, roof_h):
    """Four-sided pyramidal roof."""
    apex = (cx, base_y - half_d - roof_h)

    # Left face
    pygame.draw.polygon(surf, TILE, [
        (cx - half_w, base_y),
        apex,
        (cx, base_y - half_d),
    ])
    # Right face
    pygame.draw.polygon(surf, TILE_LO, [
        (cx + half_w, base_y),
        apex,
        (cx, base_y - half_d),
    ])
    # Back-left face (darker)
    pygame.draw.polygon(surf, _s(TILE_LO, 0.85), [
        (cx - half_w, base_y),
        apex,
        (cx, base_y + half_d),
    ])
    # Back-right face (darkest)
    pygame.draw.polygon(surf, _s(TILE_LO, 0.70), [
        (cx + half_w, base_y),
        apex,
        (cx, base_y + half_d),
    ])
    # Ridge lines
    pygame.draw.line(surf, TILE_HI,
                     apex, (cx - half_w, base_y), 1)
    pygame.draw.line(surf, TILE_HI,
                     apex, (cx + half_w, base_y), 1)
    pygame.draw.line(surf, TILE_EDGE,
                     apex, (cx, base_y - half_d), 1)
    pygame.draw.line(surf, TILE_EDGE,
                     apex, (cx, base_y + half_d), 1)


# ===========================================================================
# Foundation
# ===========================================================================
def _draw_foundation(surf, cx, base_y, rx, ry, height=14):
    top = [
        (cx, base_y - ry),
        (cx + rx, base_y),
        (cx, base_y + ry),
        (cx - rx, base_y),
    ]
    # SW side
    pygame.draw.polygon(surf, STONE_LO, [
        top[3], top[2],
        (cx, base_y + ry + height),
        (cx - rx, base_y + height),
    ])
    # SE side
    pygame.draw.polygon(surf, STONE_MID, [
        top[2], top[1],
        (cx + rx, base_y + height),
        (cx, base_y + ry + height),
    ])
    # Top
    pygame.draw.polygon(surf, STONE, top)
    # Stone block lines
    for i in range(1, rx // 10):
        px = cx - rx + i * 10
        pygame.draw.line(surf, STONE_EDGE,
                         (px, base_y - ry + (px - (cx - rx)) // 2),
                         (px, base_y + ry - (rx - (px - (cx - rx))))[:2] if False else
                         (px, base_y + ry - (px - (cx - rx)) // 2 - 2), 1)
    # Top edge
    pygame.draw.polygon(surf, STONE_EDGE, top, 1)
    # Contact shadow
    _shadow(surf, cx, base_y + ry + height - 3, rx * 0.9, 8, alpha=60)


# ===========================================================================
# Props
# ===========================================================================
def _draw_barrel(surf, x, y, w=12, h=16):
    pygame.draw.polygon(surf, WOOD_MID, [
        (x - w // 2, y - h),
        (x + w // 2, y - h),
        (x + w // 2 - 1, y),
        (x - w // 2 + 1, y),
    ])
    pygame.draw.polygon(surf, WOOD, [
        (x - w // 2 + 2, y - h),
        (x + w // 2 - 2, y - h),
        (x + w // 2 - 3, y),
        (x - w // 2 + 3, y),
    ])
    for yy in (y - h + 2, y - h // 2, y - 2):
        pygame.draw.line(surf, IRON_LO,
                         (x - w // 2, yy), (x + w // 2, yy), 1)
        pygame.draw.line(surf, IRON,
                         (x - w // 2, yy - 1), (x + w // 2, yy - 1), 1)
    # Top lid
    pygame.draw.ellipse(surf, WOOD_LO,
                        (x - w // 2, y - h - 2, w, 4))


def _draw_crate(surf, x, y, w, h):
    pygame.draw.rect(surf, WOOD_MID, (x - w // 2, y - h, w, h))
    pygame.draw.rect(surf, WOOD, (x - w // 2 + 1, y - h + 1, w - 2, h - 2))
    # Planks
    pygame.draw.line(surf, WOOD_LO, (x - w // 2 + 1, y - h // 2),
                     (x + w // 2 - 1, y - h // 2), 1)
    # Diagonal brace
    pygame.draw.line(surf, WOOD_LO, (x - w // 2 + 1, y - 2),
                     (x + w // 2 - 1, y - h + 1), 1)
    pygame.draw.rect(surf, WOOD_EDGE,
                     (x - w // 2, y - h, w, h), 1)


def _draw_sack(surf, x, y, w, h):
    pygame.draw.ellipse(surf, THATCH, (x - w // 2, y - h, w, h))
    pygame.draw.ellipse(surf, THATCH_LO, (x - w // 2, y - h, w, h), 1)
    pygame.draw.arc(surf, THATCH_HI,
                    pygame.Rect(x - w // 2, y - h - 2, w, 6),
                    math.pi, 2 * math.pi, 1)


def _draw_fence(surf, x0, y0, x1, y1, posts=6):
    for i in range(posts):
        t = i / (posts - 1)
        px = int(x0 + (x1 - x0) * t)
        py = int(y0 + (y1 - y0) * t)
        pygame.draw.line(surf, WOOD_LO, (px, py - 14), (px, py), 2)
    pygame.draw.line(surf, WOOD, (x0, y0 - 8), (x1, y1 - 8), 1)
    pygame.draw.line(surf, WOOD, (x0, y0 - 3), (x1, y1 - 3), 1)


# ===========================================================================
# BUILDINGS
# ===========================================================================
def _make_town_center(rng):
    W, H = 340, 320
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    base_y = H - 30

    _shadow(surf, cx, base_y + 8, 130, 30, alpha=110)
    _draw_foundation(surf, cx, base_y, 138, 36, height=18)

    # ---- Main keep ----
    keep_cx = cx
    keep_w = 168
    keep_h = 100
    keep_top = base_y - 24 - keep_h
    _draw_stone_wall(surf, keep_cx, keep_top, keep_w, keep_h, rng,
                     window_specs=[(-46, 20, 10, 12),
                                   (-16, 20, 10, 12),
                                   ( 20, 20, 10, 12),
                                   ( 50, 20, 10, 12),
                                   (-46, 62, 10, 12),
                                   ( 50, 62, 10, 12)],
                     door_spec=(-16, -2, 32, 40),
                     rows=7)

    # Central keep roof
    _draw_tiled_roof(surf, keep_cx, keep_top + 12, keep_w // 2 + 12, 62,
                     ridge_off=0)

    # ---- Left wing: plaster house ----
    wing_cx = cx - 100
    wing_w = 76
    wing_h = 62
    wing_top = base_y - 10 - wing_h
    _draw_plaster_wall(surf, wing_cx, wing_top, wing_w, wing_h, rng,
                       window_specs=[(-12, 22, 8, 10)],
                       door_spec=(-10, -2, 20, 26))
    _draw_thatch_roof(surf, wing_cx, wing_top + 10, wing_w // 2 + 10, 40)

    # ---- Right wing: defensive tower ----
    tower_cx = cx + 106
    tower_w = 54
    tower_h = 110
    tower_top = base_y - 8 - tower_h
    _draw_stone_wall(surf, tower_cx, tower_top, tower_w, tower_h, rng,
                     window_specs=[(-4, 30, 6, 14),
                                   (-4, 62, 6, 14)],
                     rows=8)

    # Battlements
    batt_y = tower_top + 12
    batt_h = 14
    for bx in range(tower_cx - tower_w // 2 - 3,
                    tower_cx + tower_w // 2 - 4, 11):
        pygame.draw.rect(surf, STONE, (bx, batt_y - batt_h, 8, batt_h))
        pygame.draw.rect(surf, STONE_HI, (bx, batt_y - batt_h, 8, 3))
        pygame.draw.rect(surf, STONE_EDGE, (bx, batt_y - batt_h, 8, batt_h), 1)

    # Tower cap (hip roof)
    _draw_hip_roof(surf, tower_cx, batt_y - batt_h + 4,
                   tower_w // 2 + 6, 14, 26)

    # Flag pole base (WorldFx draws the waving cloth)
    pygame.draw.rect(surf, WOOD_LO,
                     (tower_cx - 1, batt_y - batt_h - 12, 3, 12))

    # Chimney
    _draw_chimney_base(surf, cx + 34, keep_top - 18, 16, 46, rng)

    # Props: barrels, crates, bushes
    _draw_barrel(surf, cx - 100, base_y + 14, 12, 16)
    _draw_crate(surf, cx - 82, base_y + 12, 18, 16)
    _draw_barrel(surf, cx + 100, base_y + 14, 12, 16)
    _draw_bush(surf, cx - 130, base_y + 6)
    _draw_bush(surf, cx + 126, base_y + 8)
    _draw_grass_clump(surf, cx - 60, base_y + 18)
    _draw_grass_clump(surf, cx + 60, base_y + 18)

    return surf


def _draw_chimney_base(surf, x, y, w, h, rng):
    """Stone chimney; smoke is drawn by WorldFx on top."""
    _shadow(surf, x + w // 2, y + h + 4, w * 1.2, 5, alpha=70)
    # Body
    pygame.draw.rect(surf, STONE_MID, (x, y, w, h))
    pygame.draw.rect(surf, STONE, (x + 1, y + 1, w - 2, h - 2))
    # Stone block lines
    for yy in range(y + 4, y + h, 6):
        pygame.draw.line(surf, STONE_EDGE, (x, yy), (x + w, yy), 1)
    for k in range(1, 5):
        xx = x + (w * k) // 5
        pygame.draw.line(surf, STONE_EDGE, (xx, y + 4 + k % 2 * 3),
                         (xx, y + h), 1)
    # Highlight
    pygame.draw.line(surf, STONE_HI, (x + 1, y + 1), (x + 1, y + h - 1), 1)
    # Dark right side
    pygame.draw.line(surf, STONE_LO, (x + w - 2, y + 1),
                     (x + w - 2, y + h - 1), 2)
    # Cap
    pygame.draw.rect(surf, STONE_LO, (x - 3, y - 5, w + 6, 6))
    pygame.draw.rect(surf, STONE, (x - 3, y - 5, w + 6, 3))
    pygame.draw.rect(surf, STONE_EDGE, (x - 3, y - 5, w + 6, 6), 1)


def _draw_bush(surf, x, y):
    pygame.draw.ellipse(surf, (76, 118, 58), (x - 11, y - 10, 22, 14))
    pygame.draw.ellipse(surf, (108, 156, 78), (x - 8, y - 12, 16, 10))
    pygame.draw.ellipse(surf, (140, 190, 108), (x - 5, y - 12, 8, 5))


def _draw_grass_clump(surf, x, y):
    rng = random.Random(int(x * 1000) ^ int(y))
    for _ in range(8):
        bx = x + rng.randint(-6, 6)
        by = y + rng.randint(-2, 2)
        col = rng.choice([(92, 142, 68), (120, 168, 84), (70, 112, 52)])
        pygame.draw.line(surf, col, (bx, by),
                         (bx + rng.randint(-1, 1), by - rng.randint(3, 7)), 1)


# ---------------------------------------------------------------------------
def _make_house(rng):
    W, H = 210, 205
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    base_y = H - 20

    _shadow(surf, cx, base_y + 6, 82, 22, alpha=100)
    _draw_foundation(surf, cx, base_y, 84, 22, height=12)

    wall_w = 128
    wall_h = 68
    top_y = base_y - 14 - wall_h

    _draw_plaster_wall(surf, cx, top_y, wall_w, wall_h, rng,
                       window_specs=[(-30, 22, 12, 12),
                                     ( 18, 22, 12, 12)],
                       door_spec=(-10, -2, 20, 30))

    _draw_thatch_roof(surf, cx, top_y + 10, wall_w // 2 + 12, 50)

    # Chimney
    _draw_chimney_base(surf, cx + 32, top_y - 20, 12, 36, rng)

    # Front fence
    _draw_fence(surf, cx - 46, base_y + 18, cx + 46, base_y + 18, posts=7)
    _draw_bush(surf, cx - 72, base_y + 8)
    _draw_grass_clump(surf, cx + 66, base_y + 12)

    return surf


# ---------------------------------------------------------------------------
def _make_farm(rng):
    W, H = 300, 168
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    base_y = H - 22

    _shadow(surf, cx, base_y + 6, 132, 28, alpha=85)

    # Tilled earth diamond
    hw, hd = 132, 32
    earth = (108, 74, 44)
    earth_dark = (72, 48, 26)
    earth_light = (152, 108, 68)

    top = [(cx, base_y - hd), (cx + hw, base_y),
           (cx, base_y + hd), (cx - hw, base_y)]
    pygame.draw.polygon(surf, earth, top)
    pygame.draw.polygon(surf, earth_dark, [
        top[3], top[2],
        (cx, base_y + hd + 10), (cx - hw, base_y + 10)])
    pygame.draw.polygon(surf, _s(earth, 0.95), [
        top[2], top[1],
        (cx + hw, base_y + 10), (cx, base_y + hd + 10)])

    # Furrows with wheat
    for band_off in (-16, 0, 16):
        for i in range(1, 8):
            t = i / 8.0
            # Left half of the diamond
            x0 = cx - int(hw * t)
            y0 = base_y - int(hd * t) + band_off // 2
            for k in range(8):
                kt = k / 7.0
                px = int(x0 + (cx - x0) * kt)
                py = int(y0 + (base_y + band_off // 2 - y0) * kt)
                col = _s(WHEAT, 0.9 + rng.uniform(-0.1, 0.1))
                pygame.draw.line(surf, col,
                                 (px, py + 4), (px, py - 6), 2)
                pygame.draw.line(surf, WHEAT_HI,
                                 (px - 1, py - 4), (px + 1, py - 4), 1)
                pygame.draw.line(surf, WHEAT_HI,
                                 (px - 1, py - 6), (px + 1, py - 6), 1)
            # Right half
            x1 = cx + int(hw * t)
            y1 = base_y + int(hd * t) + band_off // 2
            for k in range(8):
                kt = k / 7.0
                px = int(cx + (x1 - cx) * kt)
                py = int(base_y + band_off // 2 + (y1 - base_y - band_off // 2) * kt)
                col = _s(WHEAT, 0.9 + rng.uniform(-0.1, 0.1))
                pygame.draw.line(surf, col,
                                 (px, py + 4), (px, py - 6), 2)
                pygame.draw.line(surf, WHEAT_HI,
                                 (px - 1, py - 4), (px + 1, py - 4), 1)

    # Scarecrow
    sx = cx + 92
    sy = base_y - 6
    pygame.draw.line(surf, WOOD_LO, (sx, sy - 40), (sx, sy), 2)
    pygame.draw.line(surf, WOOD_LO, (sx - 12, sy - 30), (sx + 12, sy - 30), 2)
    pygame.draw.circle(surf, (212, 176, 108), (sx, sy - 44), 6)
    pygame.draw.circle(surf, (200, 150, 90), (sx, sy - 44), 6, 1)
    pygame.draw.circle(surf, (40, 28, 20), (sx - 2, sy - 45), 1)
    pygame.draw.circle(surf, (40, 28, 20), (sx + 2, sy - 45), 1)
    pygame.draw.polygon(surf, BANNER, [
        (sx - 7, sy - 52), (sx + 7, sy - 52), (sx, sy - 60)])
    pygame.draw.line(surf, PLASTER, (sx - 6, sy - 34),
                     (sx + 6, sy - 26), 3)

    # Wheelbarrow
    wx = cx - 100
    wy = base_y + 4
    pygame.draw.polygon(surf, WOOD_MID, [
        (wx - 14, wy - 8), (wx + 14, wy - 8),
        (wx + 10, wy + 2), (wx - 10, wy + 2)])
    pygame.draw.circle(surf, WOOD_LO, (wx, wy + 4), 4)
    pygame.draw.line(surf, WOOD_LO, (wx - 10, wy - 8),
                     (wx - 18, wy - 16), 2)
    pygame.draw.line(surf, WOOD_LO, (wx + 10, wy - 8),
                     (wx + 18, wy - 16), 2)

    # Hay bale
    hx = cx - 20
    hy = base_y + 20
    pygame.draw.rect(surf, THATCH, (hx - 14, hy - 12, 28, 14))
    pygame.draw.rect(surf, THATCH_LO, (hx - 14, hy - 12, 28, 14), 1)
    for i in range(4):
        pygame.draw.line(surf, THATCH_HI,
                         (hx - 14, hy - 12 + i * 3),
                         (hx + 14, hy - 12 + i * 3), 1)

    return surf


# ---------------------------------------------------------------------------
def _make_storage(rng):
    W, H = 220, 200
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    base_y = H - 22

    _shadow(surf, cx, base_y + 6, 88, 24, alpha=100)
    _draw_foundation(surf, cx, base_y, 90, 24, height=12)

    wall_w = 140
    wall_h = 74
    top_y = base_y - 16 - wall_h
    _draw_wood_wall(surf, cx, top_y, wall_w, wall_h, rng,
                    window_specs=[(-34, 24, 12, 12),
                                  (34, 24, 12, 12)],
                    door_spec=(-18, -2, 36, 34))

    _draw_tiled_roof(surf, cx, top_y + 12, wall_w // 2 + 14, 48)

    # Stacked crates and barrels
    _draw_crate(surf, cx - 86, base_y + 20, 24, 20)
    _draw_crate(surf, cx - 62, base_y + 18, 20, 16)
    _draw_crate(surf, cx - 72, base_y + 2, 20, 18)
    _draw_barrel(surf, cx + 82, base_y + 20, 14, 18)
    _draw_barrel(surf, cx + 100, base_y + 18, 12, 16)
    _draw_sack(surf, cx - 104, base_y + 18, 16, 14)
    _draw_sack(surf, cx + 106, base_y + 22, 14, 12)

    return surf


# ---------------------------------------------------------------------------
def _make_barracks(rng):
    W, H = 300, 260
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    base_y = H - 24

    _shadow(surf, cx, base_y + 8, 122, 30, alpha=105)
    _draw_foundation(surf, cx, base_y, 124, 30, height=14)

    wall_w = 184
    wall_h = 88
    top_y = base_y - 18 - wall_h
    _draw_stone_wall(surf, cx, top_y, wall_w, wall_h, rng,
                     window_specs=[(-58, 20, 14, 16),
                                   (-24, 20, 14, 16),
                                   ( 24, 20, 14, 16),
                                   ( 58, 20, 14, 16),
                                   (-58, 58, 14, 16),
                                   ( 58, 58, 14, 16)],
                     door_spec=(-24, -2, 48, 46),
                     rows=7)

    # Roof
    _draw_tiled_roof(surf, cx, top_y + 12, wall_w // 2 + 16, 60)

    # Wooden beams over the walls
    hw = wall_w // 2
    for bx in (cx - hw + 6, cx - hw // 3, cx + hw // 3, cx + hw - 6):
        pygame.draw.line(surf, WOOD_LO,
                         (bx, top_y + 8), (bx, base_y - 18), 2)
    pygame.draw.line(surf, WOOD_LO,
                     (cx - hw + 4, top_y + 8),
                     (cx + hw - 4, top_y + 8), 2)

    # Banners on the roof
    _draw_roof_banner(surf, cx - 54, top_y + 12 - 20, 22, 58, BANNER)
    _draw_roof_banner(surf, cx + 54, top_y + 12 - 20, 22, 58, BANNER)

    # Weapon rack outside
    rack_x = cx + 116
    rack_y = base_y + 10
    pygame.draw.line(surf, WOOD_LO, (rack_x, rack_y - 28),
                     (rack_x, rack_y + 10), 3)
    for i, dy in enumerate((0, 10, 20)):
        pygame.draw.line(surf, IRON_LO,
                         (rack_x - 12, rack_y - 22 + dy),
                         (rack_x - 2, rack_y - 28 + dy), 2)
        pygame.draw.polygon(surf, IRON, [
            (rack_x - 4, rack_y - 28 + dy),
            (rack_x - 2, rack_y - 32 + dy),
            (rack_x - 2, rack_y - 24 + dy)])
    # Shield on the rack
    pygame.draw.ellipse(surf, BANNER,
                        (rack_x + 6, rack_y - 26, 16, 20))
    pygame.draw.ellipse(surf, BANNER_LO,
                        (rack_x + 6, rack_y - 26, 16, 20), 1)
    pygame.draw.line(surf, GOLD,
                     (rack_x + 14, rack_y - 24),
                     (rack_x + 14, rack_y - 8), 1)
    pygame.draw.line(surf, GOLD,
                     (rack_x + 8, rack_y - 16),
                     (rack_x + 20, rack_y - 16), 1)

    # Training dummy
    dx = cx - 122
    dy = base_y + 10
    pygame.draw.line(surf, WOOD_LO, (dx, dy - 32), (dx, dy + 10), 3)
    pygame.draw.line(surf, WOOD_LO, (dx - 12, dy - 24), (dx + 12, dy - 24), 3)
    pygame.draw.circle(surf, THATCH_HI, (dx, dy - 38), 6)
    pygame.draw.circle(surf, THATCH_LO, (dx, dy - 38), 6, 1)
    pygame.draw.line(surf, THATCH_LO, (dx - 3, dy - 34),
                     (dx + 3, dy - 34), 1)

    return surf


def _draw_roof_banner(surf, x, y_top, cloth_w, cloth_h, colour):
    # Pole
    pygame.draw.line(surf, WOOD_LO, (x, y_top), (x, y_top + cloth_h), 2)
    pygame.draw.line(surf, WOOD, (x + 1, y_top), (x + 1, y_top + cloth_h), 1)
    # Cloth
    pts = [
        (x + 2, y_top + 2),
        (x + cloth_w, y_top + 6),
        (x + cloth_w - 2, y_top + cloth_h - 4),
        (x + 2, y_top + cloth_h),
    ]
    pygame.draw.polygon(surf, colour, pts)
    pygame.draw.polygon(surf, _s(colour, 0.6), pts, 1)
    # Emblem
    pygame.draw.circle(surf, GOLD,
                       (x + cloth_w // 2 + 1, y_top + cloth_h // 2), 3)
    pygame.draw.circle(surf, GOLD_LO,
                       (x + cloth_w // 2 + 1, y_top + cloth_h // 2), 3, 1)


# ---------------------------------------------------------------------------
def _make_archery_range(rng):
    W, H = 280, 240
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    base_y = H - 24

    _shadow(surf, cx, base_y + 6, 112, 26, alpha=95)
    _draw_foundation(surf, cx, base_y, 116, 26, height=12)

    # Open-sided structure: back wall + roof, supported by posts
    wall_w = 180
    wall_h = 66
    top_y = base_y - 16 - wall_h
    _draw_wood_wall(surf, cx, top_y, wall_w, wall_h, rng,
                    window_specs=[(-46, 24, 10, 12),
                                  (46, 24, 10, 12)])

    # Roof
    _draw_tiled_roof(surf, cx, top_y + 10, wall_w // 2 + 16, 46)

    # Front support posts
    for fx in (cx - wall_w // 2 + 8, cx - 20, cx + 20,
               cx + wall_w // 2 - 8):
        pygame.draw.rect(surf, WOOD_LO, (fx - 3, top_y + 12, 6, 46))
        pygame.draw.rect(surf, WOOD, (fx - 2, top_y + 12, 3, 46))

    # Target on a stand
    tx = cx + 8
    ty = base_y - 4
    for r, col in ((20, (216, 200, 176)),
                   (16, (176, 40, 36)),
                   (12, (232, 232, 224)),
                   (8,  (176, 40, 36)),
                   (3,  (32, 24, 20))):
        pygame.draw.circle(surf, col, (tx, ty), r)
    # Stand
    pygame.draw.line(surf, WOOD_LO, (tx - 12, ty + 6),
                     (tx - 18, ty + 16), 2)
    pygame.draw.line(surf, WOOD_LO, (tx + 12, ty + 6),
                     (tx + 18, ty + 16), 2)

    # Quiver rack
    qx = cx - 96
    qy = base_y + 12
    pygame.draw.line(surf, WOOD_LO, (qx, qy - 24), (qx, qy + 8), 2)
    for i in range(3):
        qy2 = qy - 20 + i * 6
        for j in range(3):
            pygame.draw.line(surf, WOOD_LO,
                             (qx + 2 + j * 3, qy2),
                             (qx + 2 + j * 3, qy2 - 8), 1)
            pygame.draw.circle(surf, BANNER,
                               (qx + 2 + j * 3, qy2 - 9), 1)

    # Hay bales
    _draw_sack(surf, cx + 100, base_y + 10, 20, 16)
    _draw_sack(surf, cx + 112, base_y + 16, 18, 14)

    # Bows leaning against the wall
    for i in range(2):
        bx = cx + 66 + i * 12
        by = base_y + 4
        pygame.draw.arc(surf, WOOD_MID,
                        pygame.Rect(bx - 4, by - 24, 8, 24),
                        -1.4, 1.4, 2)

    return surf


# ---------------------------------------------------------------------------
def _make_stable(rng):
    W, H = 280, 240
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    base_y = H - 24

    _shadow(surf, cx, base_y + 6, 112, 26, alpha=95)
    _draw_foundation(surf, cx, base_y, 116, 26, height=12)

    wall_w = 180
    wall_h = 76
    top_y = base_y - 16 - wall_h
    _draw_wood_wall(surf, cx, top_y, wall_w, wall_h, rng,
                    window_specs=[(-46, 26, 10, 12),
                                  (46, 26, 10, 12)])

    # Large stable door (open arch) — replace default door
    door_x = cx - 26
    door_y = base_y - 54
    door_w = 52
    door_h = 44
    pygame.draw.rect(surf, (34, 24, 18), (door_x, door_y, door_w, door_h))
    pygame.draw.ellipse(surf, (34, 24, 18),
                        (door_x, door_y - 10, door_w, 22))
    pygame.draw.ellipse(surf, WOOD_LO,
                        (door_x - 2, door_y - 12, door_w + 4, 24), 2)
    pygame.draw.rect(surf, WOOD_LO, (door_x, door_y, door_w, door_h), 2)
    # Horse head silhouette inside
    hx = door_x + door_w // 2
    hy = door_y + door_h // 2 + 4
    pygame.draw.ellipse(surf, (60, 42, 28), (hx - 10, hy - 16, 14, 10))
    pygame.draw.ellipse(surf, (60, 42, 28), (hx + 2, hy - 26, 7, 14))
    pygame.draw.circle(surf, (60, 42, 28), (hx + 6, hy - 28), 4)
    pygame.draw.circle(surf, (200, 160, 100), (hx + 6, hy - 28), 1)

    # Roof
    _draw_tiled_roof(surf, cx, top_y + 10, wall_w // 2 + 16, 52)

    # Hay pile
    hay_x = cx + 106
    hay_y = base_y + 14
    pygame.draw.ellipse(surf, THATCH, (hay_x - 20, hay_y - 18, 40, 18))
    pygame.draw.ellipse(surf, THATCH_LO, (hay_x - 20, hay_y - 18, 40, 18), 2)
    for _ in range(14):
        lx = hay_x + rng.randint(-16, 16)
        ly = hay_y - rng.randint(3, 14)
        pygame.draw.line(surf, THATCH_HI,
                         (lx, ly), (lx + rng.randint(-1, 1), ly - 4), 1)

    # Fence on the left
    _draw_fence(surf, cx - 128, base_y + 18, cx - 96, base_y + 18, posts=4)
    _draw_barrel(surf, cx - 118, base_y + 4, 12, 16)

    return surf


# ---------------------------------------------------------------------------
def _make_tower(rng):
    W, H = 140, 240
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    base_y = H - 22

    _shadow(surf, cx, base_y + 6, 48, 14, alpha=110)
    _draw_foundation(surf, cx, base_y, 52, 14, height=10)

    tower_w = 68
    tower_h = 130
    tower_top = base_y - 12 - tower_h
    _draw_stone_wall(surf, cx, tower_top, tower_w, tower_h, rng,
                     window_specs=[(-4, 32, 6, 14),
                                   (-4, 68, 6, 14),
                                   (-4, 104, 6, 14)],
                     rows=12)

    # Corner quoins
    hw = tower_w // 2
    for yy in range(tower_top + 10, base_y - 4, 12):
        pygame.draw.rect(surf, STONE, (cx - hw - 3, yy, 7, 9))
        pygame.draw.rect(surf, STONE_HI, (cx - hw - 3, yy, 7, 2))
        pygame.draw.rect(surf, STONE, (cx + hw - 4, yy, 7, 9))
        pygame.draw.rect(surf, STONE_HI, (cx + hw - 4, yy, 7, 2))

    # Battlements
    batt_y = tower_top + 12
    batt_h = 16
    for bx in range(cx - hw - 3, cx + hw - 5, 12):
        pygame.draw.rect(surf, STONE, (bx, batt_y - batt_h, 9, batt_h))
        pygame.draw.rect(surf, STONE_HI, (bx, batt_y - batt_h, 9, 3))
        pygame.draw.rect(surf, STONE_EDGE, (bx, batt_y - batt_h, 9, batt_h), 1)

    # Roof cap
    _draw_hip_roof(surf, cx, batt_y - batt_h + 6, tower_w // 2 + 8, 14, 28)

    # Flag pole base
    pygame.draw.rect(surf, WOOD_LO,
                     (cx - 1, batt_y - batt_h - 14, 3, 14))

    return surf


# ---------------------------------------------------------------------------
def _make_blacksmith(rng):
    W, H = 280, 250
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    base_y = H - 22

    _shadow(surf, cx, base_y + 8, 112, 26, alpha=105)
    _draw_foundation(surf, cx, base_y, 116, 26, height=14)

    wall_w = 168
    wall_h = 82
    top_y = base_y - 16 - wall_h
    _draw_stone_wall(surf, cx, top_y, wall_w, wall_h, rng,
                     window_specs=[(-52, 26, 12, 14),
                                   (52, 26, 12, 14)],
                     door_spec=(-54, -2, 26, 34),
                     rows=6)

    # Glowing forge opening on the right
    forge_x = cx + 10
    forge_y = base_y - 44
    pygame.draw.rect(surf, (30, 20, 14), (forge_x, forge_y, 30, 32))
    pygame.draw.rect(surf, (60, 30, 14), (forge_x + 1, forge_y + 1, 28, 30))
    pygame.draw.rect(surf, (220, 100, 44), (forge_x + 4, forge_y + 8, 22, 20))
    pygame.draw.rect(surf, (255, 180, 80), (forge_x + 7, forge_y + 14, 16, 12))
    pygame.draw.rect(surf, (255, 240, 180), (forge_x + 10, forge_y + 18, 10, 6))
    # Iron frame around forge
    pygame.draw.rect(surf, IRON_LO, (forge_x - 2, forge_y - 2, 34, 36), 2)
    # Sparks
    for _ in range(10):
        sx = forge_x + rng.randint(2, 28)
        sy = forge_y + rng.randint(-6, 8)
        pygame.draw.circle(surf, (255, 210, 120), (sx, sy), 1)

    # Roof
    _draw_tiled_roof(surf, cx, top_y + 12, wall_w // 2 + 14, 56)

    # Chimney (bigger than the house)
    _draw_chimney_base(surf, cx + 48, top_y - 24, 18, 50, rng)

    # Anvil in front
    ax = cx + 82
    ay = base_y + 14
    pygame.draw.polygon(surf, (58, 52, 48), [
        (ax - 16, ay - 10), (ax + 16, ay - 10),
        (ax + 12, ay + 2), (ax - 12, ay + 2)])
    pygame.draw.polygon(surf, (40, 36, 34), [
        (ax - 12, ay + 2), (ax + 12, ay + 2),
        (ax + 8, ay + 8), (ax - 8, ay + 8)])
    pygame.draw.rect(surf, (58, 52, 48), (ax - 10, ay + 8, 20, 5))
    # Hammer on the anvil
    pygame.draw.line(surf, WOOD_LO, (ax, ay - 12), (ax + 10, ay - 20), 2)
    pygame.draw.rect(surf, IRON, (ax + 8, ay - 24, 8, 6))

    # Water trough
    tx = cx - 100
    ty = base_y + 10
    pygame.draw.polygon(surf, WOOD_LO, [
        (tx - 20, ty), (tx + 20, ty),
        (tx + 16, ty + 14), (tx - 16, ty + 14)])
    pygame.draw.polygon(surf, (70, 120, 160), [
        (tx - 18, ty + 1), (tx + 18, ty + 1),
        (tx + 14, ty + 12), (tx - 14, ty + 12)])
    pygame.draw.line(surf, (200, 220, 240),
                     (tx - 12, ty + 4), (tx + 12, ty + 4), 1)

    return surf


# ---------------------------------------------------------------------------
def _make_market(rng):
    W, H = 290, 230
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    base_y = H - 24

    _shadow(surf, cx, base_y + 6, 118, 26, alpha=90)
    _draw_foundation(surf, cx, base_y, 122, 26, height=10)

    # Three market stalls
    stalls = [
        (cx - 72, (168, 56, 48), (204, 66, 60), "fruit"),
        (cx,      (72, 116, 176), (150, 190, 220), "cloth"),
        (cx + 72, (96, 148, 84), (170, 200, 100), "veg"),
    ]
    for (scx, col, good, tag) in stalls:
        # Posts
        pygame.draw.rect(surf, WOOD_LO, (scx - 28, base_y - 66, 5, 66))
        pygame.draw.rect(surf, WOOD_LO, (scx + 24, base_y - 66, 5, 66))
        pygame.draw.rect(surf, WOOD, (scx - 27, base_y - 66, 2, 66))
        pygame.draw.rect(surf, WOOD, (scx + 25, base_y - 66, 2, 66))
        # Crossbeam
        pygame.draw.line(surf, WOOD_LO,
                         (scx - 28, base_y - 66), (scx + 28, base_y - 66), 3)
        # Awning
        pygame.draw.polygon(surf, col, [
            (scx - 34, base_y - 62),
            (scx + 34, base_y - 62),
            (scx + 28, base_y - 82),
            (scx - 28, base_y - 82)])
        # Stripe highlights
        for i in range(-2, 3):
            px = scx + i * 13
            pygame.draw.line(surf, _s(col, 1.28),
                             (px, base_y - 62), (px, base_y - 82), 1)
        # Awning shadow
        pygame.draw.line(surf, _s(col, 0.55),
                         (scx - 34, base_y - 62), (scx + 34, base_y - 62), 2)
        # Counter
        pygame.draw.polygon(surf, WOOD_MID, [
            (scx - 26, base_y - 20),
            (scx + 26, base_y - 20),
            (scx + 24, base_y - 6),
            (scx - 24, base_y - 6)])
        pygame.draw.polygon(surf, WOOD_LO, [
            (scx - 26, base_y - 20),
            (scx + 26, base_y - 20),
            (scx + 24, base_y - 6),
            (scx - 24, base_y - 6)], 2)
        # Goods
        if tag == "fruit":
            for i in range(4):
                x = scx - 14 + i * 9
                pygame.draw.circle(surf, good, (x, base_y - 24), 4)
                pygame.draw.circle(surf, _s(good, 1.3),
                                   (x - 1, base_y - 25), 1)
        elif tag == "cloth":
            for i in range(4):
                x = scx - 15 + i * 9
                pygame.draw.rect(surf, good, (x, base_y - 28, 7, 8))
                pygame.draw.rect(surf, _s(good, 0.7),
                                 (x, base_y - 28, 7, 8), 1)
        else:
            for i in range(4):
                x = scx - 14 + i * 9
                pygame.draw.circle(surf, good, (x, base_y - 24), 4)
                pygame.draw.circle(surf, _s(good, 1.3),
                                   (x - 1, base_y - 25), 1)

    # Sacks and crates
    _draw_sack(surf, cx - 106, base_y + 16, 18, 16)
    _draw_sack(surf, cx - 88, base_y + 18, 16, 14)
    _draw_crate(surf, cx + 100, base_y + 14, 22, 18)
    _draw_barrel(surf, cx + 122, base_y + 12, 12, 16)

    # Hanging sign on a pole
    pole_x = cx + 128
    pole_y = base_y - 90
    pygame.draw.line(surf, WOOD_LO, (pole_x, pole_y), (pole_x, base_y + 8), 3)
    pygame.draw.line(surf, WOOD_LO, (pole_x, pole_y), (pole_x - 20, pole_y), 2)
    pygame.draw.rect(surf, (150, 116, 74), (pole_x - 34, pole_y - 2, 22, 16))
    pygame.draw.rect(surf, (90, 66, 40), (pole_x - 34, pole_y - 2, 22, 16), 2)
    pygame.draw.circle(surf, GOLD, (pole_x - 23, pole_y + 6), 5)
    pygame.draw.circle(surf, GOLD_LO, (pole_x - 23, pole_y + 6), 5, 1)

    return surf


# ===========================================================================
# CACHE
# ===========================================================================
class BuildingSpriteCache:
    _cache = {}

    @classmethod
    def get(cls, kind):
        s = cls._cache.get(kind)
        if s is None:
            rng = random.Random(hash(kind) & 0x7FFFFFFF)
            s = _generate(kind, rng)
            cls._cache[kind] = s
        return s


def _generate(kind, rng):
    if kind == TOWN_CENTER:   return _make_town_center(rng)
    if kind == HOUSE:         return _make_house(rng)
    if kind == BARRACKS:      return _make_barracks(rng)
    if kind == ARCHERY_RANGE: return _make_archery_range(rng)
    if kind == STABLE:        return _make_stable(rng)
    if kind == STORAGE:       return _make_storage(rng)
    if kind == FARM:          return _make_farm(rng)
    if kind == TOWER:         return _make_tower(rng)
    if kind == BLACKSMITH:    return _make_blacksmith(rng)
    if kind == MARKET:        return _make_market(rng)
    return pygame.Surface((2, 2), pygame.SRCALPHA)