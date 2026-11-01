"""Environmental props: trees, rocks, bushes, flowers, logs, deposits.

Visual overhaul: many more kinds and shapes, richer palette, better
silhouettes, grounded shadows. All sprites are procedural and cached.
"""

import math
import random

import pygame

from .resources import FOOD, WOOD, STONE, IRON


# ---------------------------------------------------------------------------
# Prop kinds
# ---------------------------------------------------------------------------
TREE_ROUND = 0
TREE_PINE = 1
ROCK = 2
BERRY_BUSH = 3
STONE_DEPOSIT = 4
IRON_DEPOSIT = 5
FLOWER_PATCH = 6
GRASS_TUFT = 7
FALLEN_LOG = 8
STUMP = 9
SMALL_ROCK = 10
BOULDER = 11
STONE_PILE = 12
GRAVEL = 13

PROP_RESOURCE_TYPE = {
    TREE_ROUND: WOOD,
    TREE_PINE: WOOD,
    ROCK: None,
    BERRY_BUSH: FOOD,
    STONE_DEPOSIT: STONE,
    IRON_DEPOSIT: IRON,
    FLOWER_PATCH: None,
    GRASS_TUFT: None,
    FALLEN_LOG: None,
    STUMP: None,
    SMALL_ROCK: None,
    BOULDER: None,
    STONE_PILE: None,
    GRAVEL: None,
}

PROP_CAPACITY = {
    TREE_ROUND: 100,
    TREE_PINE: 100,
    ROCK: 0,
    BERRY_BUSH: 150,
    STONE_DEPOSIT: 350,
    IRON_DEPOSIT: 300,
    FLOWER_PATCH: 0,
    GRASS_TUFT: 0,
    FALLEN_LOG: 0,
    STUMP: 0,
    SMALL_ROCK: 0,
    BOULDER: 0,
    STONE_PILE: 0,
    GRAVEL: 0,
}


def _shade(c, f):
    return tuple(max(0, min(255, int(x * f))) for x in c)


# ---------------------------------------------------------------------------
# Shadow helper (soft, consistent light source from upper-left)
# ---------------------------------------------------------------------------
def _shadow(surf, cx, cy, rx, ry, alpha=80):
    sh = pygame.Surface((int(rx * 2) + 4, int(ry * 2) + 4), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, alpha), sh.get_rect())
    surf.blit(sh, (int(cx - rx - 2), int(cy - ry - 2)))


