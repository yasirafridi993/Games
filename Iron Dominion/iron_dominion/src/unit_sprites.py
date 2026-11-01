"""Procedurally generated unit sprites.

Every unit is drawn as a layered isometric character:
    shadow → legs → torso → arms → head → helmet/hair → weapon

Design
------
* 4 facings: NE, SE, SW, NW (viewer sees front-right, back-right,
  back-left, front-left respectively).
* 4 states: idle, walk, work, attack
* 4 phases per state for smooth animation.
* Consistent upper-left light: face and back shade differently.
* Signatures per kind so units read clearly at a glance:
    worker   = brown tunic, tan apron, leather cap
    swordsman= steel chain + blue tabard + round shield
    spearman = red tunic + leather jerkin + long spear + round shield
    archer   = green tunic + hood + bow + quiver
    cavalry  = steel armour on a barded horse, lance, kite shield

All sprites keep the "shadow at height-3" convention so the renderer's
ground-alignment code stays valid.
"""

import math
import random

import pygame


# ---------------------------------------------------------------------------
# Facing constants (must match renderer / units.py)
# ---------------------------------------------------------------------------
DIR_NE = 0
DIR_SE = 1
DIR_SW = 2
DIR_NW = 3

# Tilt helper: +1 when the unit is drawn looking to the right, -1 to left
_TILT = {DIR_NE: +1, DIR_SE: +1, DIR_SW: -1, DIR_NW: -1}

# Which side of the character the viewer sees
# SE / NW -> right side or full front
# NE     -> back (light)
# SW     -> back (dark)   (we only render front for SE and back for NE)
_FRONT = {DIR_SE, DIR_SW}
_BACK  = {DIR_NE, DIR_NW}


# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
SKIN       = (222, 184, 148)
SKIN_SHADE = (176, 138, 106)
SKIN_DARK  = (140, 106, 78)
HAIR       = (86, 58, 38)
HAIR_LIGHT = (130, 90, 58)

STEEL      = (176, 182, 190)
STEEL_HI   = (222, 226, 232)
STEEL_DK   = (98, 104, 112)
STEEL_EDGE = (56, 60, 66)

IRON       = (144, 148, 156)
IRON_DK    = (86, 90, 98)

WOOD       = (128, 90, 56)
WOOD_DK    = (86, 58, 34)
WOOD_HI    = (172, 128, 84)

LEATHER    = (132, 92, 54)
LEATHER_DK = (92, 62, 36)

BOW_WOOD   = (122, 82, 46)
BOW_DARK   = (82, 54, 30)

BOOT       = (68, 46, 30)
BOOT_HI    = (104, 74, 46)

CLOTH_BLUE   = (74, 108, 178)
CLOTH_BLUE_D = (44, 68, 124)
CLOTH_BLUE_L = (108, 146, 214)

CLOTH_RED    = (176, 60, 52)
CLOTH_RED_D  = (120, 38, 32)
CLOTH_RED_L  = (216, 96, 84)

CLOTH_GREEN   = (96, 148, 82)
CLOTH_GREEN_D = (62, 106, 54)
CLOTH_GREEN_L = (136, 190, 112)

CLOTH_TAN    = (200, 168, 122)
CLOTH_TAN_D  = (150, 120, 82)
CLOTH_TAN_L  = (232, 202, 158)

GOLD       = (206, 168, 76)
GOLD_HI    = (238, 202, 108)
GOLD_DK    = (138, 108, 42)

HORSE_BODY = (140, 92, 56)
HORSE_HI   = (184, 132, 84)
HORSE_DK   = (92, 58, 34)
HORSE_MANE = (72, 46, 28)

# Accent colours per unit kind (used for cloth / armour highlight)
ACCENT = {
    "worker":    CLOTH_TAN,
    "swordsman": CLOTH_BLUE,
    "spearman":  CLOTH_RED,
    "archer":    CLOTH_GREEN,
    "cavalry":   CLOTH_BLUE,   # same family as swordsman for cohesion
}


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------
def _shade(c, f):
    return (max(0, min(255, int(c[0] * f))),
            max(0, min(255, int(c[1] * f))),
            max(0, min(255, int(c[2] * f))))


def _mix(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def _shadow(surf, cx, foot_y, w):
    """Soft ground shadow ellipse, standard `_shadow` convention at h-3."""
    sh_w = int(w * 0.9)
    sh_h = max(4, int(w * 0.30))
    sh = pygame.Surface((sh_w * 2, sh_h * 2), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 90), sh.get_rect())
    surf.blit(sh, (cx - sh_w, foot_y - sh_h + 1))


