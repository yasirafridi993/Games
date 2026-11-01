"""Rich per-tile mountain sprites.

Five subtypes, chosen deterministically from the tile hash:
    0 SNOWY      jagged peaks with snow caps (altitude)
    1 ROCKY      bare rock, strata + cracks
    2 FORESTED   rocky peak with pine trees at the base
    3 MEDIUM     mixed rock / grass
    4 HILL       small grassy hill

Sprites are cached in an 8×8 pool (64 unique shapes) so a 64×64 map
never shows the same mountain silhouette twice on the same screen.
"""

import math
import random

import pygame

from . import config as C


# ---- rock palette (upper-left light) ---------------------------------------
ROCK_HI    = (212, 204, 190)
ROCK_TOP   = (182, 172, 158)
ROCK_UPPER = (154, 144, 130)
ROCK_MID   = (126, 116, 104)
ROCK_LOWER = (98, 88, 78)
ROCK_DEEP  = (70, 62, 56)
ROCK_EDGE  = (38, 34, 30)

SNOW_HI    = (252, 253, 255)
SNOW       = (232, 238, 244)
SNOW_SHADE = (196, 208, 220)

GRASS_HI   = (142, 188, 110)
GRASS      = (108, 156, 80)
GRASS_LO   = (72, 118, 54)

TREE_DARK  = (50, 80, 44)
TREE_MID   = (74, 116, 58)
TREE_HI    = (110, 154, 78)
TRUNK      = (68, 46, 28)


# ---- geometry --------------------------------------------------------------
_SPRITE_W = 168
_SPRITE_H = 220
_POOL_SIZE = 8
_POOL = {}


def get_mountain(col, row):
    key = (col % _POOL_SIZE, row % _POOL_SIZE)
    s = _POOL.get(key)
    if s is None:
        s = _build(key[0], key[1])
        _POOL[key] = s
    return s


# ---- helpers ---------------------------------------------------------------
def _s(c, f):
    return (max(0, min(255, int(c[0] * f))),
            max(0, min(255, int(c[1] * f))),
            max(0, min(255, int(c[2] * f))))


