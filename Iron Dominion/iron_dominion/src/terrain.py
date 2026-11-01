"""Terrain: tile types, periodic world-texture generation, seamless sampling.

Why the map no longer shows tiles
---------------------------------
Each terrain type has one large **periodic** texture (period 384×448 in
texture pixels). A tile at (col, row) samples a 128×64 window from that
texture at:

    tx = ((col - row) * 64) % 384
    ty = ((col + row) * 32) % 448

Adjacent tiles are separated by exactly 64 px in X and 32 px in Y in
texture space, and the texture wraps at 384/448 without a seam. Adjacent
tiles therefore share 64×32 px of *identical* texture content, and the
map reads as one continuous painting.

The old ``make_tile_surface(tile_type, variant)`` shim is preserved.
"""

import heapq
import math
import random

import pygame

from . import config as C

# ---------------------------------------------------------------------------
# Tile types
# ---------------------------------------------------------------------------
GRASS = 0
TALL_GRASS = 1
DIRT = 2
SAND = 3
SHALLOW_WATER = 4
DEEP_WATER = 5
STONE = 6
ROAD = 7
MOUNTAIN = 8

TILE_NAMES = {
    GRASS: "Grass", TALL_GRASS: "Tall Grass", DIRT: "Dirt", SAND: "Sand",
    SHALLOW_WATER: "Shallows", DEEP_WATER: "Deep Water",
    STONE: "Stone Ground", ROAD: "Road", MOUNTAIN: "Mountain",
}

TILE_COLORS = {
    GRASS:         ((128, 178, 100),  (86, 130, 62)),
    TALL_GRASS:    ((100, 154, 78),   (66, 112, 52)),
    DIRT:          ((176, 142, 100),  (132, 100, 64)),
    SAND:          ((226, 206, 156),  (190, 168, 118)),
    SHALLOW_WATER: ((122, 180, 214),  (78, 128, 172)),
    DEEP_WATER:    ((54, 100, 154),   (26, 58, 104)),
    STONE:         ((162, 162, 166),  (116, 116, 124)),
    ROAD:          ((178, 150, 110),  (134, 110, 80)),
    MOUNTAIN:      ((134, 136, 142),  (94, 96, 102)),
}

WATER_TILES = {SHALLOW_WATER, DEEP_WATER}
IMPASSABLE_TILES = {DEEP_WATER, MOUNTAIN}

DIR_NE, DIR_SE, DIR_SW, DIR_NW = 0, 1, 2, 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _cl(v):
    return 0 if v < 0 else (255 if v > 255 else int(v))


def shade(c, f):
    return (_cl(c[0] * f), _cl(c[1] * f), _cl(c[2] * f))


def lerp_color(a, b, t):
    return (_cl(a[0] + (b[0] - a[0]) * t),
            _cl(a[1] + (b[1] - a[1]) * t),
            _cl(a[2] + (b[2] - a[2]) * t))


# ===========================================================================
# WORLD TEXTURE
# ===========================================================================
TEX_SIZE = 512          # texture surface is 512×512
WRAP_X   = 384          # effective period in X (512 - 128 sample width)
WRAP_Y   = 448          # effective period in Y (512 - 64 sample height)

_WORLD_TEXTURES = {}


# ---- wrapped primitives ---------------------------------------------------
def _wc(surf, cx, cy, r, col):
    """Wrapped filled circle."""
    for dx in (0, -WRAP_X, WRAP_X):
        for dy in (0, -WRAP_Y, WRAP_Y):
            pygame.draw.circle(surf, col, (cx + dx, cy + dy), r)


def _wl(surf, x0, y0, x1, y1, col, w=1):
    """Wrapped line."""
    for dx in (0, -WRAP_X, WRAP_X):
        for dy in (0, -WRAP_Y, WRAP_Y):
            pygame.draw.line(surf, col,
                             (x0 + dx, y0 + dy), (x1 + dx, y1 + dy), w)