# ---------------------------------------------------------------------------
# Tree generators
# ---------------------------------------------------------------------------
def _make_round_tree(rng):
    w, h = 88, 118
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 8

    trunk_col = (110, 76, 48)
    trunk_dark = (72, 48, 28)
    trunk_hi = (138, 100, 64)

    # Palette per tree — 4 possible colorways
    palette_choice = rng.randrange(4)
    if palette_choice == 0:      # standard green
        leaf_hi = (146, 198, 100)
        leaf_mid = (106, 162, 76)
        leaf_lo = (74, 126, 58)
    elif palette_choice == 1:    # deep green
        leaf_hi = (110, 168, 88)
        leaf_mid = (80, 132, 62)
        leaf_lo = (56, 100, 44)
    elif palette_choice == 2:    # yellow-green
        leaf_hi = (176, 210, 108)
        leaf_mid = (138, 178, 82)
        leaf_lo = (100, 142, 60)
    else:                        # autumn
        leaf_hi = (216, 176, 96)
        leaf_mid = (188, 138, 72)
        leaf_lo = (140, 100, 52)

    jitter = rng.uniform(0.94, 1.06)
    leaf_hi = _shade(leaf_hi, jitter)
    leaf_mid = _shade(leaf_mid, jitter)
    leaf_lo = _shade(leaf_lo, jitter)

    _shadow(surf, cx, base_y + 2, 30, 8, alpha=70)

    # Trunk with a slight lean
    trunk_h = rng.randint(30, 42)
    trunk_w = rng.randint(7, 10)
    lean = rng.randint(-3, 3)
    tx = cx - trunk_w // 2
    ty = base_y - trunk_h
    pygame.draw.polygon(surf, trunk_dark, [
        (tx, base_y),
        (tx + trunk_w, base_y),
        (tx + trunk_w + lean, ty),
        (tx + lean, ty),
    ])
    pygame.draw.polygon(surf, trunk_col, [
        (tx + 1, base_y - 1),
        (tx + trunk_w - 1, base_y - 1),
        (tx + trunk_w + lean - 1, ty + 1),
        (tx + lean + 1, ty + 1),
    ])
    # Highlight on the left (light from upper-left)
    pygame.draw.line(surf, trunk_hi,
                     (tx + 1, base_y - 1), (tx + lean + 1, ty + 1), 1)

    # Branches peek through the canopy and break up the straight trunk.
    branch_y = ty + trunk_h // 2
    for side in (-1, 1):
        branch_x = tx + trunk_w // 2 + lean // 2
        branch_tip = branch_x + side * rng.randint(14, 21)
        branch_top = branch_y - rng.randint(8, 14)
        pygame.draw.line(surf, trunk_dark, (branch_x, branch_y),
                         (branch_tip, branch_top), 4)
        pygame.draw.line(surf, trunk_hi, (branch_x, branch_y - 1),
                         (branch_tip - side, branch_top), 1)

    # Foliage: cluster of ellipses at various positions
    foliage_cy = ty - 20

    def clump(off_x, off_y, r, col):
        pygame.draw.ellipse(surf, col,
                            (cx + off_x - r, foliage_cy + off_y - r * 0.75,
                             r * 2, int(r * 1.5)))

    clump(-16, 6, 20, leaf_lo)
    clump( 14, 5, 18, leaf_lo)
    clump(  0, 12, 22, leaf_lo)

    clump(-14, -4, 18, leaf_mid)
    clump( 12, -6, 16, leaf_mid)
    clump(  0,  2, 20, leaf_mid)

    clump(-6, -14, 14, leaf_hi)
    clump( 8, -12, 12, leaf_hi)
    clump(  0, -6, 16, leaf_hi)

    # Small clustered leaf flecks add volume without noisy pixel grain.
    for _ in range(52):
        lx = cx + rng.randint(-28, 28)
        ly = foliage_cy + rng.randint(-27, 24)
        dx = (lx - cx) / 31.0
        dy = (ly - foliage_cy) / 34.0
        if dx * dx + dy * dy > 1.0:
            continue
        radius = rng.choice((1, 1, 2, 2, 3))
        col = rng.choice((leaf_hi, leaf_mid, _shade(leaf_lo, 1.12)))
        pygame.draw.ellipse(surf, col, (lx, ly, radius * 2, radius))

    # A few larger sunlit leaf clusters create a readable upper-left light.
    for _ in range(8):
        lx = cx + rng.randint(-22, 5)
        ly = foliage_cy + rng.randint(-24, 2)
        radius = rng.randint(2, 4)
        pygame.draw.ellipse(surf, _shade(leaf_hi, 1.08),
                            (lx, ly, radius * 2, radius))

    return surf


def _make_pine_tree(rng):
    w, h = 80, 138
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 8

    trunk_col = (96, 66, 42)
    trunk_dark = (60, 40, 24)
    trunk_hi = (128, 88, 56)

    palette_choice = rng.randrange(3)
    if palette_choice == 0:
        p_hi = (110, 156, 90)
        p_mid = (78, 122, 68)
        p_lo = (54, 92, 50)
    elif palette_choice == 1:
        p_hi = (92, 142, 88)
        p_mid = (62, 106, 66)
        p_lo = (44, 78, 46)
    else:
        p_hi = (138, 172, 100)
        p_mid = (100, 138, 76)
        p_lo = (68, 100, 56)

    jitter = rng.uniform(0.94, 1.06)
    p_hi = _shade(p_hi, jitter)
    p_mid = _shade(p_mid, jitter)
    p_lo = _shade(p_lo, jitter)

    _shadow(surf, cx, base_y + 2, 24, 7, alpha=70)

    trunk_h = rng.randint(22, 32)
    trunk_w = rng.randint(6, 8)
    tx = cx - trunk_w // 2
    ty = base_y - trunk_h
    pygame.draw.rect(surf, trunk_dark, (tx, ty, trunk_w, trunk_h))
    pygame.draw.rect(surf, trunk_col, (tx + 1, ty, trunk_w - 2, trunk_h - 1))
    pygame.draw.line(surf, trunk_hi, (tx + 1, ty), (tx + 1, ty + trunk_h - 1), 1)

    # Pine tiers (triangular layers) — 4 tiers
    base_tier_y = ty + 4
    for k in range(4):
        tier_h = 22 + k * 4
        tier_w = 22 + k * 9
        tier_y = base_tier_y - k * 16
        pts = [
            (cx - tier_w, tier_y + tier_h * 0.25),
            (cx + tier_w, tier_y + tier_h * 0.25),
            (cx, tier_y - tier_h * 0.45),
        ]
        col = [p_lo, p_mid, p_hi, p_hi][k]
        pygame.draw.polygon(surf, col, pts)
        # Left-side highlight, upper-left light
        pygame.draw.line(surf, _shade(col, 1.15),
                         (cx, tier_y - tier_h * 0.45),
                         (cx - tier_w, tier_y + tier_h * 0.25), 1)
        # Short needle strokes give each tier a layered, evergreen texture.
        for side in (-1, 1):
            for n in range(4):
                t = (n + 1) / 5
                branch_x = int(cx + side * tier_w * t)
                branch_y = int(tier_y + tier_h * 0.22 - tier_h * 0.55 * t)
                tip_x = branch_x - side * rng.randint(3, 6)
                tip_y = branch_y + rng.randint(2, 5)
                pygame.draw.line(surf, _shade(col, 1.18),
                                 (branch_x, branch_y), (tip_x, tip_y), 1)

    return surf


