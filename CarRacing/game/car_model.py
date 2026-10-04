"""Procedural 3D car model with animated wheels (no model files required)."""
import math

from panda3d.core import TransparencyAttrib

from .meshes import MeshBuilder
from .visuals import apply_material

ROAD_Z = 0.04
FRONT_Y = 1.35
REAR_Y = -1.30
MAX_WHEEL_LOCK_DEG = 28.0


def _shade(color, k):
    return tuple(max(0.0, min(1.0, c * k)) for c in color)


class CarModel:
    def __init__(self, parent, color, definition=None):
        self.root = parent.attachNewNode("car")
        self.body_np = self.root.attachNewNode("body")
        self.style = definition.body_style if definition is not None else "coupe"
        self.livery = definition.livery if definition is not None else "double"
        self.accent_color = (definition.accent_color if definition is not None
                             else (0.92, 0.92, 0.92))
        self.spin_angle = 0.0
        self.roll = 0.0
        self.pitch = 0.0
        self._build_body(color)
        self._build_wheels()
        self._build_blob()

    # ----------------------------------------------------------------- parts
    def _build_body(self, color):
        dark = (0.05, 0.05, 0.06)
        dimensions = {
            "coupe": (1.90, 4.30, 1.24, 0.80, 1.32),
            "sports": (2.02, 4.55, 1.36, 0.76, 1.28),
            "supercar": (2.10, 4.75, 1.42, 0.62, 1.20),
            "muscle": (2.18, 4.62, 1.40, 0.92, 1.42),
            "rally": (1.96, 4.38, 1.30, 0.88, 1.45),
            "lightweight": (1.78, 3.92, 1.14, 0.72, 1.25),
            "heavy": (2.22, 4.82, 1.45, 0.90, 1.38),
        }
        width, length, roof_width, roof_length, roof_z = dimensions[self.style]
        paint = MeshBuilder("car_paint")
        paint.add_box(0, 0, 0.55, width, length, 0.50, (1, 1, 1), top_color=(1, 1, 1))
        paint.add_box(0, length * 0.36, 0.82, width * 0.89, length * 0.31, 0.06, (1, 1, 1))
        paint.add_box(0, -length * 0.09, roof_z, roof_width, roof_length, 0.06, (1, 1, 1))
        mb = MeshBuilder("car_body_trim")
        mb.add_box(0, 0, 0.32, width * 0.95, length * 0.95, 0.10, dark)
        self._add_livery(mb, width, length, roof_width, roof_length, roof_z)
        mb.add_box(0, length * 0.505, 0.39, width * 0.86, 0.12, 0.16, dark)
        mb.add_box(0, length * 0.512, 0.43, width * 0.42, 0.035, 0.075, (0.16, 0.18, 0.20))
        mb.add_box(0, length * 0.49, 0.30, width * 0.92, 0.22, 0.07, dark)
        for side in (-1, 1):
            mb.add_box(side * (width * 0.5 - 0.015), -0.02, 0.37,
                       0.14, length * 0.64, 0.11, _shade(color, 0.62))
            mb.add_box(side * width * 0.51, length * 0.08, 1.02, 0.24, 0.30, 0.14, dark)
        if self.style in ("sports", "supercar", "rally"):
            mb.add_box(0, 0.0, 0.815, width * 0.10, length * 0.96, 0.02, (0.95, 0.95, 0.95))
        spoiler_width, spoiler_height = {
            "coupe": (width * 0.68, 1.17),
            "sports": (width * 0.88, 1.23),
            "supercar": (width * 0.94, 1.18),
            "muscle": (width * 0.82, 1.38),
            "rally": (width * 0.86, 1.52),
            "lightweight": (width * 0.52, 1.10),
            "heavy": (width * 0.74, 1.36),
        }[self.style]
        mb.add_box(0, -length * 0.465, spoiler_height, spoiler_width, 0.30, 0.08, dark)
        for sx in (-spoiler_width * 0.31, spoiler_width * 0.31):
            mb.add_box(sx, -length * 0.445, (spoiler_height + 1.0) * 0.5,
                       0.07, 0.11, abs(spoiler_height - 1.0), dark)
        if self.style in ("muscle", "heavy"):
            mb.add_box(0, length * 0.27, 0.84, width * 0.46, 0.22, 0.10, dark)
            for sx in (-width * 0.18, width * 0.18):
                mb.add_box(sx, length * 0.30, 0.88, width * 0.08, 0.24, 0.025,
                           (0.10, 0.11, 0.13))
        if self.style == "rally":
            for sx in (-0.48, 0.0, 0.48):
                mb.add_cylinder(sx, length * 0.49, 0.82, 0.12, 0.16,
                                (1.0, 0.93, 0.63), axis="y", segments=10)
        if self.style == "supercar":
            for sx in (-0.72, 0.72):
                mb.add_box(sx, -0.15, 0.92, 0.18, 1.25, 0.12, dark)
        paint_np = paint.build()
        paint_np.reparentTo(self.body_np)
        trim_np = mb.build()
        trim_np.reparentTo(self.body_np)
        paint_finish = {
            "coupe": (0.28, 0.27),
            "sports": (0.32, 0.24),
            "supercar": (0.38, 0.21),
            "muscle": (0.24, 0.32),
            "rally": (0.18, 0.36),
            "lightweight": (0.26, 0.25),
            "heavy": (0.30, 0.28),
        }[self.style]
        paint_material = apply_material(
            paint_np, "metallic-racing-paint", color,
            metallic=paint_finish[0], roughness=paint_finish[1])
        paint_material.setAmbient(
            (color[0], color[1], color[2], 1.0))
        paint_material.setEmission(
            (color[0] * 0.25, color[1] * 0.25, color[2] * 0.25, 1.0))

        # Cabin glazing remains a separate material so paint changes never tint it.
        c = []
        for z, hx, y0, y1 in ((0.80, width * 0.43, -length * 0.27, length * 0.13),
                              (roof_z - 0.02, roof_width * 0.48,
                               -length * 0.20, length * 0.02)):
            c += [(-hx, y0, z), (hx, y0, z), (-hx, y1, z), (hx, y1, z)]
        glass = MeshBuilder("car_glass")
        glass.add_hexa(c, (0.12, 0.22, 0.32, 0.78))
        self.glass_np = glass.build()
        self.glass_np.reparentTo(self.body_np)
        self.glass_np.setTransparency(TransparencyAttrib.MAlpha)
        self.glass_np.setDepthWrite(False)
        apply_material(self.glass_np, "blue-tinted-glass", (0.30, 0.52, 0.72, 0.78),
                       metallic=0.08, roughness=0.14)
        self.glass_np.setTwoSided(True)

        lamp_positions = []
        bezels = MeshBuilder("headlight-bezels")
        lamps = MeshBuilder("headlights")
        for sx in (-width * 0.34, width * 0.34):
            lamp_width = 0.48 if self.style in ("sports", "supercar") else 0.62
            lamp_positions.append((sx, length * 0.49 + 0.05, 0.62))
            bezels.add_box(sx, length * 0.49 + 0.015, 0.62, lamp_width + 0.09, 0.09, 0.21, dark)
            lamps.add_box(sx, length * 0.49 + 0.065, 0.62, lamp_width, 0.045, 0.14,
                          (1.0, 0.95, 0.76))
        self.headlight_bezels_np = bezels.build()
        self.headlight_bezels_np.reparentTo(self.body_np)
        apply_material(self.headlight_bezels_np, "headlight-trim", (0.12, 0.13, 0.15),
                       metallic=0.22, roughness=0.44)
        self.headlights_np = lamps.build()
        self.headlights_np.reparentTo(self.body_np)
        apply_material(self.headlights_np, "headlight-lenses", (1.0, 0.9, 0.58),
                       roughness=0.18, emission=(0.8, 0.72, 0.48))
        self.headlight_glow_np = self._build_light_glow(
            lamp_positions, (1.0, 0.82, 0.50), front=True)

        tail = MeshBuilder("car_tail")
        tail_positions = []
        for sx in (-width * 0.34, width * 0.34):
            lamp_width = width * 0.26
            tail_positions.append((sx, -length * 0.49 - 0.05, 0.62))
            tail.add_box(sx, -length * 0.49 - 0.025, 0.62,
                         lamp_width + 0.08, 0.09, 0.18, (0.18, 0.025, 0.02))
            tail.add_box(sx, -length * 0.49 - 0.075, 0.62,
                         lamp_width, 0.04, 0.12, (0.75, 0.025, 0.014))
        self.tail_np = tail.build()
        self.tail_np.reparentTo(self.body_np)
        apply_material(self.tail_np, "rear-light-lenses", (0.7, 0.025, 0.012),
                       roughness=0.22, emission=(0.28, 0.008, 0.003))
        self.brake_glow_np = self._build_light_glow(
            tail_positions, (1.0, 0.04, 0.015), front=False)
        self.brake_glow_np.hide()

    def _add_livery(self, mesh, width, length, roof_width, roof_length, roof_z):
        patterns = {
            "double": ((-0.19, 0.19), 0.075, 0.055, (0.88, 0.08)),
            "single": ((0.0,), 0.24, 0.18, (0.84, 0.13)),
            "offset": ((0.30,), 0.28, 0.16, (0.72, 0.10)),
            "twin": ((-0.20, 0.20), 0.105, 0.09, (0.78, 0.08)),
            "rally": ((0.0,), 0.18, 0.14, (0.92, 0.24)),
            "pinstripe": ((-0.15, 0.15), 0.045, 0.035, (0.64, 0.06)),
            "grand_tourer": ((0.0,), 0.095, 0.075, (0.74, 0.12)),
        }
        offsets, hood_stripe, roof_stripe, side_style = patterns[self.livery]
        for offset in offsets:
            hood_x = offset * width
            mesh.add_box(hood_x, length * 0.36, 0.865, hood_stripe, length * 0.29,
                         0.018, self.accent_color)
            roof_x = offset * roof_width
            mesh.add_box(roof_x, -length * 0.09, roof_z + 0.04, roof_stripe,
                         roof_length * 0.94, 0.018, self.accent_color)

        side_length, side_z = side_style
        side_height = 0.19 if self.livery == "rally" else 0.075
        for side in (-1, 1):
            mesh.add_box(side * (width * 0.5 + 0.012), 0.03, side_z,
                         0.025, length * side_length, side_height, self.accent_color)

    def _build_light_glow(self, positions, color, front):
        glow = MeshBuilder("light-glow")
        side = 1.0 if front else -1.0
        for x, y, z in positions:
            for width, height, alpha in ((0.42, 0.20, 0.07), (0.27, 0.12, 0.12)):
                y += side * 0.012
                glow.add_quad((x - width, y, z - height), (x - width, y, z + height),
                              (x + width, y, z + height), (x + width, y, z - height),
                              (color[0], color[1], color[2], alpha), up=(0, side, 0))
        node = glow.build()
        node.reparentTo(self.body_np)
        node.setTransparency(TransparencyAttrib.MAlpha)
        node.setDepthWrite(False)
        node.setLightOff()
        node.setTwoSided(True)
        node.setBin("transparent", 10)
        return node

    def _build_wheels(self):
        wheel_specs = {
            "coupe": (0.38, 0.30, 0.23, 6),
            "sports": (0.37, 0.32, 0.25, 5),
            "supercar": (0.36, 0.34, 0.26, 7),
            "muscle": (0.40, 0.34, 0.24, 5),
            "rally": (0.40, 0.34, 0.22, 6),
            "lightweight": (0.34, 0.26, 0.21, 4),
            "heavy": (0.42, 0.36, 0.27, 8),
        }
        self.wheel_radius, tire_width, rim_radius, spoke_count = wheel_specs[self.style]
        tire_mesh = MeshBuilder("rubber-tire")
        tire_mesh.add_cylinder(0, 0, 0, self.wheel_radius, tire_width, (0.055, 0.06, 0.07),
                               axis="x", segments=14)
        tire = tire_mesh.build()
        apply_material(tire, "tire-rubber", (0.12, 0.13, 0.14), roughness=0.92)
        rotor_mesh = MeshBuilder("brake-rotor")
        rotor_mesh.add_cylinder(0, 0, 0, rim_radius * 0.72, tire_width * 0.58,
                                (0.30, 0.32, 0.34), axis="x", segments=16)
        rotor = rotor_mesh.build()
        apply_material(rotor, "brushed-brake-rotor", (0.48, 0.50, 0.52),
                       metallic=0.62, roughness=0.48)
        caliper_mesh = MeshBuilder("brake-caliper")
        caliper_mesh.add_box(0, 0, self.wheel_radius * 0.42,
                             0.12, 0.15, self.wheel_radius * 0.54, (0.72, 0.10, 0.055))
        caliper = caliper_mesh.build()
        apply_material(caliper, "painted-brake-caliper", (0.72, 0.10, 0.055),
                       metallic=0.18, roughness=0.38)
        rim_mesh = MeshBuilder("alloy-rim")
        rim_mesh.add_cylinder(0, 0, 0, rim_radius, tire_width + 0.04, (0.56, 0.61, 0.68),
                              axis="x", segments=12)
        spoke_color = (0.48, 0.54, 0.63) if self.style != "rally" else (0.82, 0.84, 0.86)
        half_width = 0.035 if spoke_count < 7 else 0.025
        for index in range(spoke_count):
            angle = math.tau * index / spoke_count
            ca, sa = math.cos(angle), math.sin(angle)
            py, pz = -sa * half_width, ca * half_width
            points = (
                (0.0, 0.055 * ca + py, 0.055 * sa + pz),
                (0.0, 0.055 * ca - py, 0.055 * sa - pz),
                (0.0, (rim_radius - 0.025) * ca - py, (rim_radius - 0.025) * sa - pz),
                (0.0, (rim_radius - 0.025) * ca + py, (rim_radius - 0.025) * sa + pz),
            )
            front = tuple((tire_width * 0.5 + 0.025, point[1], point[2]) for point in points)
            back = tuple((-tire_width * 0.5 - 0.025, point[1], point[2]) for point in reversed(points))
            rim_mesh.add_quad(*front, spoke_color, ref=(0, 0, 0))
            rim_mesh.add_quad(*back, spoke_color, ref=(0, 0, 0))
        wheel = rim_mesh.build()
        apply_material(wheel, "machined-alloy", (0.72, 0.76, 0.82), metallic=0.82, roughness=0.28)
        self.front_pivots = []
        self.spins = []
        wheel_x = {"coupe": 0.98, "sports": 1.04, "supercar": 1.08, "muscle": 1.12,
                   "rally": 1.01, "lightweight": 0.92, "heavy": 1.14}[self.style]
        front_y = {"coupe": FRONT_Y, "sports": 1.42, "supercar": 1.48,
                   "muscle": 1.38, "rally": 1.34, "lightweight": 1.20, "heavy": 1.50}[self.style]
        rear_y = {"coupe": REAR_Y, "sports": -1.38, "supercar": -1.42,
                  "muscle": -1.36, "rally": -1.30, "lightweight": -1.16, "heavy": -1.48}[self.style]
        for sx in (-wheel_x, wheel_x):
            for y, front in ((front_y, True), (rear_y, False)):
                pivot = self.body_np.attachNewNode("pivot")
                pivot.setPos(sx, y, self.wheel_radius)
                spin = pivot.attachNewNode("spin")
                tire.copyTo(spin)
                rotor.copyTo(spin)
                wheel.copyTo(spin)
                caliper_instance = caliper.copyTo(pivot)
                caliper_instance.setX(math.copysign(tire_width * 0.28, sx))
                self.spins.append(spin)
                if front:
                    self.front_pivots.append(pivot)

    def _build_blob(self):
        mb = MeshBuilder("blob")
        mb.add_quad((-1.15, -2.4, 0.012), (1.15, -2.4, 0.012), (1.15, 2.4, 0.012), (-1.15, 2.4, 0.012),
                    (0, 0, 0, 0.35), up=(0, 0, 1))
        self.blob = mb.build()
        self.blob.reparentTo(self.root)
        self.blob.setTransparency(TransparencyAttrib.MAlpha)
        self.blob.setLightOff()
        self.blob.setDepthWrite(False)

    # ----------------------------------------------------------------- state
    def set_blob(self, visible):
        """Fake blob shadow, shown only when real shadows are off."""
        if visible:
            self.blob.show()
        else:
            self.blob.hide()

    def destroy(self):
        self.root.removeNode()

    def update(self, x, y, heading, body, braking, dt, elevation=0.0):
        self.root.setPos(x, y, ROAD_Z + elevation)
        self.root.setH(math.degrees(heading))
        steer_deg = body.steer * MAX_WHEEL_LOCK_DEG
        for pivot in self.front_pivots:
            pivot.setH(steer_deg)
        self.spin_angle = (self.spin_angle + body.vf * dt / self.wheel_radius) % (2.0 * math.pi)
        angle = -math.degrees(self.spin_angle)
        for spin in self.spins:
            spin.setP(angle)
        roll_target = max(-5.0, min(5.0, body.yaw_rate * body.vf * 0.07))
        pitch_target = max(-3.0, min(3.0, body.long_accel * 0.06))
        k = min(1.0, 8.0 * dt)
        self.roll += (roll_target - self.roll) * k
        self.pitch += (pitch_target - self.pitch) * k
        self.body_np.setHpr(0, self.pitch, self.roll)
        if braking:
            self.tail_np.setColorScale(2.8, 0.45, 0.30, 1.0)
            self.brake_glow_np.show()
        else:
            self.tail_np.clearColorScale()
            self.brake_glow_np.hide()
