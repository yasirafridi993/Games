"""Track geometry (pure Python, no Panda3D).

The circuit is a closed Catmull-Rom spline through CONTROL_POINTS, resampled
into evenly spaced centre-line samples.  Everything else (road mesh, walls,
AI racing line, checkpoints, grid) is derived from those samples.

Conventions: Z is up, heading 0 faces +Y, forward = (-sin h, cos h),
"left" normal = (-ty, tx).  Positive heading = turning left.
"""
import math

from .config import NUM_CHECKPOINTS

CONTROL_POINTS = [
    (0, -200), (130, -200), (230, -185), (285, -130), (270, -55), (200, -10),
    (140, 40), (150, 115), (225, 160), (235, 235), (160, 285), (60, 265),
    (-10, 205), (-90, 215), (-190, 250), (-270, 200), (-285, 110), (-232, 35),
    (-165, -8), (-195, -85), (-203, -165), (-130, -200),
]


def wrap_angle(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


class TrackPos:
    """Result of projecting a world point onto the centre line."""
    __slots__ = ("index", "s", "lateral", "nx", "ny", "tx", "ty", "heading")


class TrackData:
    def __init__(self, control_points=None, width=20.0, spacing=5.0,
                 num_checkpoints=NUM_CHECKPOINTS, grid_start_distance=12.0,
                 grid_row_spacing=10.0, grid_lateral=3.5):
        pts = control_points or CONTROL_POINTS
        self.track_id = "custom"
        self.name = "Custom Circuit"
        self.description = "A custom procedural racing circuit."
        self.environment = "city"
        self.width = width
        self.half_width = width / 2.0
        self.grid_start_distance = grid_start_distance
        self.grid_row_spacing = grid_row_spacing
        self.grid_lateral = grid_lateral
        self.curb_width = 1.5
        self.wall_dist = self.half_width + 2.5     # inner face of the barriers
        self._resample(self._catmull_rom(pts, 30), spacing)
        self._derive()
        self.checkpoint_s = [i * self.length / num_checkpoints for i in range(num_checkpoints)]

    # ------------------------------------------------------------ building
    @staticmethod
    def _catmull_rom(pts, steps):
        n = len(pts)
        out = []
        for i in range(n):
            p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
            for k in range(steps):
                t = k / steps
                t2, t3 = t * t, t * t * t
                dimensions = 3 if len(p1) > 2 else 2
                out.append(tuple(
                    0.5 * ((2 * p1[c]) + (-p0[c] + p2[c]) * t
                           + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2
                           + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3)
                    for c in range(dimensions)))
        return out

    def _resample(self, dense, spacing):
        m = len(dense)
        cum = [0.0]
        for i in range(m):
            a, b = dense[i], dense[(i + 1) % m]
            cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        total = cum[-1]
        n = max(8, int(round(total / spacing)))
        ds = total / n
        xs, ys, zs, j = [], [], [], 0
        for k in range(n):
            target = k * ds
            while cum[j + 1] < target:
                j += 1
            a, b = dense[j], dense[(j + 1) % m]
            seg = cum[j + 1] - cum[j]
            t = (target - cum[j]) / seg if seg > 0 else 0.0
            xs.append(a[0] + (b[0] - a[0]) * t)
            ys.append(a[1] + (b[1] - a[1]) * t)
            za, zb = (a[2], b[2]) if len(a) > 2 else (0.0, 0.0)
            zs.append(za + (zb - za) * t)
        self.px, self.py, self.pz, self.n, self.ds = xs, ys, zs, n, ds
        self.length = n * ds
        self.max_elevation = max(zs)
        self.min_elevation = min(zs)

    def _derive(self):
        n, px, py = self.n, self.px, self.py
        self.sdx, self.sdy, self.sinv = [], [], []
        self.snx, self.sny, self.sheading = [], [], []
        for i in range(n):
            j = (i + 1) % n
            dx, dy = px[j] - px[i], py[j] - py[i]
            seg = math.hypot(dx, dy)
            ux, uy = dx / seg, dy / seg
            self.sdx.append(dx)
            self.sdy.append(dy)
            self.sinv.append(1.0 / (seg * seg))
            self.snx.append(-uy)
            self.sny.append(ux)
            self.sheading.append(math.atan2(-ux, uy))
        # per-sample values (tangent, normal, miter factor, curvature)
        self.tx, self.ty, self.nx, self.ny = [], [], [], []
        self.miter, self.kappa, self.heading = [], [], []
        for i in range(n):
            p = i - 1
            tx = -math.sin(self.sheading[p]) - math.sin(self.sheading[i])
            ty = math.cos(self.sheading[p]) + math.cos(self.sheading[i])
            ln = math.hypot(tx, ty)
            tx, ty = tx / ln, ty / ln
            self.tx.append(tx)
            self.ty.append(ty)
            self.nx.append(-ty)
            self.ny.append(tx)
            d = max(0.5, self.nx[i] * self.snx[i] + self.ny[i] * self.sny[i])
            self.miter.append(1.0 / d)
            self.heading.append(math.atan2(-tx, ty))
            self.kappa.append(wrap_angle(self.sheading[i] - self.sheading[p]) / self.ds)

    # ------------------------------------------------------------- queries
    def project(self, x, y, hint=None, window=10):
        """Closest centre-line point to (x, y) as a TrackPos."""
        n = self.n
        if hint is None:
            indices = range(n)
        else:
            indices = [(hint + k) % n for k in range(-window, window + 1)]
        px, py, sdx, sdy, sinv = self.px, self.py, self.sdx, self.sdy, self.sinv
        best_i, best_t, best_d = 0, 0.0, 1e18
        for i in indices:
            ax, ay = px[i], py[i]
            dx, dy = sdx[i], sdy[i]
            t = ((x - ax) * dx + (y - ay) * dy) * sinv[i]
            if t < 0.0:
                t = 0.0
            elif t > 1.0:
                t = 1.0
            qx, qy = ax + dx * t - x, ay + dy * t - y
            d2 = qx * qx + qy * qy
            if d2 < best_d:
                best_i, best_t, best_d = i, t, d2
        if hint is not None and best_d > (self.half_width * 3.0) ** 2:
            return self.project(x, y, None)
        i = best_i
        p = TrackPos()
        p.index = i
        p.s = (i + best_t) * self.ds
        p.nx, p.ny = self.snx[i], self.sny[i]
        p.lateral = (x - (px[i] + sdx[i] * best_t)) * p.nx + (y - (py[i] + sdy[i] * best_t)) * p.ny
        p.heading = self.sheading[i]
        p.tx, p.ty = -math.sin(p.heading), math.cos(p.heading)
        return p

    def point_at(self, s, lateral=0.0):
        """World (x, y, heading) at arc length s and lateral offset (+ = left)."""
        f = (s % self.length) / self.ds
        i = min(int(f), self.n - 1)
        t = f - i
        x = self.px[i] + self.sdx[i] * t + self.snx[i] * lateral
        y = self.py[i] + self.sdy[i] * t + self.sny[i] * lateral
        return x, y, self.sheading[i]

    def height_at(self, s):
        """Interpolated authored elevation at arc length s."""
        f = (s % self.length) / self.ds
        i = min(int(f), self.n - 1)
        t = f - i
        return self.pz[i] + (self.pz[(i + 1) % self.n] - self.pz[i]) * t

    def grid_slot(self, k):
        """(s, lateral) of starting-grid slot k (0 = pole)."""
        row, col = divmod(k, 2)
        s = self.length - self.grid_start_distance - row * self.grid_row_spacing - col * 4.5
        grid_lateral = min(self.grid_lateral, self.half_width * 0.55)
        lateral = grid_lateral if col == 0 else -grid_lateral
        return s, lateral

    def offset_point(self, i, lateral):
        """Mitered offset of sample i (used for meshes)."""
        i %= self.n
        m = lateral * self.miter[i]
        return self.px[i] + self.nx[i] * m, self.py[i] + self.ny[i] * m