# ---------------------------------------------------------------------------
# Rock generator
# ---------------------------------------------------------------------------
def _make_rock(rng):
    w, h = 68, 54
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 8

    palettes = [
        ((178, 168, 154), (136, 126, 112), (90, 82, 72)),
        ((162, 162, 164), (120, 120, 126), (78, 78, 84)),
        ((158, 142, 122), (116, 104, 86), (78, 68, 54)),
        ((148, 152, 140), (108, 112, 102), (72, 76, 70)),
    ]
    base, mid, dark = rng.choice(palettes)
    light = _shade(base, 1.22)
    edge = _shade(dark, 0.72)

    _shadow(surf, cx, base_y + 4, 26, 6, alpha=95)

    # Body
    size = rng.randint(20, 26)
    n_verts = rng.randint(7, 9)
    pts = []
    for k in range(n_verts):
        a = -math.pi * 0.9 + k * (math.pi * 1.8 / (n_verts - 1))
        r = size * rng.uniform(0.82, 1.05)
        pts.append((cx + math.cos(a) * r,
                    base_y - 4 + math.sin(a) * r * 0.6))
    pygame.draw.polygon(surf, mid, pts)
    pygame.draw.polygon(surf, edge, pts, 2)

    # Layered strata: 3 horizontal bands
    for i in range(3):
        y_band = base_y - 4 - size + i * size // 2
        col = _shade(mid, 0.86 + i * 0.10)
        pygame.draw.line(surf, col,
                         (cx - size, y_band + 2),
                         (cx + size, y_band + 2), 1)

    # Upper-left highlight facet
    top_pts = [
        (cx - size * 0.62, base_y - size * 0.50),
        (cx - size * 0.10, base_y - size * 0.80),
        (cx + size * 0.42, base_y - size * 0.60),
        (cx - size * 0.18, base_y - size * 0.30),
    ]
    pygame.draw.polygon(surf, light, top_pts)
    pygame.draw.line(surf, _shade(light, 1.08),
                     top_pts[0], top_pts[1], 1)

    # Cracks
    for _ in range(rng.randint(2, 4)):
        x0 = cx + rng.randint(-size, size)
        y0 = base_y - rng.randint(3, size)
        ang = rng.uniform(-0.6, 0.6) + math.pi / 2
        ln = rng.randint(4, 9)
        pygame.draw.line(surf, edge, (x0, y0),
                         (int(x0 + math.cos(ang) * ln),
                          int(y0 + math.sin(ang) * ln)), 1)

    # Moss on the lower-left
    if rng.random() < 0.6:
        for _ in range(rng.randint(2, 5)):
            mx = cx + rng.randint(-size, 0)
            my = base_y - rng.randint(0, 5)
            pygame.draw.circle(surf, (86, 118, 66), (mx, my),
                               rng.randint(2, 3))

    # Small chips around the base
    for _ in range(rng.randint(2, 4)):
        px = cx + rng.randint(-int(size * 1.4), int(size * 1.4))
        py = base_y + rng.randint(-3, 4)
        r = rng.randint(2, 4)
        pygame.draw.circle(surf, mid, (px, py), r)
        pygame.draw.circle(surf, edge, (px, py), r, 1)

    return surf


