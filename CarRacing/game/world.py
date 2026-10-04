"""Builds the 3D environment: lighting, sky, terrain, road, barriers and scenery.

Everything is generated procedurally.  Optional replacement textures can be
dropped into assets/textures/ (road.png, grass.png).
"""
import math
import random

from panda3d.core import (AmbientLight, AntialiasAttrib, DirectionalLight, Filename, Fog,
                          LineSegs, PNMImage, Texture, TextNode, TransparencyAttrib, Vec4)

from .config import TEXTURES_DIR
from .graphics import GRAPHICS_PROFILES, WEATHER_PRESETS
from .meshes import MeshBuilder
from .visuals import apply_material

ROAD_Z = 0.04
MARK_Z = 0.07
HORIZON = (0.74, 0.86, 0.97)
ZENITH = (0.20, 0.45, 0.85)
SUN_OFFSET = (90.0, -120.0, 170.0)
SIGN_TEXTS = ("TURBO", "APEX", "NITRO", "VELOCITY", "SPEEDLINE", "RACE-X", "DRIFT", "OCTANE", "TORQUE", "GT PRO")
SIGN_COLORS = ((0.80, 0.10, 0.10), (0.10, 0.30, 0.75), (0.90, 0.55, 0.05), (0.10, 0.55, 0.30),
               (0.45, 0.15, 0.60))
BUILDING_COLORS = ((0.75, 0.72, 0.66), (0.55, 0.60, 0.70), (0.80, 0.55, 0.40), (0.65, 0.65, 0.70),
                   (0.45, 0.50, 0.55))
ENVIRONMENTS = {
    "city": {
        "grass": (0.26, 0.52, 0.18), "road": (0.24, 0.24, 0.26),
        "dirt": (0.42, 0.32, 0.20), "hill": (0.55, 0.68, 0.78),
        "sky_tint": (1.0, 1.0, 1.0), "light_tint": (1.0, 0.98, 0.94),
        "trees": 110, "buildings": 16,
    },
    "mountain": {
        "grass": (0.22, 0.37, 0.22), "road": (0.22, 0.23, 0.24),
        "dirt": (0.37, 0.32, 0.26), "hill": (0.34, 0.43, 0.47),
        "sky_tint": (0.86, 0.94, 1.0), "light_tint": (0.91, 0.96, 1.0),
        "trees": 95, "buildings": 2,
    },
    "desert": {
        "grass": (0.69, 0.50, 0.25), "road": (0.33, 0.30, 0.27),
        "dirt": (0.74, 0.55, 0.29), "hill": (0.69, 0.43, 0.27),
        "sky_tint": (1.0, 0.91, 0.75), "light_tint": (1.0, 0.91, 0.76),
        "trees": 0, "buildings": 0,
    },
    "forest": {
        "grass": (0.20, 0.43, 0.20), "road": (0.26, 0.25, 0.22),
        "dirt": (0.34, 0.27, 0.17), "hill": (0.27, 0.43, 0.34),
        "sky_tint": (0.91, 1.0, 0.95), "light_tint": (0.91, 1.0, 0.88),
        "trees": 280, "buildings": 5,
    },
    "coastal": {
        "grass": (0.31, 0.52, 0.35), "road": (0.26, 0.27, 0.28),
        "dirt": (0.49, 0.43, 0.34), "hill": (0.43, 0.56, 0.66),
        "sky_tint": (0.84, 0.96, 1.0), "light_tint": (0.91, 0.97, 1.0),
        "trees": 48, "buildings": 2,
    },
    "industrial": {
        "grass": (0.28, 0.32, 0.27), "road": (0.29, 0.30, 0.31),
        "dirt": (0.34, 0.32, 0.28), "hill": (0.40, 0.44, 0.48),
        "sky_tint": (0.85, 0.88, 0.92), "light_tint": (0.91, 0.92, 0.92),
        "trees": 8, "buildings": 24,
    },
    "neon_city": {
        "grass": (0.045, 0.055, 0.10), "road": (0.10, 0.085, 0.16),
        "dirt": (0.12, 0.10, 0.17), "hill": (0.10, 0.12, 0.22),
        "sky_tint": (0.68, 0.57, 1.0), "light_tint": (0.70, 0.75, 1.0),
        "trees": 0, "buildings": 26,
    },
    "extreme_mountain": {
        "grass": (0.25, 0.31, 0.30), "road": (0.19, 0.20, 0.22),
        "dirt": (0.33, 0.30, 0.28), "hill": (0.37, 0.38, 0.48),
        "sky_tint": (0.94, 0.78, 0.72), "light_tint": (1.0, 0.75, 0.58),
        "trees": 32, "buildings": 0,
    },
}


