"""Small procedural mesh builder for Panda3D (no external model files needed).

Faces are auto-oriented: pass ``ref`` (a point inside a closed solid) or ``up``
(for flat surfaces) and the winding/normal is flipped to face the right way.
"""
import math

from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexData,
                          GeomVertexFormat, GeomVertexWriter, NodePath)

_BOX_FACES = ((0, 2, 6, 4), (1, 3, 7, 5), (0, 1, 5, 4), (2, 3, 7, 6), (0, 1, 3, 2), (4, 5, 7, 6))


def _color4(c):
    return (c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0)


def _normal(p0, p1, p2):
    ax, ay, az = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    bx, by, bz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    if ln < 1e-9:
        return None
    return nx / ln, ny / ln, nz / ln


class MeshBuilder:
    def __init__(self, name="mesh"):
        self.name = name
        self._verts = []
        self._tris = []

    # ------------------------------------------------------------ primitives
    def _add_poly(self, pts, color, ref, up, uvs):
        n = _normal(pts[0], pts[1], pts[2])
        if n is None:
            return
        flip = False
        if up is not None:
            flip = n[0] * up[0] + n[1] * up[1] + n[2] * up[2] < 0
        elif ref is not None:
            cx = sum(p[0] for p in pts) / len(pts) - ref[0]
            cy = sum(p[1] for p in pts) / len(pts) - ref[1]
            cz = sum(p[2] for p in pts) / len(pts) - ref[2]
            flip = n[0] * cx + n[1] * cy + n[2] * cz < 0
        if uvs is None:
            uvs = [(0.0, 0.0)] * len(pts)
        pts, uvs = list(pts), list(uvs)
        if flip:
            n = (-n[0], -n[1], -n[2])
            pts = [pts[0]] + pts[:0:-1]
            uvs = [uvs[0]] + uvs[:0:-1]
        col = _color4(color)
        base = len(self._verts)
        for p, uv in zip(pts, uvs):
            self._verts.append((p, n, col, uv))
        for k in range(1, len(pts) - 1):
            self._tris.append((base, base + k, base + k + 1))

    def add_tri(self, p0, p1, p2, color, ref=None, up=None, uvs=None):
        self._add_poly((p0, p1, p2), color, ref, up, uvs)

    def add_quad(self, p0, p1, p2, p3, color, ref=None, up=None, uvs=None):
        self._add_poly((p0, p1, p2, p3), color, ref, up, uvs)

    def add_hexa(self, corners, color, top_color=None):
        """Closed solid from 8 corners ordered ix + 2*iy + 4*iz."""
        ref = (sum(c[0] for c in corners) / 8.0, sum(c[1] for c in corners) / 8.0,
               sum(c[2] for c in corners) / 8.0)
        for fi, face in enumerate(_BOX_FACES):
            col = top_color if (fi == 5 and top_color is not None) else color
            self.add_quad(*[corners[i] for i in face], color=col, ref=ref)

    def add_box(self, cx, cy, cz, sx, sy, sz, color, heading=0.0, top_color=None):
        a = math.radians(heading)
        ca, sa = math.cos(a), math.sin(a)
        hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
        corners = []
        for lz in (-hz, hz):
            for ly in (-hy, hy):
                for lx in (-hx, hx):
                    corners.append((cx + lx * ca - ly * sa, cy + lx * sa + ly * ca, cz + lz))
        self.add_hexa(corners, color, top_color)

    def add_cylinder(self, cx, cy, cz, radius, length, color, axis="z",
                     segments=8, caps=True, heading=0.0):
        a = math.radians(heading)
        ca, sa = math.cos(a), math.sin(a)
        ring = [(radius * math.cos(2 * math.pi * k / segments),
                 radius * math.sin(2 * math.pi * k / segments)) for k in range(segments)]
        h = length / 2.0

        def P(u, v, w):
            if axis == "z":
                lx, ly, lz = u, v, w
            elif axis == "x":
                lx, ly, lz = w, u, v
            else:
                lx, ly, lz = u, w, v
            return (cx + lx * ca - ly * sa, cy + lx * sa + ly * ca, cz + lz)

        ref = (cx, cy, cz)
        for k in range(segments):
            k2 = (k + 1) % segments
            self.add_quad(P(*ring[k], -h), P(*ring[k2], -h), P(*ring[k2], h), P(*ring[k], h),
                          color, ref=ref)
        if caps:
            for end in (-h, h):
                for k in range(segments):
                    k2 = (k + 1) % segments
                    self.add_tri(P(0, 0, end), P(*ring[k], end), P(*ring[k2], end), color, ref=ref)

    def add_cone(self, cx, cy, base_z, radius, height, color, segments=8):
        ring = [(cx + radius * math.cos(2 * math.pi * k / segments),
                 cy + radius * math.sin(2 * math.pi * k / segments)) for k in range(segments)]
        apex = (cx, cy, base_z + height)
        ref = (cx, cy, base_z + height * 0.3)
        for k in range(segments):
            k2 = (k + 1) % segments
            a, b = ring[k], ring[k2]
            self.add_tri((a[0], a[1], base_z), (b[0], b[1], base_z), apex, color, ref=ref)
            self.add_tri((a[0], a[1], base_z), (b[0], b[1], base_z), (cx, cy, base_z), color, ref=ref)

    # ----------------------------------------------------------------- build
    def build(self):
        node = NodePath(self.name)
        if not self._tris:
            return node
        vdata = GeomVertexData(self.name, GeomVertexFormat.getV3n3c4t2(), Geom.UHStatic)
        vdata.setNumRows(len(self._verts))
        vw = GeomVertexWriter(vdata, "vertex")
        nw = GeomVertexWriter(vdata, "normal")
        cw = GeomVertexWriter(vdata, "color")
        tw = GeomVertexWriter(vdata, "texcoord")
        for p, n, c, uv in self._verts:
            vw.addData3(p[0], p[1], p[2])
            nw.addData3(n[0], n[1], n[2])
            cw.addData4(c[0], c[1], c[2], c[3])
            tw.addData2(uv[0], uv[1])
        prim = GeomTriangles(Geom.UHStatic)
        for a, b, c in self._tris:
            prim.addVertices(a, b, c)
        geom = Geom(vdata)
        geom.addPrimitive(prim)
        gnode = GeomNode(self.name)
        gnode.addGeom(geom)
        return NodePath(gnode)