def _make_boulder(rng):
    """A large multi-lobed boulder (bigger than _make_rock)."""
    w, h = 96, 78
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 10

    palettes = [
        ((172, 164, 150), (128, 118, 104), (82, 74, 66)),
        ((158, 156, 158), (116, 116, 122), (72, 72, 78)),
        ((160, 138, 116), (112, 96, 78), (72, 62, 48)),
    ]
    base, mid, dark = rng.choice(palettes)
    light = _shade(base, 1.24)
    edge = _shade(dark, 0.72)

    _shadow(surf, cx, base_y + 6, 40, 9, alpha=110)

    # Main lobe
    size = rng.randint(28, 34)
    def lobe(off_x, off_y, scale):
        n = rng.randint(7, 9)
        pts = []
        for k in range(n):
            a = -math.pi * 0.9 + k * (math.pi * 1.8 / (n - 1))
            r = size * scale * rng.uniform(0.82, 1.05)
            pts.append((cx + off_x + math.cos(a) * r,
                        base_y + off_y + math.sin(a) * r * 0.6))
        return pts

    # Two overlapping lobes for the boulder silhouette
    left_lobe = lobe(-size * 0.35, 0, 0.75)
    right_lobe = lobe(size * 0.35, 2, 0.85)
    main_lobe = lobe(0, -2, 1.0)

    for L in (left_lobe, right_lobe, main_lobe):
        pygame.draw.polygon(surf, mid, L)
    for L in (left_lobe, right_lobe, main_lobe):
        pygame.draw.polygon(surf, edge, L, 2)

    # Highlight on the upper-left of the whole formation
    hl = [
        (cx - size * 0.95, base_y - size * 0.55),
        (cx - size * 0.35, base_y - size * 0.95),
        (cx + size * 0.20, base_y - size * 0.85),
        (cx - size * 0.45, base_y - size * 0.40),
    ]
    pygame.draw.polygon(surf, light, hl)

    # Strata lines
    for i in range(4):
        y_band = base_y - size + i * size // 3
        pygame.draw.line(surf, _shade(mid, 0.84 + i * 0.08),
                         (cx - size * 1.05, y_band + 2),
                         (cx + size * 1.05, y_band + 2), 1)

    # Cracks
    for _ in range(rng.randint(3, 5)):
        x0 = cx + rng.randint(-int(size * 1.1), int(size * 1.1))
        y0 = base_y - rng.randint(4, size)
        ang = rng.uniform(-0.5, 0.5) + math.pi / 2
        ln = rng.randint(6, 12)
        pygame.draw.line(surf, edge, (x0, y0),
                         (int(x0 + math.cos(ang) * ln),
                          int(y0 + math.sin(ang) * ln)), 1)

    # Mossy patches
    for _ in range(rng.randint(3, 6)):
        mx = cx + rng.randint(-int(size * 1.2), int(size * 0.4))
        my = base_y - rng.randint(0, 6)
        pygame.draw.circle(surf, (84, 116, 64), (mx, my),
                           rng.randint(2, 4))

    return surf


def _make_small_rock(rng):
    w = 30
    h = 24
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 4

    palettes = [
        ((150, 142, 130), (110, 102, 92), (74, 68, 60)),
        ((148, 148, 150), (108, 108, 112), (72, 72, 78)),
        ((146, 128, 108), (106, 92, 76), (70, 60, 46)),
    ]
    base, mid, dark = rng.choice(palettes)
    light = _shade(base, 1.22)
    edge = _shade(dark, 0.72)

    _shadow(surf, cx, base_y + 2, 12, 3, alpha=80)

    size = rng.randint(8, 11)
    pts = []
    for k in range(6):
        a = -math.pi * 0.9 + k * (math.pi * 1.8 / 5)
        r = size * rng.uniform(0.85, 1.05)
        pts.append((cx + math.cos(a) * r,
                    base_y - 2 + math.sin(a) * r * 0.6))
    pygame.draw.polygon(surf, mid, pts)
    pygame.draw.polygon(surf, edge, pts, 1)

    pygame.draw.polygon(surf, light, [
        (cx - size * 0.5, base_y - size * 0.35),
        (cx - size * 0.05, base_y - size * 0.7),
        (cx + size * 0.25, base_y - size * 0.4),
    ])

    return surf