def _lerp3(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


class World:
    def __init__(self, render, loader, track, quality="medium", weather="day", grid_size=4):
        self.render = render
        self.loader = loader
        self.track = track
        self.grid_size = max(2, grid_size)
        self.environment = ENVIRONMENTS[track.environment]
        self.quality = quality if quality in GRAPHICS_PROFILES else "medium"
        self.requested_weather = weather if weather in WEATHER_PRESETS else "day"
        self.weather = self.requested_weather
        if self.track.environment == "neon_city" and self.weather == "day":
            self.weather = "night"
        self.quality_profile = GRAPHICS_PROFILES[self.quality]
        self._tree_target = int(self.environment["trees"] * self.quality_profile["tree_scale"])
        self.weather_profile = WEATHER_PRESETS[self.weather]
        self.horizon = self._weather_color("horizon")
        self.zenith = self._weather_color("zenith")
        self.rng = random.Random(11)
        self._track_cell_size = 32.0
        self._track_buckets = self._index_track()
        self.root = render.attachNewNode("world")
        self.shadows_enabled = False
        self._buildings = []
        self._make_textures()
        self._make_lights()
        self._make_sky()
        self._make_ground()
        self._make_road()
        self._make_edges()
        self._make_start_area()
        self._make_scenery()
        self._make_clouds()
        self._make_rain()
        self.apply_quality(self.quality, self.weather)

    def _weather_color(self, key):
        color = self.weather_profile[key]
        tint = self.environment["sky_tint"] if key in ("horizon", "zenith") else self.environment["light_tint"]
        if len(color) == 4:
            return (color[0] * tint[0], color[1] * tint[1], color[2] * tint[2], color[3])
        return tuple(color[index] * tint[index] for index in range(3))

    def _fog_density(self):
        factor = {"forest": 1.45, "mountain": 1.2, "extreme_mountain": 1.25,
                  "coastal": 0.8, "desert": 0.65}.get(self.track.environment, 1.0)
        return self.weather_profile["fog"] * factor

    # -------------------------------------------------------------- textures
    def _noise_texture(self, name, base, variation, patch, seed):
        size = self.quality_profile["texture_size"]
        rng = random.Random(seed)
        cells = max(2, size // 16)
        patches = [[rng.uniform(-patch, patch) for _ in range(cells)] for _ in range(cells)]
        img = PNMImage(size, size, 3)
        for y in range(size):
            for x in range(size):
                coarse = patches[y * cells // size][x * cells // size]
                fine = rng.uniform(-variation, variation)
                wear = 0.0
                if name.startswith("asphalt"):
                    wear = 0.035 * math.sin(x * 0.37 + y * 0.14) + rng.uniform(-0.035, 0.035)
                elif name == "water":
                    wear = 0.055 * math.sin(x * 0.22 + math.sin(y * 0.09) * 2.0)
                v = 1.0 + coarse + fine + wear
                img.setXel(x, y, min(1.0, base[0] * v), min(1.0, base[1] * v), min(1.0, base[2] * v))
        tex = Texture(name)
        tex.load(img)
        return tex

    def _load_texture(self, filename, fallback):
        tex = None
        stem, suffix = filename.rsplit(".", 1)
        paths = (TEXTURES_DIR / (stem + "_" + self.quality + "." + suffix),
                 TEXTURES_DIR / filename)
        for path in paths:
            if not path.is_file():
                continue
            try:
                tex = self.loader.loadTexture(Filename.fromOsSpecific(str(path)))
            except Exception as exc:
                print("Could not load texture %s: %s" % (filename, exc))
            if tex is not None:
                break
        tex = tex or fallback()
        tex.setWrapU(Texture.WMRepeat)
        tex.setWrapV(Texture.WMRepeat)
        tex.setMinfilter(Texture.FTLinearMipmapLinear)
        tex.setMagfilter(Texture.FTLinear)
        tex.setAnisotropicDegree(self.quality_profile["anisotropic_degree"])
        tex.generateRamMipmapImages()
        return tex

    def _make_textures(self):
        self.road_tex = self._load_texture(
            "road.png", lambda: self._noise_texture(
                "asphalt", self.environment["road"], 0.14, 0.05,
                1 if self.track.environment == "city" else 3))
        self.grass_tex = self._load_texture(
            "grass.png", lambda: self._noise_texture(
                "grass", self.environment["grass"], 0.12, 0.10,
                2 if self.track.environment == "city" else 4))
        self.dirt_tex = self._load_texture(
            "dirt.png", lambda: self._noise_texture("dirt", self.environment["dirt"], 0.20, 0.16, 5))

    # ---------------------------------------------------------------- lights
    def _make_lights(self):
        ambient = AmbientLight("ambient")
        self.ambient = ambient
        ambient.setColor(Vec4(*self._weather_color("ambient")))
        self.ambient_np = self.root.attachNewNode(ambient)
        self.render.setLight(self.ambient_np)
        self.sun = DirectionalLight("sun")
        self.sun.setColor(Vec4(*self._weather_color("sun")))
        self.sun_np = self.root.attachNewNode(self.sun)
        self.sun_np.setPos(*SUN_OFFSET)
        self.sun_np.lookAt(0, 0, 0)
        lens = self.sun.getLens()
        lens.setFilmSize(150, 150)
        lens.setNearFar(20, 520)
        self.render.setLight(self.sun_np)
        fill = DirectionalLight("fill")
        self.fill = fill
        fill.setColor(Vec4(*self._weather_color("fill")))
        self.fill_np = self.root.attachNewNode(fill)
        self.fill_np.setPos(-60, 80, 40)
        self.fill_np.lookAt(0, 0, 0)
        self.render.setLight(self.fill_np)
        fog = Fog("fog")
        fog.setColor(*self.horizon)
        fog.setExpDensity(self._fog_density())
        self.render.setFog(fog)
        self.fog = fog

    def apply_quality(self, level, weather=None):
        """Apply one centralized graphics profile and a visual-only weather preset."""
        if level not in GRAPHICS_PROFILES:
            raise ValueError("Unknown graphics quality: %s" % level)
        if weather is not None and weather not in WEATHER_PRESETS:
            raise ValueError("Unknown visual weather: %s" % weather)
        requested_weather = weather
        if weather == "day" and self.track.environment == "neon_city":
            weather = "night"
        weather_changed = weather is not None and weather != self.weather
        self.quality = level
        self.quality_profile = GRAPHICS_PROFILES[level]
        if weather is not None:
            self.requested_weather = requested_weather
            self.weather = weather
            self.weather_profile = WEATHER_PRESETS[weather]
        self.horizon = self._weather_color("horizon")
        self.zenith = self._weather_color("zenith")

        if weather_changed:
            self.ambient.setColor(Vec4(*self._weather_color("ambient")))
            self.sun.setColor(Vec4(*self._weather_color("sun")))
            self.fill.setColor(Vec4(*self._weather_color("fill")))
            self.fog.setColor(*self.horizon)
            self.fog.setExpDensity(self._fog_density())
            self.sky_np.removeNode()
            self._make_sky()
            if self.rain_np is not None:
                self.rain_np.removeNode()
            self._make_rain()
        shadows = self.quality_profile["shadow_size"] > 0
        try:
            if shadows:
                size = self.quality_profile["shadow_size"]
                film_size = self.quality_profile["shadow_film_size"]
                self.sun.getLens().setFilmSize(film_size, film_size)
                self.sun.setShadowCaster(False)
                self.render.setShaderAuto()
                self.sun.setShadowCaster(True, size, size)
            else:
                self.sun.setShadowCaster(False)
                self.render.clearShader()
        except Exception as exc:                       # very old GPUs / drivers
            print("Shadows unavailable:", exc)
            self.sun.setShadowCaster(False)
            self.render.clearShader()
            shadows = False
        self.shadows_enabled = shadows
        self.render.setAntialias(
            AntialiasAttrib.MAuto if self.quality_profile["antialias"] else AntialiasAttrib.MNone)
        if self.weather_profile["wet"]:
            self.road_np.setColorScale(0.70, 0.74, 0.80, 1.0)
        else:
            self.road_np.clearColorScale()
        self.road_material.setRoughness(0.16 if self.weather_profile["wet"] else 0.78)
        self.road_material.setShininess(80 if self.weather_profile["wet"] else 18)
        self._update_rain_visibility()

    def destroy(self):
        for light_np in (self.ambient_np, self.sun_np, self.fill_np):
            self.render.clearLight(light_np)
        self.render.clearFog()
        self.root.removeNode()
        if self.rain_np is not None:
            self.rain_np.removeNode()

    # ------------------------------------------------------------------- sky
    def _make_sky(self):
        radius = 1100.0
        rings = [-8, 0, 10, 25, 45, 70, 90]
        mb = MeshBuilder("sky")
        segs = 24

        def pt(elev, k):
            e = math.radians(elev)
            a = 2 * math.pi * k / segs
            return (radius * math.cos(e) * math.cos(a), radius * math.cos(e) * math.sin(a),
                    radius * math.sin(e))

        def col(elev):
            t = max(0.0, math.sin(math.radians(elev))) ** 0.6
            return _lerp3(self.horizon, self.zenith, t)

        for r in range(len(rings) - 1):
            for k in range(segs):
                k2 = (k + 1) % segs
                if rings[r + 1] >= 90:
                    mb.add_tri(pt(rings[r], k), pt(rings[r], k2), (0, 0, radius), col(rings[r]))
                else:
                    mb.add_quad(pt(rings[r], k), pt(rings[r], k2), pt(rings[r + 1], k2),
                                pt(rings[r + 1], k), col(rings[r]))
        hills = MeshBuilder("hills")
        n = 72
        for k in range(n):
            k2 = (k + 1) % n
            pts = []
            for kk in (k, k2):
                a = 2 * math.pi * kk / n
                h = 45 + 35 * math.sin(3 * a + 1) + 25 * math.sin(7 * a + 2) + 15 * math.sin(13 * a)
                pts.append((900 * math.cos(a), 900 * math.sin(a), max(15.0, h)))
            (tx0, ty0, tz0), (tx1, ty1, tz1) = pts
            hills.add_quad((tx0, ty0, -5), (tx1, ty1, -5), (tx1, ty1, tz1), (tx0, ty0, tz0),
                           self.environment["hill"])
        self.sky_np = self.root.attachNewNode("sky")
        for builder in (mb, hills):
            builder.build().reparentTo(self.sky_np)
        self.sky_np.setTwoSided(True)
        self.sky_np.setLightOff()
        self.sky_np.setFogOff()
        self.sky_np.setBin("background", 0)
        self.sky_np.setDepthWrite(False)

    def _make_clouds(self):
        count = self.quality_profile["cloud_count"]
        rng = random.Random(902)
        color = (0.72, 0.76, 0.82, 0.13) if self.weather == "rain" else (
            (0.20, 0.18, 0.30, 0.24) if self.weather == "night" else (1.0, 0.79, 0.70, 0.22)
            if self.weather == "sunset" else (0.94, 0.97, 1.0, 0.25))
        clouds = MeshBuilder("procedural-clouds")
        for _ in range(count):
            angle = rng.uniform(0, math.tau)
            elevation = math.radians(rng.uniform(4, 18))
            radius = rng.uniform(620, 900)
            center = (radius * math.cos(elevation) * math.cos(angle),
                      radius * math.cos(elevation) * math.sin(angle),
                      radius * math.sin(elevation))
            east = (-math.sin(angle), math.cos(angle), 0.0)
            up = (-math.sin(elevation) * math.cos(angle),
                  -math.sin(elevation) * math.sin(angle), math.cos(elevation))
            for _ in range(rng.randint(3, 6)):
                ox, oy = rng.uniform(-30, 30), rng.uniform(-12, 12)
                cx = center[0] + east[0] * ox + up[0] * oy
                cy = center[1] + east[1] * ox + up[1] * oy
                cz = center[2] + east[2] * ox + up[2] * oy
                cloud_radius = rng.uniform(10, 24)
                points = []
                for k in range(10):
                    a = 2 * math.pi * k / 10
                    points.append((cx + east[0] * math.cos(a) * cloud_radius
                                   + up[0] * math.sin(a) * cloud_radius * 0.48,
                                   cy + east[1] * math.cos(a) * cloud_radius
                                   + up[1] * math.sin(a) * cloud_radius * 0.48,
                                   cz + east[2] * math.cos(a) * cloud_radius
                                   + up[2] * math.sin(a) * cloud_radius * 0.48))
                middle = (cx, cy, cz)
                for k in range(10):
                    clouds.add_tri(middle, points[k], points[(k + 1) % 10], color)
        self.cloud_np = clouds.build()
        self.cloud_np.reparentTo(self.sky_np)
        self.cloud_np.setTransparency(TransparencyAttrib.MAlpha)
        self.cloud_np.setLightOff()
        self.cloud_np.setDepthWrite(False)
        self.cloud_np.setTwoSided(True)

    def _make_rain(self):
        self.rain_np = None
        if not self.weather_profile["rain"]:
            return
        lines = LineSegs("rain-streaks")
        lines.setThickness(1.1 if self.quality == "low" else 1.6)
        lines.setColor(0.72, 0.82, 0.95, 0.42)
        rng = random.Random(437)
        for _ in range(self.quality_profile["rain_streaks"]):
            x, y, z = rng.uniform(-22, 22), rng.uniform(-22, 22), rng.uniform(0, 22)
            lines.moveTo(x, y, z)
            lines.drawTo(x - 0.22, y - 0.08, z - 1.5)
        self.rain_np = self.render.attachNewNode(lines.create())
        self.rain_np.setTransparency(TransparencyAttrib.MAlpha)
        self.rain_np.setDepthWrite(False)
        self.rain_phase = 0.0
        self._update_rain_visibility()

    def _update_rain_visibility(self):
        if self.rain_np is None:
            return
        self.rain_np.show() if self.weather_profile["rain"] else self.rain_np.hide()

    # ---------------------------------------------------------------- ground
    def _make_ground(self):
        r = 1400.0
        mb = MeshBuilder("grass")
        u = r / 6.0
        ground_z = min(-2.0, self.track.min_elevation - 1.0)
        mb.add_quad((-r, -r, ground_z), (r, -r, ground_z), (r, r, ground_z), (-r, r, ground_z), (1, 1, 1),
                    up=(0, 0, 1), uvs=[(-u, -u), (u, -u), (u, u), (-u, u)])
        np_ = mb.build()
        np_.reparentTo(self.root)
        np_.setTexture(self.grass_tex)
        apply_material(np_, "terrain", (0.80, 0.84, 0.80), roughness=0.95)
        if self.track.environment == "coastal":
            water = MeshBuilder("coastal-water")
            water.add_quad((300, -r, ground_z + 0.5), (r, -r, ground_z + 0.5),
                           (r, r, ground_z + 0.5), (300, r, ground_z + 0.5),
                           (1, 1, 1), up=(0, 0, 1),
                           uvs=[(0, 0), (r / 30, 0), (r / 30, r / 30), (0, r / 30)])
            water_np = water.build()
            water_np.reparentTo(self.root)
            water_np.setTexture(self._load_texture(
                "water.png", lambda: self._noise_texture(
                    "water", (0.08, 0.28, 0.40), 0.07, 0.10, 17)))
            apply_material(water_np, "coastal-water", (0.16, 0.42, 0.58),
                           metallic=0.32, roughness=0.30)
        if self.track.environment in ("mountain", "extreme_mountain"):
            cliffs = MeshBuilder("mountain-slope")
            for i in range(self.track.n):
                nxt = (i + 1) % self.track.n
                center_z = self.track.pz[i]
                next_z = self.track.pz[nxt]
                for side in (-1, 1):
                    inner0 = self.track.offset_point(i, side * (self.track.half_width + 5))
                    inner1 = self.track.offset_point(nxt, side * (self.track.half_width + 5))
                    outer0 = self.track.offset_point(i, side * 58)
                    outer1 = self.track.offset_point(nxt, side * 58)
                    low0, low1 = min(ground_z, center_z - 34), min(ground_z, next_z - 34)
                    cliffs.add_quad(
                        (inner0[0], inner0[1], center_z - 2),
                        (outer0[0], outer0[1], low0),
                        (outer1[0], outer1[1], low1),
                        (inner1[0], inner1[1], next_z - 2),
                        self.environment["hill"], up=(0, 0, 1))
            cliff_np = cliffs.build()
            cliff_np.reparentTo(self.root)
            cliff_np.setTwoSided(True)

    # ------------------------------------------------------------------ road
    def _make_road(self):
        t = self.track
        mb = MeshBuilder("road")
        wear = MeshBuilder("tire-wear")
        hw = t.half_width
        for i in range(t.n):
            l0 = t.offset_point(i, hw)
            r0 = t.offset_point(i, -hw)
            l1 = t.offset_point(i + 1, hw)
            r1 = t.offset_point(i + 1, -hw)
            v0, v1 = i * t.ds / 5.0, (i + 1) * t.ds / 5.0
            z0, z1 = t.pz[i] + ROAD_Z, t.pz[(i + 1) % t.n] + ROAD_Z
            mb.add_quad((l0[0], l0[1], z0), (r0[0], r0[1], z0),
                        (r1[0], r1[1], z1), (l1[0], l1[1], z1), (1, 1, 1),
                        up=(0, 0, 1), uvs=[(0, v0), (4, v0), (4, v1), (0, v1)])
            for lateral in (-0.92, 0.92):
                a0 = t.offset_point(i, lateral - 0.16)
                a1 = t.offset_point(i, lateral + 0.16)
                b0 = t.offset_point(i + 1, lateral - 0.16)
                b1 = t.offset_point(i + 1, lateral + 0.16)
                wear.add_quad((a0[0], a0[1], z0 + 0.006), (a1[0], a1[1], z0 + 0.006),
                              (b1[0], b1[1], z1 + 0.006), (b0[0], b0[1], z1 + 0.006),
                              (0.20, 0.21, 0.22, 0.20), up=(0, 0, 1))
        np_ = mb.build()
        np_.reparentTo(self.root)
        np_.setTexture(self.road_tex)
        self.road_np = np_
        self.road_material = apply_material(
            np_, "wet-asphalt", (0.72, 0.74, 0.78), roughness=0.78)
        self.tire_wear_np = wear.build()
        self.tire_wear_np.reparentTo(self.root)
        self.tire_wear_np.setTransparency(TransparencyAttrib.MAlpha)
        self.tire_wear_np.setDepthWrite(False)
        apply_material(self.tire_wear_np, "rubber-road-wear", (0.52, 0.53, 0.54),
                       roughness=0.94)

    def _strip(self, mb, i, lat0, lat1, z, color):
        t = self.track
        a0, a1 = t.offset_point(i, lat0), t.offset_point(i, lat1)
        b0, b1 = t.offset_point(i + 1, lat0), t.offset_point(i + 1, lat1)
        z0, z1 = t.pz[i] + z, t.pz[(i + 1) % t.n] + z
        mb.add_quad((a0[0], a0[1], z0), (a1[0], a1[1], z0),
                    (b1[0], b1[1], z1), (b0[0], b0[1], z1),
                    color, up=(0, 0, 1))

    def _make_edges(self):
        t = self.track
        hw, cw, wd = t.half_width, t.curb_width, t.wall_dist
        flat = MeshBuilder("markings")
        gravel = MeshBuilder("roadside-dirt")
        walls = MeshBuilder("barriers")
        caps = MeshBuilder("barrier-caps")
        supports = MeshBuilder("barrier-supports")
        white, red = (0.93, 0.93, 0.93), (0.82, 0.10, 0.10)
        for i in range(t.n):
            for side in (1, -1):
                self._strip(flat, i, side * hw, side * (hw + cw), MARK_Z, red if (i // 2) % 2 else white)
                self._strip(gravel, i, side * (hw + cw), side * wd, ROAD_Z - 0.005, (1, 1, 1))
                self._strip(flat, i, side * (hw - 0.9), side * (hw - 0.5), MARK_Z, white)
            if i % 2 == 0:                                   # dashed centre line
                mid_x = t.px[i] + t.sdx[i] * 0.5
                mid_y = t.py[i] + t.sdy[i] * 0.5
                nx, ny = t.snx[i] * 0.15, t.sny[i] * 0.15
                z0, z1 = t.pz[i] + MARK_Z, t.pz[(i + 1) % t.n] + MARK_Z
                flat.add_quad((t.px[i] - nx, t.py[i] - ny, z0), (t.px[i] + nx, t.py[i] + ny, z0),
                              (mid_x + nx, mid_y + ny, z1), (mid_x - nx, mid_y - ny, z1),
                              white, up=(0, 0, 1))
            # barriers (inner face exactly at wall_dist)
            for side in (1, -1):
                a = t.offset_point(i, side * (wd + 0.4))
                b = t.offset_point(i + 1, side * (wd + 0.4))
                dx, dy = b[0] - a[0], b[1] - a[1]
                ln = math.hypot(dx, dy) or 1.0
                ux, uy = dx / ln, dy / ln
                tvx, tvy = -uy * 0.4, ux * 0.4
                a = (a[0] - ux * 0.2, a[1] - uy * 0.2)
                b = (b[0] + ux * 0.2, b[1] + uy * 0.2)
                corners = []
                for z in (0.0, 1.2):
                    for p, base_z in ((a, t.pz[i]), (b, t.pz[(i + 1) % t.n])):
                        for s in (-1, 1):
                            corners.append((p[0] + tvx * s, p[1] + tvy * s, base_z + z))
                walls.add_hexa(corners, red if (i // 2) % 2 else (0.9, 0.9, 0.9), top_color=(0.75, 0.75, 0.75))
                self._strip(caps, i, side * (wd + 0.06), side * (wd + 0.74),
                            1.205, (0.47, 0.49, 0.52))
            support_step = max(1, int(round(14.0 / t.ds)))
            if i % support_step == 0:
                for side in (1, -1):
                    px, py = t.offset_point(i, side * (wd + 0.4))
                    supports.add_box(px, py, t.pz[i] + 0.60, 0.46, 0.46, 1.18,
                                     (0.32, 0.34, 0.37))
        flat_np = flat.build()
        flat_np.reparentTo(self.root)
        apply_material(flat_np, "road-markings", (0.92, 0.92, 0.90), roughness=0.65)
        gravel_np = gravel.build()
        gravel_np.reparentTo(self.root)
        gravel_np.setTexture(self.dirt_tex)
        apply_material(gravel_np, "roadside-dirt", (0.82, 0.78, 0.69), roughness=0.98)
        walls_np = walls.build()
        walls_np.reparentTo(self.root)
        apply_material(walls_np, "painted-barriers", (0.86, 0.86, 0.86), roughness=0.62)
        caps_np = caps.build()
        caps_np.reparentTo(self.root)
        apply_material(caps_np, "barrier-metal-caps", (0.72, 0.74, 0.77),
                       metallic=0.52, roughness=0.38)
        supports_np = supports.build()
        supports_np.reparentTo(self.root)
        apply_material(supports_np, "barrier-supports", (0.62, 0.64, 0.67),
                       metallic=0.48, roughness=0.50)

    # ------------------------------------------------------------ start area
    def _make_start_area(self):
        t = self.track
        x, y, h = t.point_at(0.0, 0.0)
        node = self.root.attachNewNode("start")
        node.setPos(x, y, t.height_at(0.0))
        node.setH(math.degrees(h))
        mb = MeshBuilder("start")
        up = (0, 0, 1)
        # chequered finish line
        for row in range(2):
            for col in range(int(t.width)):
                x0, y0 = -t.half_width + col, -1.0 + row
                c = (0.95, 0.95, 0.95) if (row + col) % 2 == 0 else (0.05, 0.05, 0.05)
                mb.add_quad((x0, y0, MARK_Z + 0.01), (x0 + 1, y0, MARK_Z + 0.01),
                            (x0 + 1, y0 + 1, MARK_Z + 0.01), (x0, y0 + 1, MARK_Z + 0.01), c, up=up)
        # grid slot rectangles
        for k in range(self.grid_size):
            s, lat = t.grid_slot(k)
            gx, gy = -lat, s - t.length
            for (bx, by, sx, sy) in ((-1.4, 0.0, 0.14, 5.0), (1.4, 0.0, 0.14, 5.0), (0.0, -2.5, 2.9, 0.14)):
                mb.add_box(gx + bx, gy + by, MARK_Z + 0.01, sx, sy, 0.02, (0.95, 0.95, 0.95))
        # finish gantry
        post_x = t.wall_dist + 2.5
        for sx in (-post_x, post_x):
            mb.add_box(sx, 0, 4.2, 1.2, 1.2, 8.4, (0.35, 0.36, 0.40))
        mb.add_box(0, 0, 8.4, post_x * 2 + 1.2, 1.4, 1.8, (0.12, 0.12, 0.14))
        cols = int(post_x * 2)
        for face in (-0.71, 0.71):
            for row in range(2):
                for col in range(cols):
                    x0 = -post_x + col
                    z0 = 7.6 + row * 0.9
                    c = (0.95, 0.95, 0.95) if (row + col) % 2 == 0 else (0.05, 0.05, 0.05)
                    mb.add_quad((x0, face, z0), (x0 + 1, face, z0), (x0 + 1, face, z0 + 0.9),
                                (x0, face, z0 + 0.9), c, ref=(0, 0, 8.4))
        mb.build().reparentTo(node)

    # --------------------------------------------------------------- scenery
    def _dist_to_track(self, x, y):
        size = self._track_cell_size
        cx, cy = math.floor(x / size), math.floor(y / size)
        best_squared = math.inf
        radius = 0
        while True:
            for gx in range(cx - radius, cx + radius + 1):
                for gy in range(cy - radius, cy + radius + 1):
                    if radius and abs(gx - cx) != radius and abs(gy - cy) != radius:
                        continue
                    for px, py in self._track_buckets.get((gx, gy), ()):
                        distance_squared = (px - x) ** 2 + (py - y) ** 2
                        best_squared = min(best_squared, distance_squared)
            left = x - (cx - radius) * size
            right = (cx + radius + 1) * size - x
            bottom = y - (cy - radius) * size
            top = (cy + radius + 1) * size - y
            nearest_unsearched = min(left, right, bottom, top)
            if best_squared <= nearest_unsearched ** 2:
                return math.sqrt(best_squared)
            radius += 1

    def _index_track(self):
        buckets = {}
        size = self._track_cell_size
        for x, y in zip(self.track.px, self.track.py):
            cell = math.floor(x / size), math.floor(y / size)
            buckets.setdefault(cell, []).append((x, y))
        return buckets

    def _side_pos(self, s, lateral):
        x, y, h = self.track.point_at(s, lateral)
        return x, y, math.degrees(h)

    def _make_scenery(self):
        sc = MeshBuilder("scenery")
        urban = self.track.environment in ("city", "industrial", "neon_city")
        if urban:
            self._grandstand(sc)
            self._pit_building(sc)
        self._buildings_group(sc)
        if self.track.environment not in ("forest", "desert", "mountain", "extreme_mountain"):
            self._street_lights(sc)
        self._trees(sc)
        self._rocks(sc)
        self._environment_props(sc)
        self.scenery_np = sc.build()
        self.scenery_np.reparentTo(self.root)
        apply_material(self.scenery_np, "scenery-finish", (0.82, 0.84, 0.86), roughness=0.82)
        self._signs()

    def _grandstand(self, sc):
        t, rng = self.track, self.rng
        s_mid, length = 75.0, 85.0
        palette = ((0.9, 0.2, 0.2), (0.2, 0.4, 0.9), (0.95, 0.95, 0.95), (0.95, 0.8, 0.2), (0.3, 0.75, 0.4))
        for k in range(3):
            lat = -(t.wall_dist + 5.0 + 3.5 * k)
            height = 2.5 + 2.0 * k
            x, y, hd = self._side_pos(s_mid, lat)
            sc.add_box(x, y, height / 2, 6.0, length, height, (0.60, 0.60, 0.63), heading=hd)
            for m in range(int(length / 2.1)):
                sx, sy, _ = self._side_pos(s_mid - length / 2 + 1.0 + m * 2.1, lat)
                sc.add_box(sx, sy, height + 0.5, 0.8, 0.8, 1.0, rng.choice(palette), heading=hd)
        x, y, hd = self._side_pos(s_mid, -(t.wall_dist + 8.5))
        sc.add_box(x, y, 10.0, 15.0, length, 0.35, (0.85, 0.15, 0.15), heading=hd)
        for end in (-length / 2 + 1.0, length / 2 - 1.0):
            for lat in (-(t.wall_dist + 5.0), -(t.wall_dist + 12.0)):
                px, py, _ = self._side_pos(s_mid + end, lat)
                sc.add_cylinder(px, py, 5.0, 0.2, 10.0, (0.4, 0.4, 0.45), "z", 6)

    def _pit_building(self, sc):
        t = self.track
        s_mid, length = t.length - 75.0, 110.0
        lat = t.wall_dist + 9.0
        x, y, hd = self._side_pos(s_mid, lat)
        sc.add_box(x, y, 2.5, 9.0, length, 5.0,
                   (0.44, 0.48, 0.53) if self.track.environment == "neon_city"
                   else (0.82, 0.82, 0.85), heading=hd)
        sc.add_box(x, y, 5.2, 9.6, length + 0.6, 0.5, (0.85, 0.15, 0.15), heading=hd)
        for m in range(9):
            dx, dy, _ = self._side_pos(s_mid - length / 2 + 8 + m * 11.5, lat - 4.55)
            sc.add_box(dx, dy, 1.6, 0.2, 7.0, 3.2, (0.15, 0.17, 0.22), heading=hd)

    def _buildings_group(self, sc):
        rng = self.rng
        tries = 0
        while len(self._buildings) < int(self.environment["buildings"] * self.quality_profile["building_scale"]) and tries < 600:
            tries += 1
            x, y = rng.uniform(-430, 430), rng.uniform(-300, 430)
            w, d, h = rng.uniform(14, 30), rng.uniform(14, 30), rng.uniform(10, 45)
            if self._dist_to_track(x, y) < 55 or any((x - b[0]) ** 2 + (y - b[1]) ** 2 < 55 ** 2
                                                      for b in self._buildings):
                continue
            hd = rng.uniform(0, 180)
            col = rng.choice(BUILDING_COLORS)
            sc.add_box(x, y, h / 2, w, d, h, col, heading=hd)
            sc.add_box(x, y, h + 0.4, w + 0.6, d + 0.6, 0.8, (0.30, 0.30, 0.33), heading=hd)
            heading = math.radians(hd)
            columns = max(2, min(6, int(w // 4)))
            rows = max(1, min(7, int((h - 3) // 5)))
            for row in range(rows):
                z = 3.0 + row * 5.0
                for side in (-1, 1):
                    for column in range(columns):
                        local_x = (column + 0.5) * w / columns - w / 2
                        local_y = side * (d / 2 + 0.07)
                        wx = x + local_x * math.cos(heading) - local_y * math.sin(heading)
                        wy = y + local_x * math.sin(heading) + local_y * math.cos(heading)
                        lit = rng.random() < (0.36 if self.track.environment == "neon_city" else 0.12)
                        pane = ((0.68, 0.42, 0.19) if lit else (0.10, 0.16, 0.23))
                        sc.add_box(wx, wy, z, max(1.1, w / columns * 0.66),
                                   0.08, 1.65, pane, heading=hd)
            sc.add_box(x, y, h + 1.1, w * 0.22, d * 0.18, 0.7,
                       (0.34, 0.36, 0.39), heading=hd)
            self._buildings.append((x, y, max(w, d)))

    def _street_lights(self, sc):
        t = self.track
        side = 1
        for i in range(5, t.n, 18):
            lat = side * (t.wall_dist + 3.0)
            x, y = t.offset_point(i, lat)
            sc.add_cylinder(x, y, 4.5, 0.13, 9.0, (0.35, 0.36, 0.40), "z", 6)
            tx, ty = -t.nx[i] * side, -t.ny[i] * side            # direction towards the track
            ang = math.degrees(math.atan2(ty, tx))
            sc.add_box(x + tx * 1.1, y + ty * 1.1, 9.0, 2.4, 0.22, 0.2, (0.35, 0.36, 0.40), heading=ang)
            sc.add_box(x + tx * 2.0, y + ty * 2.0, 8.85, 1.0, 0.5, 0.18, (1.0, 0.95, 0.70), heading=ang)
            side = -side

    def _trees(self, sc):
        rng = self.rng
        count = 0
        for _ in range(900):
            if count >= self._tree_target:
                break
            x, y = rng.uniform(-440, 440), rng.uniform(-310, 440)
            min_clearance = self.track.wall_dist + (5.5 if self.track.environment == "forest" else 22.0)
            if self._dist_to_track(x, y) < min_clearance:
                continue
            if any((x - b[0]) ** 2 + (y - b[1]) ** 2 < (b[2] * 0.8 + 5) ** 2 for b in self._buildings):
                continue
            k = rng.uniform(0.7, 1.6)
            g = rng.random()
            trunk = 2.2 * k
            sc.add_cylinder(x, y, trunk / 2, 0.35 * k, trunk, (0.35, 0.22, 0.12), "z", 6, caps=False)
            col = (0.10 + 0.08 * g, 0.36 + 0.20 * g, 0.12 + 0.05 * g)
            sc.add_cone(x, y, trunk * 0.7, 2.6 * k, 4.2 * k, col, 8)
            sc.add_cone(x, y, trunk + 2.0 * k, 1.9 * k, 3.4 * k, (col[0] * 1.1, col[1] * 1.1, col[2] * 1.1), 8)
            count += 1

    def _rocks(self, sc):
        if self.track.environment not in ("forest", "desert", "mountain", "extreme_mountain"):
            return
        base_count = self.quality_profile["rock_count"]
        count = base_count if self.track.environment in ("forest", "desert") else base_count // 2
        made, tries = 0, 0
        while made < count and tries < count * 8:
            tries += 1
            x, y = self.rng.uniform(-430, 430), self.rng.uniform(-300, 430)
            if self._dist_to_track(x, y) < 36:
                continue
            size = self.rng.uniform(0.8, 2.5)
            shade = self.rng.uniform(0.25, 0.43)
            if self.track.environment == "desert":
                shade = self.rng.uniform(0.48, 0.68)
            corners = [(-size, -size * 0.7, 0), (size, -size * 0.7, 0),
                       (-size, size * 0.7, 0), (size, size * 0.7, 0),
                       (-size * 0.65, -size * 0.5, size * 0.8),
                       (size * 0.65, -size * 0.5, size * 0.8),
                       (-size * 0.65, size * 0.5, size * 0.8),
                       (size * 0.65, size * 0.5, size * 0.8)]
            sc.add_hexa([(x + px, y + py, pz) for px, py, pz in corners],
                        (shade, shade * 1.02, shade * 1.04))
            made += 1

    def _environment_props(self, sc):
        env = self.track.environment
        rng = self.rng
        if env in ("desert", "mountain", "extreme_mountain"):
            count = self.quality_profile["landscape_prop_count"]
            made = 0
            for _ in range(count * 5):
                if made >= count:
                    break
                x, y = rng.uniform(-400, 400), rng.uniform(-300, 400)
                if self._dist_to_track(x, y) < self.track.wall_dist + 24:
                    continue
                radius = rng.uniform(12, 34) if env == "desert" else rng.uniform(16, 42)
                height = rng.uniform(4, 11) if env == "desert" else rng.uniform(8, 28)
                color = ((0.68, 0.49, 0.27) if env == "desert"
                         else self.environment["hill"])
                sc.add_cone(x, y, -1.0, radius, height, color, 9)
                made += 1
        if env == "industrial":
            palette = ((0.78, 0.28, 0.08), (0.08, 0.30, 0.50), (0.68, 0.56, 0.18))
            for i in range(0, self.track.n, max(1, self.track.n // 14)):
                side = 1 if (i // max(1, self.track.n // 14)) % 2 else -1
                x, y, heading = self._side_pos(i * self.track.ds, side * (self.track.wall_dist + 11))
                sc.add_box(x, y, 2.8, 6.0, 12.0, 5.6,
                           palette[(i // max(1, self.track.n // 14)) % len(palette)],
                           heading=heading)
        if env == "neon_city":
            for i in range(0, self.track.n, max(1, self.track.n // 12)):
                x, y, heading = self._side_pos(i * self.track.ds, self.track.wall_dist + 5.0)
                color = (0.15, 0.85, 0.95) if i % 2 else (0.90, 0.12, 0.70)
                sc.add_box(x, y, 5.0, 0.28, 1.0, 9.0, color, heading=heading)

    def _signs(self):
        t = self.track
        step = t.n // len(SIGN_TEXTS)
        for k, text in enumerate(SIGN_TEXTS):
            i = (k * step + 9) % t.n
            side = 1 if k % 2 == 0 else -1
            lat = side * (t.wall_dist + 4.5)
            x, y = t.offset_point(i, lat)
            away = (t.nx[i] * side, t.ny[i] * side)                 # points away from the track
            heading = math.degrees(math.atan2(-away[0], away[1]))   # local +Y -> away
            node = self.root.attachNewNode("sign")
            node.setPos(x, y, 0)
            node.setH(heading)
            mb = MeshBuilder("sign")
            color = SIGN_COLORS[k % len(SIGN_COLORS)]
            for sx in (-2.6, 2.6):
                mb.add_cylinder(sx, 0, 1.7, 0.12, 3.4, (0.35, 0.36, 0.4), "z", 6)
            mb.add_box(0, 0, 4.0, 6.4, 0.3, 2.4, color)
            mb.build().reparentTo(node)
            tn = TextNode("label")
            tn.setText(text)
            tn.setAlign(TextNode.ACenter)
            tn.setTextColor(1, 1, 1, 1)
            label = node.attachNewNode(tn)
            label.setPos(0, -0.18, 3.7)
            label.setScale(1.25)
            label.setTwoSided(True)

    # ---------------------------------------------------------------- update
    def update(self, focus_xy, camera_pos, dt=0.0):
        """Keep the shadow camera on the player and the sky around the camera."""
        self.sun_np.setPos(focus_xy[0] + SUN_OFFSET[0], focus_xy[1] + SUN_OFFSET[1], SUN_OFFSET[2])
        self.sky_np.setPos(camera_pos)
        if self.rain_np is not None and self.weather_profile["rain"]:
            self.rain_phase = (self.rain_phase + max(0.0, dt) * 28.0) % 22.0
            self.rain_np.setPos(camera_pos.getX() - 22.0, camera_pos.getY() - 22.0,
                                camera_pos.getZ() + 10.0 - self.rain_phase)