# ---------------------------------------------------------------------------
# Body part renderers
# ---------------------------------------------------------------------------
def _draw_legs(surf, cx, foot_y, tilt, color, hi, offsets, boots=True):
    """Two legs. offsets = ((l_dx, l_dy), (r_dx, r_dy))."""
    l_off, r_off = offsets
    leg_w = 4
    leg_h = 8
    # Left leg
    lx = cx - 4 + tilt * 1 + l_off[0]
    ly = foot_y - leg_h + l_off[1]
    pygame.draw.rect(surf, color, (lx, ly, leg_w, leg_h + 2))
    pygame.draw.rect(surf, hi, (lx, ly, 1, leg_h + 2))
    # Right leg
    rx = cx + 1 + tilt * 1 + r_off[0]
    ry = foot_y - leg_h + r_off[1]
    pygame.draw.rect(surf, color, (rx, ry, leg_w, leg_h + 2))
    pygame.draw.rect(surf, hi, (rx, ry, 1, leg_h + 2))
    # Boots
    if boots:
        pygame.draw.rect(surf, BOOT, (lx - 1, ly + leg_h, leg_w + 1, 3))
        pygame.draw.rect(surf, BOOT, (rx - 1, ry + leg_h, leg_w + 1, 3))
        pygame.draw.rect(surf, BOOT_HI, (lx - 1, ly + leg_h, leg_w + 1, 1))
        pygame.draw.rect(surf, BOOT_HI, (rx - 1, ry + leg_h, leg_w + 1, 1))


def _draw_torso(surf, cx, top_y, w, h, base, shade_col, hi_col,
                belt=True, pauldron=False, tabard=False, tabard_col=None):
    """Simple vertical torso block with shading and optional accessories."""
    left = cx - w // 2
    # Main block
    pygame.draw.rect(surf, base, (left, top_y, w, h))
    # Left highlight stripe
    pygame.draw.rect(surf, hi_col, (left, top_y, 2, h))
    # Right shadow stripe
    pygame.draw.rect(surf, shade_col, (left + w - 2, top_y, 2, h))
    # Horizontal shading gradient
    for i in range(3, w - 3):
        x = left + i
        t = (i - 3) / max(1, w - 6)
        col = _mix(hi_col, shade_col, t)
        pygame.draw.line(surf, col, (x, top_y + 1), (x, top_y + h - 1))
    # Fine edge seams make cloth and armor read as layered materials.
    pygame.draw.line(surf, _shade(shade_col, 0.82),
                     (left + 1, top_y + 3), (left + 1, top_y + h - 4), 1)
    pygame.draw.line(surf, hi_col,
                     (left + 2, top_y + 2), (left + w - 3, top_y + 2), 1)
    # Belt
    if belt:
        pygame.draw.rect(surf, WOOD_DK, (left, top_y + h - 3, w, 2))
        pygame.draw.rect(surf, GOLD, (cx - 1, top_y + h - 3, 3, 2))
    # Tabard centre stripe
    if tabard and tabard_col is not None:
        pygame.draw.rect(surf, tabard_col, (cx - 3, top_y + 2, 6, h - 4))
        pygame.draw.rect(surf, _shade(tabard_col, 1.25),
                         (cx - 3, top_y + 2, 1, h - 4))
        pygame.draw.line(surf, _shade(tabard_col, 0.62),
                         (cx + 2, top_y + 3), (cx + 2, top_y + h - 4), 1)
        for stitch_y in range(top_y + 4, top_y + h - 4, 4):
            pygame.draw.line(surf, _shade(tabard_col, 1.38),
                             (cx - 4, stitch_y), (cx - 3, stitch_y), 1)
    # Pauldrons
    if pauldron:
        pygame.draw.ellipse(surf, STEEL,
                            (left - 3, top_y - 2, 6, 6))
        pygame.draw.ellipse(surf, STEEL_HI,
                            (left - 2, top_y - 1, 4, 3))
        pygame.draw.ellipse(surf, STEEL,
                            (left + w - 3, top_y - 2, 6, 6))
        pygame.draw.ellipse(surf, STEEL_HI,
                            (left + w - 2, top_y - 1, 4, 3))
        pygame.draw.circle(surf, GOLD_DK, (left, top_y + 1), 1)
        pygame.draw.circle(surf, GOLD_DK, (left + w - 1, top_y + 1), 1)


def _draw_arms(surf, cx, torso_top, torso_w, torso_h, tilt,
               arm_offsets, hand_col=SKIN):
    """Two arms hanging or swinging. arm_offsets = (l_dy, r_dy)."""
    l_dy, r_dy = arm_offsets
    arm_w = 3
    arm_h = 8
    # Left arm
    lx = cx - torso_w // 2 - arm_w + 1
    ly = torso_top + 2 + l_dy
    pygame.draw.rect(surf, SKIN_SHADE, (lx, ly, arm_w, arm_h))
    pygame.draw.rect(surf, SKIN, (lx + 1, ly, arm_w - 1, arm_h))
    # Right arm
    rx = cx + torso_w // 2 - 1
    ry = torso_top + 2 + r_dy
    pygame.draw.rect(surf, SKIN_SHADE, (rx, ry, arm_w, arm_h))
    pygame.draw.rect(surf, SKIN, (rx, ry, arm_w - 1, arm_h))