def _make_stone_pile(rng):
    """A cluster of 5–8 medium and small stones."""
    w, h = 56, 40
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 6

    palettes = [
        ((160, 152, 138), (120, 110, 96), (78, 70, 60)),
        ((154, 154, 156), (114, 114, 118), (72, 72, 78)),
        ((156, 136, 112), (114, 96, 78), (74, 62, 46)),
    ]
    base, mid, dark = rng.choice(palettes)
    light = _shade(base, 1.22)
    edge = _shade(dark, 0.7)

    _shadow(surf, cx, base_y + 3, 22, 5, alpha=95)

    for _ in range(rng.randint(5, 8)):
        ox = rng.randint(-18, 18)
        oy = rng.randint(-14, 4)
        size = rng.randint(6, 11)
        px = cx + ox
        py = base_y + oy
        pts = []
        n = rng.randint(5, 7)
        for k in range(n):
            a = -math.pi * 0.85 + k * (math.pi * 1.7 / (n - 1))
            r = size * rng.uniform(0.8, 1.05)
            pts.append((px + math.cos(a) * r,
                        py + math.sin(a) * r * 0.65))
        pygame.draw.polygon(surf, mid, pts)
        pygame.draw.polygon(surf, edge, pts, 1)
        # Tiny highlight
        pygame.draw.polygon(surf, light, [
            (px - size * 0.5, py - size * 0.3),
            (px - size * 0.05, py - size * 0.65),
            (px + size * 0.25, py - size * 0.35),
        ])

    return surf


def _make_gravel(rng):
    """A flat scatter of tiny stones."""
    w, h = 44, 22
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 4

    palettes = [
        ((158, 148, 134), (110, 102, 90)),
        ((150, 150, 152), (104, 104, 108)),
        ((148, 130, 108), (100, 88, 74)),
    ]
    base, dark = rng.choice(palettes)
    light = _shade(base, 1.25)
    edge = _shade(dark, 0.72)

    _shadow(surf, cx, base_y + 2, 18, 3, alpha=70)

    for _ in range(rng.randint(14, 22)):
        px = cx + rng.randint(-18, 18)
        py = base_y + rng.randint(-8, 2)
        r = rng.choice([1, 1, 2, 2, 3])
        col = _shade(base, rng.uniform(0.85, 1.15))
        pygame.draw.circle(surf, col, (px, py), r)
        if r >= 2:
            pygame.draw.circle(surf, light, (px - 1, py - 1), 1)
            pygame.draw.circle(surf, edge, (px, py), r, 1)

    return surf


# ---------------------------------------------------------------------------
# Bushes, flowers, grass, logs, stumps
# ---------------------------------------------------------------------------
def _make_berry_bush(rng):
    w, h = 54, 44
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 5

    leaf_cols = rng.choice([
        ((96, 156, 76), (70, 118, 56), (52, 90, 42)),
        ((76, 138, 62), (54, 104, 46), (40, 78, 36)),
    ])
    leaf_hi, leaf_mid, leaf_lo = leaf_cols

    _shadow(surf, cx, base_y + 1, 20, 6, alpha=75)

    # Base blob
    pygame.draw.ellipse(surf, leaf_lo, (cx - 22, base_y - 24, 44, 28))
    pygame.draw.ellipse(surf, leaf_mid, (cx - 20, base_y - 26, 40, 26))
    pygame.draw.ellipse(surf, leaf_hi, (cx - 14, base_y - 28, 26, 20))

    # Berries
    berry_col = rng.choice([(210, 60, 60), (230, 90, 90), (180, 40, 60)])
    berry_hi = _shade(berry_col, 1.4)
    for _ in range(rng.randint(6, 10)):
        bx = cx + rng.randint(-16, 16)
        by = base_y - rng.randint(4, 22)
        pygame.draw.circle(surf, berry_col, (bx, by), 3)
        pygame.draw.circle(surf, berry_hi, (bx - 1, by - 1), 1)
    return surf


def _make_flower_patch(rng):
    w, h = 34, 26
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 3

    # Tiny green base
    pygame.draw.ellipse(surf, (86, 132, 66), (cx - 12, base_y - 8, 24, 8))

    palette = rng.choice([
        [(232, 216, 120), (250, 235, 150)],
        [(230, 230, 235), (250, 250, 255)],
        [(218, 130, 160), (240, 165, 190)],
        [(206, 156, 220), (228, 180, 240)],
        [(240, 180, 90),  (250, 210, 130)],
    ])
    for _ in range(rng.randint(4, 7)):
        fx = cx + rng.randint(-11, 11)
        fy = base_y - rng.randint(3, 12)
        pygame.draw.circle(surf, palette[0], (fx, fy), 2)
        surf.set_at((fx, fy), palette[1])
    return surf