def _wlines(surf, pts, col, w=1):
    for dx in (0, -WRAP_X, WRAP_X):
        for dy in (0, -WRAP_Y, WRAP_Y):
            shifted = [(px + dx, py + dy) for (px, py) in pts]
            pygame.draw.lines(surf, col, False, shifted, w)


def _wpoly(surf, pts, col, w=0):
    for dx in (0, -WRAP_X, WRAP_X):
        for dy in (0, -WRAP_Y, WRAP_Y):
            shifted = [(px + dx, py + dy) for (px, py) in pts]
            pygame.draw.polygon(surf, col, shifted, w)


def _wset(surf, x, y, col):
    surf.set_at((x % WRAP_X, y % WRAP_Y), col)


def _wellipse(surf, x, y, w, h, col):
    for dx in (0, -WRAP_X, WRAP_X):
        for dy in (0, -WRAP_Y, WRAP_Y):
            pygame.draw.ellipse(surf, col, (x + dx, y + dy, w, h))


# ---- per-type detail renderers -------------------------------------------
def _tex_grass(surf, rng):
    base, dark = TILE_COLORS[GRASS]
    light = shade(base, 1.14)
    dark2 = shade(dark, 0.82)

    # 4000 grass blades
    for _ in range(4000):
        x = rng.randint(0, WRAP_X - 1)
        y = rng.randint(0, WRAP_Y - 1)
        ln = rng.randint(1, 3)
        col = dark2 if rng.random() < 0.65 else light
        _wl(surf, x, y, x, y - ln, col)

    # 300 soft patches
    for _ in range(300):
        cx = rng.randint(0, WRAP_X - 1)
        cy = rng.randint(0, WRAP_Y - 1)
        rw = rng.randint(4, 12)
        rh = rng.randint(2, 6)
        col = light if rng.random() < 0.5 else dark2
        ov = pygame.Surface((rw * 2, rh * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(ov, (*col, 90), ov.get_rect())
        for dx in (0, -WRAP_X, WRAP_X):
            for dy in (0, -WRAP_Y, WRAP_Y):
                surf.blit(ov, (cx - rw + dx, cy - rh + dy))

    # 400 flowers
    palette = [(232, 216, 120), (245, 240, 230), (220, 130, 160),
               (206, 156, 220), (240, 180, 90)]
    for _ in range(400):
        x = rng.randint(2, WRAP_X - 3)
        y = rng.randint(2, WRAP_Y - 3)
        col = rng.choice(palette)
        _wset(surf, x, y, col)
        _wset(surf, x + 1, y, shade(col, 0.85))

    # 100 small stones
    for _ in range(100):
        x = rng.randint(3, WRAP_X - 4)
        y = rng.randint(3, WRAP_Y - 4)
        col = rng.choice([(140, 130, 118), (128, 122, 112)])
        _wc(surf, x, y, rng.choice([1, 1, 2]), col)


def _tex_tall_grass(surf, rng):
    base, dark = TILE_COLORS[TALL_GRASS]
    light = shade(base, 1.18)
    dark2 = shade(dark, 0.80)

    # Dense fronds
    for _ in range(6000):
        x = rng.randint(0, WRAP_X - 1)
        y = rng.randint(0, WRAP_Y - 1)
        ln = rng.randint(2, 6)
        tip_x = x + rng.randint(-1, 1)
        col = dark2 if rng.random() < 0.7 else light
        _wl(surf, x, y, tip_x, y - ln, col)

    # Tall fronds
    for _ in range(500):
        x = rng.randint(0, WRAP_X - 1)
        y = rng.randint(6, WRAP_Y - 1)
        ln = rng.randint(6, 11)
        _wl(surf, x, y, x + rng.randint(-2, 2), y - ln, dark2)

    # Occasional flowers
    for _ in range(120):
        x = rng.randint(3, WRAP_X - 4)
        y = rng.randint(3, WRAP_Y - 4)
        _wset(surf, x, y,
              rng.choice([(230, 200, 120), (240, 240, 220), (200, 150, 200)]))


def _tex_dirt(surf, rng):
    base, dark = TILE_COLORS[DIRT]
    light = shade(base, 1.14)
    dark2 = shade(dark, 0.82)

    # 3500 clod spots
    for _ in range(3500):
        x = rng.randint(0, WRAP_X - 1)
        y = rng.randint(0, WRAP_Y - 1)
        col = dark2 if rng.random() < 0.6 else light
        _wset(surf, x, y, col)

    # 180 soft clods
    for _ in range(180):
        cx = rng.randint(0, WRAP_X - 1)
        cy = rng.randint(0, WRAP_Y - 1)
        rw = rng.randint(3, 8)
        rh = rng.randint(2, 5)
        col = light if rng.random() < 0.5 else dark2
        ov = pygame.Surface((rw * 2, rh * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(ov, (*col, 90), ov.get_rect())
        for dx in (0, -WRAP_X, WRAP_X):
            for dy in (0, -WRAP_Y, WRAP_Y):
                surf.blit(ov, (cx - rw + dx, cy - rh + dy))

    # 140 pebbles
    for _ in range(140):
        x = rng.randint(2, WRAP_X - 3)
        y = rng.randint(2, WRAP_Y - 3)
        col = rng.choice([(150, 130, 100), (128, 106, 82)])
        _wc(surf, x, y, 1, col)

    # 40 footprint dimples
    for _ in range(40):
        x = rng.randint(0, WRAP_X - 1)
        y = rng.randint(0, WRAP_Y - 1)
        rw = rng.randint(2, 4)
        rh = rng.randint(1, 2)
        _wellipse(surf, x, y, rw, rh, dark2)


def _tex_sand(surf, rng):
    """No horizontal lines — fine grain only, plus tiny curved ripples."""
    base, dark = TILE_COLORS[SAND]
    light = shade(base, 1.08)
    dark2 = shade(dark, 0.90)

    # 8000 fine grain dots
    for _ in range(8000):
        x = rng.randint(0, WRAP_X - 1)
        y = rng.randint(0, WRAP_Y - 1)
        col = dark2 if rng.random() < 0.55 else light
        _wset(surf, x, y, col)

    # 200 short curved ripples
    for _ in range(200):
        x0 = rng.randint(2, WRAP_X - 10)
        y0 = rng.randint(2, WRAP_Y - 4)
        seg = rng.randint(4, 8)
        pts = [(x0 + k, y0 + int(math.sin(k * 0.8) * 1.5))
               for k in range(seg)]
        _wlines(surf, pts, dark2, 1)

    # 60 pebbles
    for _ in range(60):
        x = rng.randint(2, WRAP_X - 3)
        y = rng.randint(2, WRAP_Y - 3)
        _wc(surf, x, y, 1, (152, 130, 100))


def _tex_stone(surf, rng):
    base, dark = TILE_COLORS[STONE]
    light = shade(base, 1.16)
    dark2 = shade(dark, 0.82)

    # 5000 speckles
    for _ in range(5000):
        x = rng.randint(0, WRAP_X - 1)
        y = rng.randint(0, WRAP_Y - 1)
        col = dark2 if rng.random() < 0.55 else light
        _wset(surf, x, y, col)

    # 700 pebbles
    for _ in range(700):
        x = rng.randint(2, WRAP_X - 3)
        y = rng.randint(2, WRAP_Y - 3)
        r = rng.choice([1, 1, 2, 2, 3])
        col = light if rng.random() < 0.4 else dark2
        _wc(surf, x, y, r, col)

    # 40 cracks
    for _ in range(40):
        x0 = rng.randint(0, WRAP_X - 1)
        y0 = rng.randint(0, WRAP_Y - 1)
        ln = rng.randint(6, 18)
        ang = rng.uniform(0, math.tau)
        x1 = int(x0 + math.cos(ang) * ln)
        y1 = int(y0 + math.sin(ang) * ln)
        _wl(surf, x0, y0, x1, y1, dark2)


def _tex_road(surf, rng):
    base, dark = TILE_COLORS[ROAD]
    light = shade(base, 1.12)
    dark2 = shade(dark, 0.80)

    # Grain
    for _ in range(4000):
        x = rng.randint(0, WRAP_X - 1)
        y = rng.randint(0, WRAP_Y - 1)
        col = dark2 if rng.random() < 0.6 else light
        _wset(surf, x, y, col)

    # Pebbles
    for _ in range(400):
        x = rng.randint(2, WRAP_X - 3)
        y = rng.randint(2, WRAP_Y - 3)
        _wc(surf, x, y, rng.choice([1, 1, 2]), dark2)

    # Faint wheel ruts — diagonal soft streaks
    for _ in range(10):
        x0 = rng.randint(0, WRAP_X - 60)
        y0 = rng.randint(0, WRAP_Y - 20)
        ln = rng.randint(30, 60)
        for k in range(ln):
            x = x0 + k
            y = y0 + k // 5
            _wset(surf, x, y, dark2)


def _tex_shallow_water(surf, rng):
    base, dark = TILE_COLORS[SHALLOW_WATER]
    light = shade(base, 1.18)
    dark2 = shade(dark, 0.86)

    # Base variation
    for _ in range(4000):
        x = rng.randint(0, WRAP_X - 1)
        y = rng.randint(0, WRAP_Y - 1)
        col = dark2 if rng.random() < 0.5 else light
        _wset(surf, x, y, col)

    # 500 wavy ripples
    for _ in range(500):
        x0 = rng.randint(0, WRAP_X - 15)
        y0 = rng.randint(0, WRAP_Y - 3)
        ln = rng.randint(6, 16)
        pts = [(x0 + k, y0 + int(math.sin(k * 0.55) * 1.5))
               for k in range(ln)]
        _wlines(surf, pts, light, 1)

    # 200 sparkles
    for _ in range(200):
        x = rng.randint(2, WRAP_X - 3)
        y = rng.randint(2, WRAP_Y - 3)
        _wset(surf, x, y, (248, 252, 255))


def _tex_deep_water(surf, rng):
    base, dark = TILE_COLORS[DEEP_WATER]
    light = shade(base, 1.20)
    dark2 = shade(dark, 0.86)

    for _ in range(3000):
        x = rng.randint(0, WRAP_X - 1)
        y = rng.randint(0, WRAP_Y - 1)
        col = dark2 if rng.random() < 0.5 else light
        _wset(surf, x, y, col)

    for _ in range(120):
        x0 = rng.randint(0, WRAP_X - 15)
        y0 = rng.randint(0, WRAP_Y - 3)
        ln = rng.randint(8, 18)
        pts = [(x0 + k, y0 + int(math.sin(k * 0.5) * 1.3))
               for k in range(ln)]
        _wlines(surf, pts, light, 1)


def _tex_mountain(surf, rng):
    base, dark = TILE_COLORS[MOUNTAIN]
    light = shade(base, 1.20)
    dark2 = shade(dark, 0.78)

    for _ in range(5000):
        x = rng.randint(0, WRAP_X - 1)
        y = rng.randint(0, WRAP_Y - 1)
        col = dark2 if rng.random() < 0.6 else light
        _wset(surf, x, y, col)

    # Angular rock facets
    for _ in range(500):
        cx = rng.randint(2, WRAP_X - 3)
        cy = rng.randint(2, WRAP_Y - 3)
        r = rng.randint(2, 6)
        pts = []
        for _k in range(3):
            a = rng.uniform(0, math.tau)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r * 0.7))
        _wpoly(surf, pts, light if rng.random() < 0.5 else dark2)


_TEX_FNS = {
    GRASS:         _tex_grass,
    TALL_GRASS:    _tex_tall_grass,
    DIRT:          _tex_dirt,
    SAND:          _tex_sand,
    STONE:         _tex_stone,
    ROAD:          _tex_road,
    SHALLOW_WATER: _tex_shallow_water,
    DEEP_WATER:    _tex_deep_water,
    MOUNTAIN:      _tex_mountain,
}


def _build_world_texture(tile_type, seed):
    surf = pygame.Surface((TEX_SIZE, TEX_SIZE))
    surf.fill(TILE_COLORS[tile_type][0])
    rng = random.Random(seed * 7919 + tile_type * 104729)
    fn = _TEX_FNS.get(tile_type)
    if fn is not None:
        fn(surf, rng)
    return surf


def _get_world_texture(tile_type):
    tex = _WORLD_TEXTURES.get(tile_type)
    if tex is None:
        tex = _build_world_texture(tile_type, C.MAP_SEED)
        _WORLD_TEXTURES[tile_type] = tex
    return tex


# ===========================================================================
# TILE SAMPLING
# ===========================================================================
_TILE_CACHE = {}
_DIAMOND_MASK = None


def _get_diamond_mask():
    global _DIAMOND_MASK
    if _DIAMOND_MASK is None:
        w, h = C.TILE_WIDTH, C.TILE_HEIGHT
        m = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(m, (255, 255, 255, 255),
                            [(w // 2, 0), (w, h // 2), (w // 2, h), (0, h // 2)])
        _DIAMOND_MASK = m
    return _DIAMOND_MASK


def _sample_pos(col, row):
    """Return (tx, ty) — the top-left of the sample window in the texture."""
    wx = (col - row) * C.TILE_HALF_W
    wy = (col + row) * C.TILE_HALF_H
    tx = wx % WRAP_X
    ty = wy % WRAP_Y
    return tx, ty


def _build_tile(tile_type, tx, ty):
    tex = _get_world_texture(tile_type)
    surf = pygame.Surface((C.TILE_WIDTH, C.TILE_HEIGHT), pygame.SRCALPHA)
    surf.blit(tex, (0, 0),
              pygame.Rect(tx, ty, C.TILE_WIDTH, C.TILE_HEIGHT))
    surf.blit(_get_diamond_mask(), (0, 0),
              special_flags=pygame.BLEND_RGBA_MULT)
    return surf


def get_tile_surface(tile_type, col, row):
    """Return the seamless tile sprite for this tile's world position."""
    tx, ty = _sample_pos(col, row)
    key = (tile_type, tx, ty)
    s = _TILE_CACHE.get(key)
    if s is None:
        s = _build_tile(tile_type, tx, ty)
        _TILE_CACHE[key] = s
    return s


# ---- backward-compat -------------------------------------------------------
def make_tile_surface(tile_type, variant):
    """Legacy API. Samples the world texture at a fixed offset."""
    tx = (variant % 6) * 64
    ty = (variant // 6) * 32
    tx = tx % WRAP_X
    ty = ty % WRAP_Y
    return _build_tile(tile_type, tx, ty)


# ===========================================================================
# EDGE OVERLAYS (soft terrain transitions)
# ===========================================================================
_TRANSITION_BANDS = 28
_TRANSITION_DEPTH = 36
_EDGE_CACHE = {}


def make_edge_overlay(tile_type, direction, subvariant=0):
    key = (tile_type, direction, subvariant)
    s = _EDGE_CACHE.get(key)
    if s is not None:
        return s

    w, h = C.TILE_WIDTH, C.TILE_HEIGHT
    cx, cy = w * 0.5, h * 0.5
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    color = TILE_COLORS[tile_type][0]

    top = (cx, 0.0); right = (float(w), cy)
    bottom = (cx, float(h)); left = (0.0, cy)

    if direction == DIR_NE:
        p0, p1 = top, right; inward = (-2.0, 1.0)
    elif direction == DIR_SE:
        p0, p1 = right, bottom; inward = (-2.0, -1.0)
    elif direction == DIR_SW:
        p0, p1 = bottom, left; inward = (2.0, -1.0)
    elif direction == DIR_NW:
        p0, p1 = left, top; inward = (2.0, 1.0)
    else:
        _EDGE_CACHE[key] = surf
        return surf

    mag = math.hypot(*inward)
    inx, iny = inward[0] / mag, inward[1] / mag

    rng = random.Random((tile_type * 1009) ^ (direction * 9176)
                        ^ (subvariant * 251))

    n = _TRANSITION_BANDS
    depth = _TRANSITION_DEPTH
    for i in range(n):
        t0 = i / n
        t1 = (i + 1) / n
        tm = (t0 + t1) * 0.5
        alpha = int(150 * ((1.0 - tm) ** 2.1))
        alpha = int(alpha * (1.0 + rng.uniform(-0.25, 0.25)))
        if alpha < 2:
            continue
        alpha = min(alpha, 255)
        d0 = t0 * depth
        d1 = t1 * depth
        w0 = rng.uniform(-3.0, 3.0)
        w1 = rng.uniform(-3.0, 3.0)
        q0 = (p0[0] + inx * (d0 + w0), p0[1] + iny * (d0 + w0))
        q1 = (p1[0] + inx * (d0 + w1), p1[1] + iny * (d0 + w1))
        q2 = (p1[0] + inx * d1, p1[1] + iny * d1)
        q3 = (p0[0] + inx * d1, p0[1] + iny * d1)
        pygame.draw.polygon(surf, (*color, alpha), [q0, q1, q2, q3])

    surf.blit(_get_diamond_mask(), (0, 0),
              special_flags=pygame.BLEND_RGBA_MULT)
    _EDGE_CACHE[key] = surf
    return surf


# ===========================================================================
# NOISE (used by world gen)
# ===========================================================================
def _value_noise(cols, rows, scale, rng):
    gw = int(cols / scale) + 3
    gh = int(rows / scale) + 3
    grid = [[rng.random() for _ in range(gw)] for _ in range(gh)]
    out = [[0.0] * cols for _ in range(rows)]
    for row in range(rows):
        fy = row / scale
        y0 = int(fy); ty = fy - y0
        sy = ty * ty * (3.0 - 2.0 * ty)
        g0, g1 = grid[y0], grid[y0 + 1]
        out_row = out[row]
        for col in range(cols):
            fx = col / scale
            x0 = int(fx); tx = fx - x0
            sx = tx * tx * (3.0 - 2.0 * tx)
            a = g0[x0] + (g0[x0 + 1] - g0[x0]) * sx
            b = g1[x0] + (g1[x0 + 1] - g1[x0]) * sx
            out_row[col] = a + (b - a) * sy
    return out


def _fractal_noise(cols, rows, seed):
    rng = random.Random(seed)
    layers = ((20.0, 1.0), (10.0, 0.5), (5.0, 0.25), (2.5, 0.125))
    acc = [[0.0] * cols for _ in range(rows)]
    for scale, weight in layers:
        layer = _value_noise(cols, rows, scale, rng)
        for row in range(rows):
            a = acc[row]; l = layer[row]
            for col in range(cols):
                a[col] += l[col] * weight
    lo = min(min(r) for r in acc); hi = max(max(r) for r in acc)
    span = (hi - lo) or 1.0
    for row in range(rows):
        a = acc[row]
        for col in range(cols):
            a[col] = (a[col] - lo) / span
    return acc


# ===========================================================================
# TerrainMap (unchanged public API)
# ===========================================================================
class TerrainMap:
    def __init__(self, cols, rows, seed):
        self.cols = cols
        self.rows = rows
        self.seed = seed
        self.tiles = [[(GRASS, 0) for _ in range(cols)] for _ in range(rows)]
        self.elevation = [[0] * cols for _ in range(rows)]
        self.generate()

    def generate(self):
        elev = _fractal_noise(self.cols, self.rows, self.seed + 1)
        moist = _fractal_noise(self.cols, self.rows, self.seed + 2)
        detail = _fractal_noise(self.cols, self.rows, self.seed + 3)
        rng = random.Random(self.seed ^ 0x5EED)

        for row in range(self.rows):
            for col in range(self.cols):
                e = elev[row][col]; m = moist[row][col]; d = detail[row][col]
                if e < 0.28:
                    t = DEEP_WATER if e < 0.14 else SHALLOW_WATER; el = 0
                elif e < 0.35:
                    t = SAND; el = 0
                elif e > 0.80:
                    t = MOUNTAIN; el = 2
                elif e > 0.64:
                    el = 1
                    t = GRASS if m > 0.5 else STONE
                else:
                    el = 0
                    if m > 0.62:   t = GRASS
                    elif m > 0.44: t = TALL_GRASS
                    elif m > 0.26: t = DIRT
                    else:          t = STONE if d > 0.5 else DIRT
                self.tiles[row][col] = (t, rng.randrange(C.TILE_VARIANTS))
                self.elevation[row][col] = el

        self._carve_beaches()
        self._generate_roads(rng)

    def _carve_beaches(self):
        for row in range(self.rows):
            for col in range(self.cols):
                t, v = self.tiles[row][col]
                if t in WATER_TILES:
                    continue
                for dc, dr in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nc, nr = col + dc, row + dr
                    if 0 <= nc < self.cols and 0 <= nr < self.rows:
                        if self.tiles[nr][nc][0] in WATER_TILES:
                            if t in (GRASS, TALL_GRASS, DIRT):
                                self.tiles[row][col] = (SAND, v)
                            break

    def _generate_roads(self, rng):
        waypoints = []
        for _ in range(6):
            for _try in range(40):
                c = rng.randrange(self.cols // 5, 4 * self.cols // 5)
                r = rng.randrange(self.rows // 5, 4 * self.rows // 5)
                if self.is_walkable(c, r) and self.elevation[r][c] == 0:
                    waypoints.append((c, r)); break
        for i in range(len(waypoints) - 1):
            a, b = waypoints[i], waypoints[i + 1]
            for (c, r) in self._astar(a, b):
                for dc in (-1, 0, 1):
                    for dr in (-1, 0, 1):
                        nc, nr = c + dc, r + dr
                        if 0 <= nc < self.cols and 0 <= nr < self.rows:
                            if self.elevation[nr][nc] != 0:
                                continue
                            tt, vv = self.tiles[nr][nc]
                            if tt in WATER_TILES or tt == MOUNTAIN:
                                continue
                            self.tiles[nr][nc] = (ROAD, vv)

    def _astar(self, start, goal):
        def h(a, b): return abs(a[0] - b[0]) + abs(a[1] - b[1])
        open_set = [(h(start, goal), 0, start)]
        came = {}; g = {start: 0}
        while open_set:
            _f, _g, cur = heapq.heappop(open_set)
            if cur == goal:
                path = [cur]
                while cur in came:
                    cur = came[cur]; path.append(cur)
                return list(reversed(path))
            cx, cy = cur
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nc, ny = cx + dx, cy + dy
                if not (0 <= nc < self.cols and 0 <= ny < self.rows):
                    continue
                if not self.is_walkable(nc, ny): continue
                if self.elevation[ny][nc] != 0: continue
                ng = g[cur] + 1
                if (nc, ny) not in g or ng < g[(nc, ny)]:
                    came[(nc, ny)] = cur; g[(nc, ny)] = ng
                    heapq.heappush(open_set, (ng + h((nc, ny), goal),
                                              ng, (nc, ny)))
        return []

    def get(self, col, row): return self.tiles[row][col]
    def get_elevation(self, col, row): return self.elevation[row][col]
    def in_bounds(self, col, row):
        return 0 <= col < self.cols and 0 <= row < self.rows
    def is_water(self, col, row):
        return self.tiles[row][col][0] in WATER_TILES
    def is_walkable(self, col, row):
        return self.tiles[row][col][0] not in IMPASSABLE_TILES