def _draw_head(surf, cx, top_y, tilt, helmet=None, hair=False, hood=False,
               facing_right=True):
    """Head with face or helmet. `helmet` ∈ {None, 'nasal', 'plume',
    'conical', 'hood', 'cap'}."""
    head_w = 9
    head_h = 9
    hx = cx - head_w // 2 + tilt
    # Neck
    pygame.draw.rect(surf, SKIN_SHADE, (cx - 2, top_y - 2, 4, 3))

    if helmet == "hood":
        # Hood covers most of the head; show a sliver of face
        pygame.draw.polygon(surf, CLOTH_GREEN_D, [
            (hx - 1, top_y + head_h),
            (hx - 1, top_y),
            (hx + head_w, top_y - 2),
            (hx + head_w + 1, top_y + head_h),
        ])
        pygame.draw.polygon(surf, CLOTH_GREEN, [
            (hx, top_y + 2),
            (hx + 1, top_y + 1),
            (hx + head_w - 1, top_y),
            (hx + head_w, top_y + head_h - 3),
            (hx, top_y + head_h - 3),
        ])
        # Face
        pygame.draw.ellipse(surf, SKIN, (hx + 2, top_y + 3, 6, 5))
        pygame.draw.circle(surf, (28, 20, 16),
                           (hx + (6 if facing_right else 3), top_y + 5), 1)
        return

    if helmet == "cap":
        pygame.draw.ellipse(surf, SKIN,
                            (hx, top_y + 2, head_w, head_h))
        pygame.draw.ellipse(surf, LEATHER,
                            (hx - 1, top_y - 1, head_w + 2, 5))
        pygame.draw.ellipse(surf, _shade(LEATHER, 1.25),
                            (hx - 1, top_y - 1, head_w + 2, 3))
        pygame.draw.circle(surf, (28, 20, 16),
                           (hx + (6 if facing_right else 3), top_y + 6), 1)
        return

    # Base skull
    pygame.draw.ellipse(surf, SKIN, (hx, top_y, head_w, head_h))
    # Jaw shadow
    pygame.draw.ellipse(surf, SKIN_SHADE, (hx, top_y + 5, head_w, 4))
    # Eye
    eye_x = hx + (6 if facing_right else 3)
    pygame.draw.circle(surf, (28, 20, 16), (eye_x, top_y + 4), 1)

    if hair:
        pygame.draw.ellipse(surf, HAIR, (hx - 1, top_y - 1, head_w + 2, 4))
        pygame.draw.ellipse(surf, HAIR_LIGHT,
                            (hx, top_y - 1, 4, 2))

    if helmet == "nasal":
        # Steel cap with nasal guard
        pygame.draw.ellipse(surf, STEEL, (hx - 1, top_y - 2, head_w + 2, 7))
        pygame.draw.ellipse(surf, STEEL_HI, (hx, top_y - 1, head_w - 1, 3))
        pygame.draw.rect(surf, STEEL_DK,
                         (hx + (5 if facing_right else 3),
                          top_y + 2, 2, 4))
        pygame.draw.rect(surf, STEEL_EDGE,
                         (hx + (5 if facing_right else 3),
                          top_y + 2, 2, 4), 1)

    elif helmet == "plume":
        # Round helm with a plume
        pygame.draw.ellipse(surf, STEEL, (hx - 1, top_y - 3, head_w + 2, 8))
        pygame.draw.ellipse(surf, STEEL_HI,
                            (hx, top_y - 2, head_w - 1, 3))
        # Cheek guards
        pygame.draw.rect(surf, STEEL_DK, (hx - 2, top_y + 2, 2, 5))
        pygame.draw.rect(surf, STEEL_DK, (hx + head_w, top_y + 2, 2, 5))
        # Plume
        pygame.draw.ellipse(surf, CLOTH_RED,
                            (hx + 1, top_y - 8, 5, 8))
        pygame.draw.ellipse(surf, CLOTH_RED_L,
                            (hx + 1, top_y - 8, 3, 5))

    elif helmet == "conical":
        pygame.draw.polygon(surf, STEEL, [
            (hx - 2, top_y + head_h - 1),
            (hx + head_w + 2, top_y + head_h - 1),
            (hx + head_w // 2, top_y - 4),
        ])
        pygame.draw.polygon(surf, STEEL_HI, [
            (hx - 1, top_y + head_h - 2),
            (hx + head_w // 2, top_y - 3),
            (hx + head_w // 2 - 1, top_y + head_h - 2),
        ])
        pygame.draw.rect(surf, STEEL_DK,
                         (hx - 2, top_y + head_h - 3,
                          head_w + 4, 3))


# ---------------------------------------------------------------------------
# Weapon renderers
# ---------------------------------------------------------------------------
def _draw_sword(surf, x, y, ang, length=16):
    """Straight steel sword. ang in radians (0 = pointing right)."""
    # Handle
    hx = x - math.cos(ang) * 3
    hy = y - math.sin(ang) * 3
    pygame.draw.line(surf, WOOD_DK, (x, y), (hx, hy), 2)
    # Guard
    gx = x - math.cos(ang) * 1
    gy = y - math.sin(ang) * 1
    n_x = -math.sin(ang)
    n_y = math.cos(ang)
    pygame.draw.line(surf, GOLD,
                     (gx - n_x * 3, gy - n_y * 3),
                     (gx + n_x * 3, gy + n_y * 3), 2)
    # Blade
    bx = x + math.cos(ang) * length
    by = y + math.sin(ang) * length
    pygame.draw.line(surf, STEEL_DK, (gx, gy), (bx, by), 3)
    pygame.draw.line(surf, STEEL, (gx, gy), (bx, by), 2)
    pygame.draw.line(surf, STEEL_HI,
                     (gx - n_x * 1, gy - n_y * 1),
                     (bx - n_x * 1, by - n_y * 1), 1)


def _draw_spear(surf, x, y, ang, length=26):
    """Long spear with a metal tip."""
    ex = x + math.cos(ang) * length
    ey = y + math.sin(ang) * length
    # Shaft
    pygame.draw.line(surf, WOOD_DK, (x, y), (ex, ey), 2)
    pygame.draw.line(surf, WOOD, (x, y), (ex, ey), 1)
    # Tip
    n_x = -math.sin(ang)
    n_y = math.cos(ang)
    tip = (ex + math.cos(ang) * 4, ey + math.sin(ang) * 4)
    pygame.draw.polygon(surf, STEEL, [
        (ex + n_x * 2, ey + n_y * 2),
        tip,
        (ex - n_x * 2, ey - n_y * 2),
    ])
    pygame.draw.polygon(surf, STEEL_HI, [
        (ex + n_x * 1, ey + n_y * 1),
        tip,
        (ex - n_x * 0.5, ey - n_y * 0.5),
    ])
    # Leather grip
    pygame.draw.line(surf, LEATHER,
                     (x + math.cos(ang) * 4, y + math.sin(ang) * 4),
                     (x + math.cos(ang) * 8, y + math.sin(ang) * 8), 1)


def _draw_bow(surf, x, y, facing_right):
    """Curved bow with string."""
    if facing_right:
        pygame.draw.arc(surf, BOW_WOOD,
                        pygame.Rect(x - 6, y - 10, 12, 20),
                        -1.5, 1.5, 2)
        pygame.draw.arc(surf, BOW_DARK,
                        pygame.Rect(x - 6, y - 10, 12, 20),
                        -1.5, 1.5, 1)
        pygame.draw.line(surf, (232, 232, 220),
                         (x, y - 10), (x, y + 10), 1)
    else:
        pygame.draw.arc(surf, BOW_WOOD,
                        pygame.Rect(x - 6, y - 10, 12, 20),
                        math.pi - 1.5, math.pi + 1.5, 2)
        pygame.draw.arc(surf, BOW_DARK,
                        pygame.Rect(x - 6, y - 10, 12, 20),
                        math.pi - 1.5, math.pi + 1.5, 1)
        pygame.draw.line(surf, (232, 232, 220),
                         (x, y - 10), (x, y + 10), 1)


def _draw_quiver(surf, x, y, rng):
    """Archer quiver on the back, with arrow fletchings."""
    pygame.draw.rect(surf, LEATHER_DK, (x, y, 5, 12))
    pygame.draw.rect(surf, LEATHER, (x + 1, y, 3, 12))
    for i in range(3):
        ax = x + 1 + i * 1.5
        pygame.draw.line(surf, WOOD_DK, (ax, y), (ax, y - 4), 1)
        pygame.draw.circle(surf, CLOTH_RED, (int(ax), y - 4), 1)


def _draw_shield(surf, x, y, w, h, colour, emblem=True):
    """Kite shield with a coloured field."""
    pts = [
        (x - w // 2, y - h // 2),
        (x + w // 2, y - h // 2),
        (x + w // 2, y + h // 4),
        (x, y + h // 2),
        (x - w // 2, y + h // 4),
    ]
    pygame.draw.polygon(surf, colour, pts)
    pygame.draw.polygon(surf, _shade(colour, 0.6), pts, 1)
    # Highlight
    pygame.draw.line(surf, _shade(colour, 1.3),
                     (x - w // 2 + 1, y - h // 2 + 1),
                     (x - w // 2 + 1, y + h // 4), 1)
    if emblem:
        pygame.draw.rect(surf, GOLD,
                         (x - 1, y - h // 4, 3, 6))
        pygame.draw.rect(surf, GOLD_DK,
                         (x - 2, y - h // 4 + 1, 5, 2))


# ---------------------------------------------------------------------------
# Attack animation offsets
# ---------------------------------------------------------------------------
def _walk_offsets(phase):
    """Leg and arm offsets for a walk cycle."""
    # Phases: 0 = neutral, 1 = step L, 2 = neutral, 3 = step R
    if phase == 0:
        return (0, 0), (0, 0), (0, 0), (0, 0)
    if phase == 1:
        return (-2, 0), (2, -1), (0, 1), (0, -1)
    if phase == 2:
        return (0, -1), (0, -1), (0, 0), (0, 0)
    return (2, 0), (-2, -1), (0, -1), (0, 1)


def _idle_offsets(phase):
    """Gentle breathing for idle."""
    bob = (0, -1, 0, 1)[phase]
    return (0, 0), (0, 0), (0, bob), (0, bob)


def _attack_offsets(phase):
    """Wind-up → strike → recovery → back to ready."""
    # (l_leg, r_leg, l_arm, r_arm) — l_arm is the front/support arm,
    # r_arm is the weapon arm
    if phase == 0:
        return (0, 0), (0, 0), (0, 0), (0, 0)
    if phase == 1:
        return (-1, 0), (1, 0), (0, 2), (0, -2)   # wind up
    if phase == 2:
        return (-2, 0), (2, 0), (0, -2), (0, 3)   # strike
    return (0, 0), (0, 0), (0, 0), (0, 1)          # recover


# ---------------------------------------------------------------------------
# Sprite generation
# ---------------------------------------------------------------------------
def _sprite(kind, facing, state, phase):
    """Dispatch: returns the finished surface for the given key."""
    if kind == "worker":
        return _worker(facing, state, phase)
    if kind == "swordsman":
        return _swordsman(facing, state, phase)
    if kind == "spearman":
        return _spearman(facing, state, phase)
    if kind == "archer":
        return _archer(facing, state, phase)
    if kind == "cavalry":
        return _cavalry(facing, state, phase)
    return pygame.Surface((2, 2), pygame.SRCALPHA)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
def _worker(facing, state, phase):
    W, H = 34, 44
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    foot_y = H - 6
    tilt = _TILT[facing]

    _shadow(surf, cx + tilt, foot_y, 9)

    if state == "walk":
        l_off, r_off, l_arm, r_arm = _walk_offsets(phase)
    elif state == "work":
        l_off, r_off, l_arm, r_arm = _attack_offsets(phase)
    elif state == "attack":
        l_off, r_off, l_arm, r_arm = _attack_offsets(phase)
    else:
        l_off, r_off, l_arm, r_arm = _idle_offsets(phase)

    # Legs (no boots — worker in cloth trousers + leather boots)
    _draw_legs(surf, cx, foot_y, tilt, CLOTH_TAN_D, CLOTH_TAN_L,
               (l_off, r_off))

    # Torso: tan tunic with leather apron
    torso_top = foot_y - 24
    _draw_torso(surf, cx + tilt, torso_top, 12, 15,
                CLOTH_TAN, CLOTH_TAN_D, CLOTH_TAN_L,
                belt=True, tabard=False)
    # Leather apron front
    pygame.draw.polygon(surf, LEATHER, [
        (cx - 5 + tilt, torso_top + 5),
        (cx + 5 + tilt, torso_top + 5),
        (cx + 4 + tilt, torso_top + 14),
        (cx - 4 + tilt, torso_top + 14),
    ])
    pygame.draw.polygon(surf, _shade(LEATHER, 0.6), [
        (cx - 5 + tilt, torso_top + 5),
        (cx + 5 + tilt, torso_top + 5),
        (cx + 4 + tilt, torso_top + 14),
        (cx - 4 + tilt, torso_top + 14),
    ], 1)

    # Arms
    _draw_arms(surf, cx + tilt, torso_top, 12, 15, tilt,
               (l_arm[1], r_arm[1]))

    # Head: leather cap + face
    head_y = torso_top - 8
    _draw_head(surf, cx + tilt, head_y, tilt,
               helmet="cap", hair=True,
               facing_right=(tilt > 0))

    # Tool: axe over the right shoulder while walking / idle, swings during work
    tool_x = cx + 10 + tilt
    tool_y = torso_top + 4
    if state == "work":
        swing = (-6, -3, 4, 2)[phase]
        _draw_sword(surf, tool_x, tool_y + 2 + swing, math.pi * 0.8, 10)
    else:
        _draw_sword(surf, tool_x, tool_y, -math.pi * 0.55, 10)

    return surf


# ---------------------------------------------------------------------------
# Swordsman
# ---------------------------------------------------------------------------
def _swordsman(facing, state, phase):
    W, H = 34, 48
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    foot_y = H - 6
    tilt = _TILT[facing]

    _shadow(surf, cx + tilt, foot_y, 10)

    if state == "walk":
        l_off, r_off, l_arm, r_arm = _walk_offsets(phase)
    elif state == "attack":
        l_off, r_off, l_arm, r_arm = _attack_offsets(phase)
    else:
        l_off, r_off, l_arm, r_arm = _idle_offsets(phase)

    # Legs: dark trousers + steel greaves + boots
    _draw_legs(surf, cx, foot_y, tilt, (48, 48, 56), (86, 86, 98),
               (l_off, r_off))
    # Greaves overlay
    pygame.draw.rect(surf, STEEL_DK,
                     (cx - 3 + tilt, foot_y - 5, 3, 4))
    pygame.draw.rect(surf, STEEL_DK,
                     (cx + 2 + tilt, foot_y - 5, 3, 4))

    # Torso: chainmail under a blue tabard
    torso_top = foot_y - 25
    _draw_torso(surf, cx + tilt, torso_top, 14, 16,
                STEEL_DK, STEEL_EDGE, STEEL,
                belt=True, pauldron=True, tabard=True,
                tabard_col=CLOTH_BLUE)
    # Cross on the tabard
    pygame.draw.line(surf, GOLD,
                     (cx + tilt - 3, torso_top + 6),
                     (cx + tilt + 4, torso_top + 6), 2)
    pygame.draw.line(surf, GOLD,
                     (cx + tilt, torso_top + 4),
                     (cx + tilt, torso_top + 10), 2)

    # Arms: chainmail sleeves
    _draw_arms(surf, cx + tilt, torso_top, 14, 16, tilt,
               (l_arm[1], r_arm[1]))

    # Head: steel cap with nasal guard
    head_y = torso_top - 8
    _draw_head(surf, cx + tilt, head_y, tilt,
               helmet="nasal", facing_right=(tilt > 0))

    # Shield on the front arm (left side of the sprite)
    shield_x = cx - 10 + tilt
    shield_y = torso_top + 9
    _draw_shield(surf, shield_x, shield_y, 10, 14, CLOTH_BLUE)

    # Sword on the right side; blade angle depends on state
    sw_x = cx + 11 + tilt
    sw_y = torso_top + 6
    if state == "attack":
        # Wind-up / strike / recover
        angles = (-math.pi * 0.85, -math.pi * 0.35, 0.0, -math.pi * 0.6)
        _draw_sword(surf, sw_x, sw_y, angles[phase], 14)
    elif state == "walk":
        _draw_sword(surf, sw_x, sw_y + 2, -math.pi * 0.25, 13)
    else:
        _draw_sword(surf, sw_x, sw_y + 4, -math.pi * 0.6, 14)

    return surf


# ---------------------------------------------------------------------------
# Spearman
# ---------------------------------------------------------------------------
def _spearman(facing, state, phase):
    W, H = 36, 52
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    foot_y = H - 6
    tilt = _TILT[facing]

    _shadow(surf, cx + tilt, foot_y, 10)

    if state == "walk":
        l_off, r_off, l_arm, r_arm = _walk_offsets(phase)
    elif state == "attack":
        l_off, r_off, l_arm, r_arm = _attack_offsets(phase)
    else:
        l_off, r_off, l_arm, r_arm = _idle_offsets(phase)

    # Legs: leather trousers + boots
    _draw_legs(surf, cx, foot_y, tilt, LEATHER_DK, LEATHER,
               (l_off, r_off))

    # Torso: red tabard over leather jerkin
    torso_top = foot_y - 25
    _draw_torso(surf, cx + tilt, torso_top, 13, 16,
                LEATHER, LEATHER_DK, CLOTH_TAN_L,
                belt=True, tabard=True, tabard_col=CLOTH_RED)
    # Diagonal leather strap across chest
    pygame.draw.line(surf, LEATHER_DK,
                     (cx + tilt - 6, torso_top + 1),
                     (cx + tilt + 6, torso_top + 12), 2)

    # Arms
    _draw_arms(surf, cx + tilt, torso_top, 13, 16, tilt,
               (l_arm[1], r_arm[1]))

    # Head: simple leather cap
    head_y = torso_top - 8
    _draw_head(surf, cx + tilt, head_y, tilt,
               helmet="cap", hair=False,
               facing_right=(tilt > 0))

    # Shield on the front arm
    _draw_shield(surf, cx - 10 + tilt, torso_top + 8, 9, 12, CLOTH_RED)

    # Spear on the back/right side, nearly vertical
    sp_x = cx + 12 + tilt
    sp_y = torso_top + 2
    if state == "attack":
        # Thrust angle
        angles = (-math.pi * 0.55, -math.pi * 0.45, -math.pi * 0.15,
                  -math.pi * 0.35)
        _draw_spear(surf, sp_x, sp_y, angles[phase], 28)
    else:
        _draw_spear(surf, sp_x, sp_y, -math.pi * 0.5, 28)

    return surf


# ---------------------------------------------------------------------------
# Archer
# ---------------------------------------------------------------------------
def _archer(facing, state, phase):
    W, H = 34, 48
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    foot_y = H - 6
    tilt = _TILT[facing]

    _shadow(surf, cx + tilt, foot_y, 9)

    if state == "walk":
        l_off, r_off, l_arm, r_arm = _walk_offsets(phase)
    elif state == "attack":
        l_off, r_off, l_arm, r_arm = _attack_offsets(phase)
    else:
        l_off, r_off, l_arm, r_arm = _idle_offsets(phase)

    # Legs: brown trousers + soft boots
    _draw_legs(surf, cx, foot_y, tilt, LEATHER_DK, LEATHER,
               (l_off, r_off))

    # Torso: green tunic
    torso_top = foot_y - 24
    _draw_torso(surf, cx + tilt, torso_top, 12, 15,
                CLOTH_GREEN, CLOTH_GREEN_D, CLOTH_GREEN_L,
                belt=True)
    # Leather strap for quiver
    pygame.draw.line(surf, LEATHER_DK,
                     (cx + tilt - 5, torso_top + 2),
                     (cx + tilt + 5, torso_top + 12), 2)

    # Arms
    _draw_arms(surf, cx + tilt, torso_top, 12, 15, tilt,
               (l_arm[1], r_arm[1]))

    # Head: green hood
    head_y = torso_top - 8
    _draw_head(surf, cx + tilt, head_y, tilt,
               helmet="hood", facing_right=(tilt > 0))

    # Quiver on the back
    _draw_quiver(surf, cx + 5 + tilt, torso_top + 4, None)

    # Bow: front hand holds it; draws back during attack
    bow_x = cx - 10 + tilt
    bow_y = torso_top + 8
    if state == "attack":
        pull = (2, -4, -6, -2)[phase]
        # Bow held forward
        _draw_bow(surf, bow_x, bow_y + pull, facing_right=(tilt > 0))
        # Arrow on the string
        ay = bow_y + pull + 1
        pygame.draw.line(surf, WOOD_DK,
                         (bow_x, ay), (bow_x + 6 + pull, ay), 1)
        pygame.draw.circle(surf, CLOTH_RED,
                           (bow_x + 6 + pull, ay), 1)
    else:
        _draw_bow(surf, bow_x, bow_y, facing_right=(tilt > 0))

    return surf


# ---------------------------------------------------------------------------
# Cavalry
# ---------------------------------------------------------------------------
def _cavalry(facing, state, phase):
    W, H = 58, 68
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    foot_y = H - 6
    tilt = _TILT[facing]

    _shadow(surf, cx + tilt, foot_y, 18)

    # --- Leg offsets for the horse ---
    if state == "walk":
        # Different phases for the four horse legs (l_f, r_f, l_b, r_b)
        phases = (
            (0, 0, 0, 0),
            (-2, 2, 2, -2),
            (0, -2, 0, -2),
            (2, -2, -2, 2),
        )
        lf, rf, lb, rb = phases[phase]
    elif state == "attack":
        lf = rf = lb = rb = 0
    else:
        # Subtle idle: tiny bob
        bob = (0, -1, 0, 1)[phase]
        lf = rf = lb = rb = 0

    leg_w = 3
    leg_top = foot_y - 16

    # Back legs (drawn first)
    bl_x = cx - 8 + tilt + lb
    br_x = cx + 2 + tilt + rb
    pygame.draw.rect(surf, HORSE_DK, (bl_x, leg_top, leg_w, 14))
    pygame.draw.rect(surf, HORSE_DK, (br_x, leg_top, leg_w, 14))
    # Hooves
    pygame.draw.rect(surf, (34, 24, 18), (bl_x, leg_top + 13, leg_w, 3))
    pygame.draw.rect(surf, (34, 24, 18), (br_x, leg_top + 13, leg_w, 3))

    # Horse body
    body_y = leg_top - 12
    body_w = 34
    body_h = 16
    body = pygame.Rect(cx - body_w // 2 + tilt, body_y, body_w, body_h)
    pygame.draw.ellipse(surf, HORSE_DK, body)
    pygame.draw.ellipse(surf, HORSE_BODY,
                        body.inflate(-4, -3))
    # Highlight along the back
    pygame.draw.ellipse(surf, HORSE_HI,
                        pygame.Rect(body.x + 4, body.y + 1,
                                    body.w - 12, 4))

    # Front legs (drawn over the body)
    fl_x = cx - 5 + tilt + lf
    fr_x = cx + 6 + tilt + rf
    pygame.draw.rect(surf, HORSE_DK, (fl_x, leg_top, leg_w, 14))
    pygame.draw.rect(surf, HORSE_DK, (fr_x, leg_top, leg_w, 14))
    pygame.draw.rect(surf, (34, 24, 18), (fl_x, leg_top + 13, leg_w, 3))
    pygame.draw.rect(surf, (34, 24, 18), (fr_x, leg_top + 13, leg_w, 3))

    # Neck + head
    neck_pts = [
        (cx + 8 + tilt, body_y + 1),
        (cx + 18 + tilt, body_y - 10),
        (cx + 24 + tilt, body_y - 8),
        (cx + 14 + tilt, body_y + 4),
    ]
    pygame.draw.polygon(surf, HORSE_BODY, neck_pts)
    pygame.draw.polygon(surf, HORSE_DK, neck_pts, 1)
    head_pts = [
        (cx + 18 + tilt, body_y - 12),
        (cx + 28 + tilt, body_y - 14),
        (cx + 30 + tilt, body_y - 8),
        (cx + 24 + tilt, body_y - 7),
        (cx + 19 + tilt, body_y - 9),
    ]
    pygame.draw.polygon(surf, HORSE_BODY, head_pts)
    pygame.draw.polygon(surf, HORSE_DK, head_pts, 1)
    # Mane
    pygame.draw.line(surf, HORSE_MANE,
                     (cx + 17 + tilt, body_y - 8),
                     (cx + 9 + tilt, body_y + 2), 2)
    # Eye
    pygame.draw.circle(surf, (16, 10, 6),
                       (cx + 26 + tilt, body_y - 10), 1)

    # --- Rider ---
    saddle_y = body_y - 2
    # Saddle
    pygame.draw.rect(surf, WOOD_DK,
                     (cx - 9 + tilt, saddle_y, 18, 3))
    pygame.draw.rect(surf, CLOTH_RED,
                     (cx - 9 + tilt, saddle_y + 3, 18, 2))

    # Rider legs hanging down
    pygame.draw.rect(surf, (48, 48, 56),
                     (cx - 5 + tilt, saddle_y + 2, 3, 8))
    pygame.draw.rect(surf, (48, 48, 56),
                     (cx + 3 + tilt, saddle_y + 2, 3, 8))
    pygame.draw.rect(surf, BOOT,
                     (cx - 5 + tilt, saddle_y + 9, 3, 3))
    pygame.draw.rect(surf, BOOT,
                     (cx + 3 + tilt, saddle_y + 9, 3, 3))

    # Rider torso
    torso_top = saddle_y - 14
    _draw_torso(surf, cx + tilt, torso_top, 12, 15,
                STEEL_DK, STEEL_EDGE, STEEL,
                belt=True, pauldron=True,
                tabard=True, tabard_col=CLOTH_BLUE)

    # Rider arms
    _draw_arms(surf, cx + tilt, torso_top, 12, 15, tilt,
               (0, 0))

    # Rider head: plumed helm
    head_y = torso_top - 8
    _draw_head(surf, cx + tilt, head_y, tilt,
               helmet="plume", facing_right=(tilt > 0))

    # Lance on the right
    lance_x = cx + 14 + tilt
    lance_y = torso_top + 6
    if state == "attack":
        angles = (-math.pi * 0.35, -math.pi * 0.15, 0.15, -math.pi * 0.25)
        _draw_spear(surf, lance_x, lance_y, angles[phase], 34)
    else:
        _draw_spear(surf, lance_x, lance_y, -math.pi * 0.35, 34)

    # Kite shield on the left arm
    _draw_shield(surf, cx - 12 + tilt, torso_top + 8, 11, 14, CLOTH_BLUE)

    return surf


# ---------------------------------------------------------------------------
# Public cache
# ---------------------------------------------------------------------------
class UnitSpriteCache:
    _cache = {}

    @classmethod
    def get(cls, kind, facing, state, phase):
        key = (kind, facing, state, phase)
        s = cls._cache.get(key)
        if s is None:
            s = _sprite(kind, facing, state, phase)
            cls._cache[key] = s
        return s