def _make_grass_tuft(rng):
    w, h = 22, 20
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 2
    col = rng.choice([(96, 152, 76), (118, 176, 90), (76, 128, 62)])
    dark = _shade(col, 0.7)
    for _ in range(rng.randint(5, 8)):
        x = cx + rng.randint(-6, 6)
        length = rng.randint(6, 11)
        tip_x = x + rng.randint(-3, 3)
        pygame.draw.line(surf, col, (x, base_y), (tip_x, base_y - length), 1)
        pygame.draw.line(surf, dark, (x, base_y), (x, base_y - length // 2), 1)
    return surf


def _make_fallen_log(rng):
    w, h = 60, 24
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    base_y = h - 6
    bark = (108, 74, 44)
    bark_dark = (74, 48, 28)
    bark_hi = (140, 100, 62)
    ring = (150, 108, 66)

    _shadow(surf, w // 2, base_y + 2, 24, 4, alpha=70)

    # Log body — slight diagonal
    lean = rng.randint(-3, 3)
    pts = [
        (6, base_y - 4),
        (6, base_y - 12),
        (w - 8, base_y - 14 + lean),
        (w - 8, base_y - 4 + lean),
    ]
    pygame.draw.polygon(surf, bark, pts)
    pygame.draw.polygon(surf, bark_dark, pts, 2)
    # Highlight line
    pygame.draw.line(surf, bark_hi,
                     (8, base_y - 11), (w - 10, base_y - 12 + lean), 2)
    # End cap
    pygame.draw.ellipse(surf, ring, (w - 12, base_y - 14 + lean, 8, 10))
    pygame.draw.ellipse(surf, bark_dark, (w - 12, base_y - 14 + lean, 8, 10), 1)
    pygame.draw.ellipse(surf, _shade(ring, 1.15), (w - 10, base_y - 11 + lean, 3, 4))
    return surf


def _make_stump(rng):
    w, h = 34, 26
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 4
    bark = (112, 78, 46)
    bark_dark = (72, 46, 26)
    ring_col = (166, 122, 76)
    ring_dark = (110, 78, 46)

    _shadow(surf, cx, base_y + 1, 12, 4, alpha=75)

    # Trunk
    pygame.draw.rect(surf, bark, (cx - 8, base_y - 12, 16, 12))
    pygame.draw.rect(surf, bark_dark, (cx - 8, base_y - 12, 16, 12), 1)
    # Top face with growth rings
    pygame.draw.ellipse(surf, ring_col, (cx - 9, base_y - 16, 18, 8))
    pygame.draw.ellipse(surf, ring_dark, (cx - 9, base_y - 16, 18, 8), 1)
    pygame.draw.ellipse(surf, ring_dark, (cx - 5, base_y - 14, 10, 4), 1)
    pygame.draw.ellipse(surf, ring_dark, (cx - 2, base_y - 12, 4, 2))
    return surf


# ---------------------------------------------------------------------------
# Resource deposits
# ---------------------------------------------------------------------------
def _make_stone_deposit(rng):
    w, h = 70, 56
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 6

    base = (150, 148, 142)
    light = _shade(base, 1.25)
    dark = _shade(base, 0.7)
    warmer = (176, 168, 148)

    _shadow(surf, cx, base_y + 2, 26, 8, alpha=80)

    # Cluster of 3-4 angular rocks
    for (ox, oy, size, col) in [
        (-14, 0, 14, base),
        ( 10, 0, 15, base),
        (  0, -8, 12, warmer),
    ]:
        pts = []
        for k in range(7):
            ang = -math.pi * 0.9 + k * (math.pi * 1.8 / 6)
            r = size * rng.uniform(0.85, 1.05)
            x = cx + ox + math.cos(ang) * r
            y = base_y + oy + math.sin(ang) * r * 0.55
            pts.append((x, y))
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, dark, pts, 2)
        # Top highlight
        top_pts = [
            (cx + ox - size * 0.5, base_y + oy - size * 0.35),
            (cx + ox, base_y + oy - size * 0.65),
            (cx + ox + size * 0.35, base_y + oy - size * 0.35),
        ]
        pygame.draw.polygon(surf, light, top_pts)
    return surf


def _make_iron_deposit(rng):
    w, h = 72, 58
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    base_y = h - 6

    base = (128, 118, 112)
    light = _shade(base, 1.35)
    dark = _shade(base, 0.65)
    vein = (200, 106, 60)
    vein_hi = (240, 160, 90)

    _shadow(surf, cx, base_y + 2, 28, 8, alpha=80)

    # Cluster of angular chunks
    for (ox, oy, size, col) in [
        (-14, 0, 15, base),
        ( 12, 0, 16, base),
        (  0, -10, 13, light),
    ]:
        pts = []
        for k in range(7):
            ang = -math.pi * 0.9 + k * (math.pi * 1.8 / 6)
            r = size * rng.uniform(0.8, 1.05)
            x = cx + ox + math.cos(ang) * r
            y = base_y + oy + math.sin(ang) * r * 0.55
            pts.append((x, y))
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, dark, pts, 2)

        # Orange veins
        for _ in range(rng.randint(1, 3)):
            x0 = cx + ox + rng.randint(-size, size)
            y0 = base_y + oy + rng.randint(-size // 2, size // 2)
            x1 = x0 + rng.randint(-4, 4)
            y1 = y0 + rng.randint(-5, 5)
            pygame.draw.line(surf, vein, (x0, y0), (x1, y1), 2)
            pygame.draw.line(surf, vein_hi, (x0, y0), (x1, y1), 1)

    return surf


# ---------------------------------------------------------------------------
# Sprite cache
# ---------------------------------------------------------------------------
class PropSprites:
    _cache = {}

    @classmethod
    def get(cls, kind, variant):
        key = (kind, variant)
        surf = cls._cache.get(key)
        if surf is None:
            surf = cls._generate(kind, variant)
            cls._cache[key] = surf
        return surf

    @classmethod
    def _generate(cls, kind, variant):
        rng = random.Random(kind * 7919 + variant * 6271 + 13)
        if kind == TREE_ROUND:
            return _make_round_tree(rng)
        if kind == TREE_PINE:
            return _make_pine_tree(rng)
        if kind == ROCK:
            return _make_rock(rng)
        if kind == BERRY_BUSH:
            return _make_berry_bush(rng)
        if kind == STONE_DEPOSIT:
            return _make_stone_deposit(rng)
        if kind == IRON_DEPOSIT:
            return _make_iron_deposit(rng)
        if kind == FLOWER_PATCH:
            return _make_flower_patch(rng)
        if kind == GRASS_TUFT:
            return _make_grass_tuft(rng)
        if kind == FALLEN_LOG:
            return _make_fallen_log(rng)
        if kind == STUMP:
            return _make_stump(rng)
        if kind == SMALL_ROCK:
            return _make_small_rock(rng)
        if kind == BOULDER:
            return _make_boulder(rng)
        if kind == STONE_PILE:
            return _make_stone_pile(rng)
        if kind == GRAVEL:
            return _make_gravel(rng)
        return pygame.Surface((2, 2), pygame.SRCALPHA)


# ---------------------------------------------------------------------------
# Prop entity
# ---------------------------------------------------------------------------
class Prop:
    __slots__ = (
        "kind", "col", "row", "ox", "oy", "variant", "sprite",
        "resource_type", "amount", "max_amount", "alive",
    )

    def __init__(self, kind, col, row, ox, oy, variant):
        self.kind = kind
        self.col = col
        self.row = row
        self.ox = ox
        self.oy = oy
        self.variant = variant
        self.sprite = PropSprites.get(kind, variant)

        self.resource_type = PROP_RESOURCE_TYPE.get(kind)
        self.max_amount = PROP_CAPACITY.get(kind, 0)
        self.amount = self.max_amount
        self.alive = True

    def is_resource(self):
        return self.resource_type is not None

    def has_resources(self):
        return self.resource_type is not None and self.amount > 0 and self.alive

    def harvest(self, amount):
        if amount <= 0 or self.amount <= 0 or not self.alive:
            return 0
        taken = min(amount, self.amount)
        self.amount -= taken
        if self.amount <= 0:
            self.alive = False
        return taken

    def world_position(self):
        from . import config as C
        hw = C.TILE_HALF_W
        hh = C.TILE_HALF_H
        wx = (self.col - self.row) * hw + self.ox
        wy = (self.col + self.row) * hh + self.oy
        return wx, wy