def _blend(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def _scatter(surf, rng, poly, base, n, var):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x0, x1 = int(min(xs)), int(max(xs))
    y0, y1 = int(min(ys)), int(max(ys))
    for _ in range(n):
        px = rng.randint(x0, x1)
        py = rng.randint(y0, y1)
        if _inside_poly(px, py, poly):
            surf.set_at((px, py), _s(base, 1.0 + rng.uniform(-var, var)))


def _inside_poly(x, y, poly):
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and \
           (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
            inside = not inside
        j = i
    return inside


# ---- peak rendering --------------------------------------------------------
def _draw_peak(surf, rng, poly, subtype, peak_h):
    """Draw one peak polygon with strata, facets, snow and outline."""
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x0, x1 = int(min(xs)), int(max(xs))
    y0, y1 = int(min(ys)), int(max(ys))
    pw = x1 - x0 + 1
    ph = y1 - y0 + 1
    if pw < 6 or ph < 6:
        return
    shifted = [(p[0] - x0, p[1] - y0) for p in poly]

    # Scratch canvas for masked detail
    scratch = pygame.Surface((pw, ph), pygame.SRCALPHA)

    # 1. Base rock with a top-down gradient
    pygame.draw.polygon(scratch, ROCK_MID, shifted)

    # 2. Strata bands (lighter at the top, darker at the base)
    n_bands = max(6, ph // 10)
    for i in range(n_bands):
        t = i / max(1, n_bands - 1)
        col = _blend(ROCK_HI, ROCK_DEEP, t)
        band_y = int(ph * i / n_bands)
        pygame.draw.line(scratch, col, (0, band_y), (pw - 1, band_y), 1)

    # 3. Angular rock facets
    n_facets = max(8, (pw * ph) // 300)
    for _ in range(n_facets):
        fx = rng.randint(0, pw - 1)
        fy = rng.randint(0, ph - 1)
        r = rng.randint(3, 8)
        col = _s(ROCK_MID, rng.uniform(0.80, 1.22))
        # Draw as a small tilted oval for rock-like irregularity
        pygame.draw.ellipse(scratch, col,
                            (fx - r, fy - r // 2, r * 2, r))

    # 4. Cracks
    for _ in range(rng.randint(2, 5)):
        c_x = rng.randint(2, pw - 3)
        c_y = rng.randint(2, ph - 3)
        c_len = rng.randint(6, 16)
        ang = rng.uniform(-0.4, 0.4) + math.pi / 2
        ex = int(c_x + math.cos(ang) * c_len)
        ey = int(c_y + math.sin(ang) * c_len)
        pygame.draw.line(scratch, ROCK_EDGE, (c_x, c_y), (ex, ey), 1)

    # 5. Snow cap for high peaks
    if subtype == 0 and peak_h > 130:
        snow_frac = rng.uniform(0.22, 0.34)
        snow_y = int(ph * snow_frac)
        pygame.draw.rect(scratch, SNOW, (0, 0, pw, snow_y))
        pygame.draw.line(scratch, SNOW_SHADE,
                         (0, snow_y), (pw - 1, snow_y), 2)
        # Snow highlights
        for _ in range(4):
            sx = rng.randint(0, pw - 1)
            sy = rng.randint(1, max(1, snow_y - 2))
            pygame.draw.line(scratch, SNOW_HI,
                             (sx, sy), (sx, sy + rng.randint(1, 3)), 1)

    # 6. Clip everything to the polygon silhouette
    mask = pygame.Surface((pw, ph), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), shifted)
    scratch.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    surf.blit(scratch, (x0, y0))

    # 7. Crisp outline
    pygame.draw.polygon(surf, ROCK_EDGE, poly, 1)


# ---- base skirt ------------------------------------------------------------
def _draw_base(surf, rng, cx, tile_cy, tile_dw, tile_dh, subtype):
    tile_top    = (cx, tile_cy - tile_dh)
    tile_right  = (cx + tile_dw, tile_cy)
    tile_bottom = (cx, tile_cy + tile_dh)
    tile_left   = (cx - tile_dw, tile_cy)
    poly = [tile_top, tile_right, tile_bottom, tile_left]

    if subtype in (0, 1):
        base = ROCK_MID
    elif subtype == 2:
        base = GRASS
    elif subtype == 3:
        base = _blend(GRASS, ROCK_MID, 0.55)
    else:
        base = GRASS

    pygame.draw.polygon(surf, base, poly)
    _scatter(surf, rng, poly, base, n=90, var=0.16)
    # Ground detail: pebbles / grass tufts
    for _ in range(rng.randint(8, 16)):
        px = rng.randint(cx - tile_dw + 4, cx + tile_dw - 4)
        py = rng.randint(tile_cy - tile_dh + 4, tile_cy + tile_dh - 4)
        if _inside_poly(px, py, poly):
            if subtype in (0, 1):
                col = _s(ROCK_LOWER, rng.uniform(0.9, 1.15))
                pygame.draw.circle(surf, col, (px, py), rng.randint(1, 2))
            else:
                col = _s(GRASS_LO, rng.uniform(0.9, 1.15))
                pygame.draw.line(surf, col, (px, py),
                                 (px + rng.randint(-1, 1),
                                  py - rng.randint(2, 5)), 1)

    pygame.draw.polygon(surf, ROCK_EDGE, poly, 1)


# ---- pine trees at the base (forested subtype) -----------------------------
def _draw_base_trees(surf, rng, cx, tile_cy, tile_dw, tile_dh):
    for _ in range(rng.randint(5, 9)):
        px = cx + rng.randint(-tile_dw + 10, tile_dw - 10)
        py = tile_cy + rng.randint(-tile_dh + 4, tile_dh - 6)
        # Small pine (3 stacked triangles + trunk)
        size = rng.randint(6, 10)
        # Trunk
        pygame.draw.line(surf, TRUNK, (px, py), (px, py - 3), 1)
        # Foliage tiers
        for k in range(3):
            w = size - k * 2
            yy = py - 3 - k * 3
            pygame.draw.polygon(surf, TREE_DARK, [
                (px - w // 2, yy), (px + w // 2, yy), (px, yy - w // 2)])
            pygame.draw.polygon(surf, TREE_MID, [
                (px - w // 2 + 1, yy - 1), (px + w // 2 - 1, yy - 1),
                (px, yy - w // 2 + 1)])
            pygame.draw.line(surf, TREE_HI,
                             (px, yy), (px, yy - w // 2), 1)


# ---- master builder --------------------------------------------------------
def _build(scol, srow):
    W, H = _SPRITE_W, _SPRITE_H
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    rng = random.Random(scol * 7919 + srow * 104729 + 17)

    subtype = (scol * 3 + srow * 5) % 5
    cx = W // 2
    bottom_y = H - 6
    tile_dh = C.TILE_HALF_H
    tile_dw = C.TILE_HALF_W
    tile_cy = bottom_y - tile_dh

    # ---- peak scale by subtype ----
    if subtype == 0:        # snowy
        peak_h = rng.randint(140, 175)
        n_secondary = rng.randint(1, 2)
    elif subtype == 1:      # rocky
        peak_h = rng.randint(110, 150)
        n_secondary = rng.randint(1, 2)
    elif subtype == 2:      # forested
        peak_h = rng.randint(80, 120)
        n_secondary = 1
    elif subtype == 3:      # medium
        peak_h = rng.randint(50, 85)
        n_secondary = rng.randint(0, 1)
    else:                   # hill
        peak_h = rng.randint(28, 48)
        n_secondary = 0

    # ---- base skirt first (peaks will overlay it) ----
    _draw_base(surf, rng, cx, tile_cy, tile_dw, tile_dh, subtype)

    # ---- secondary peaks (drawn back-to-front so main is on top) ----
    secondary_polys = []
    for i in range(n_secondary):
        offset = rng.choice([-1, 1]) * rng.randint(28, 46)
        sec_h = peak_h * rng.uniform(0.55, 0.80)
        sec_top_y = tile_cy - int(sec_h)
        sec_top_x = cx + offset
        sec_half = rng.randint(6, 12)
        if offset < 0:
            lb = (cx - tile_dw + rng.randint(-8, 4),
                  tile_cy + rng.randint(-4, 8))
            rb = (cx + rng.randint(-6, 6), tile_cy + rng.randint(-4, 8))
        else:
            lb = (cx + rng.randint(-6, 6), tile_cy + rng.randint(-4, 8))
            rb = (cx + tile_dw + rng.randint(-4, 8),
                  tile_cy + rng.randint(-4, 8))
        poly = [
            (sec_top_x, sec_top_y),
            (sec_top_x + sec_half, sec_top_y + sec_half),
            rb,
            (cx + rng.randint(-6, 6), bottom_y - 4),
            lb,
            (sec_top_x - sec_half, sec_top_y + sec_half),
        ]
        secondary_polys.append(poly)

    # Sort so leftmost secondary is drawn first
    secondary_polys.sort(key=lambda p: min(pt[0] for pt in p))
    for poly in secondary_polys:
        _draw_peak(surf, rng, poly, subtype, peak_h * 0.7)

    # ---- main peak ----
    main_top_y = tile_cy - peak_h
    main_top_x = cx + rng.randint(-10, 10)
    main_half = rng.randint(8, 14)
    main_left = (cx - tile_dw + rng.randint(-6, 6),
                 tile_cy + rng.randint(-4, 6))
    main_right = (cx + tile_dw + rng.randint(-6, 6),
                  tile_cy + rng.randint(-4, 6))
    main_poly = [
        (main_top_x, main_top_y),
        (main_top_x + main_half, main_top_y + main_half),
        main_right,
        (cx + rng.randint(-8, 8), bottom_y - 4),
        main_left,
        (main_top_x - main_half, main_top_y + main_half),
    ]
    _draw_peak(surf, rng, main_poly, subtype, peak_h)

    # ---- forested: trees at the base ----
    if subtype == 2:
        _draw_base_trees(surf, rng, cx, tile_cy, tile_dw, tile_dh)

    # ---- moss / lichen on the lower skirt for rocky and medium ----
    if subtype in (1, 3):
        for _ in range(rng.randint(4, 8)):
            mx = cx + rng.randint(-tile_dw + 8, tile_dw - 8)
            my = tile_cy + rng.randint(-tile_dh // 2, tile_dh - 6)
            pygame.draw.circle(surf, (86, 120, 66), (mx, my),
                               rng.randint(2, 4))
            pygame.draw.circle(surf, (128, 166, 96), (mx - 1, my - 1), 1)

    # ---- soft contact shadow under the whole formation ----
    sh_w = tile_dw + 6
    sh_h = tile_dh // 2 + 4
    shadow = pygame.Surface((sh_w * 2, sh_h * 2), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 100), shadow.get_rect())
    surf.blit(shadow, (cx - sh_w, tile_cy + 2))

    return surf