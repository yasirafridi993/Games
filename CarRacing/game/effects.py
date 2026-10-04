"""Small, pooled visual effects; no effect allocates nodes during a race."""
import math
import random

from panda3d.core import (CardMaker, GeomVertexData, GeomVertexFormat, GeomVertexWriter,
                          GeomNode, Geom, GeomLines, NodePath, PNMImage, Texture)

from .graphics import GRAPHICS_PROFILES, WEATHER_PRESETS


def _sprite_texture(name, size=32):
    image = PNMImage(size, size, 4)
    for y in range(size):
        for x in range(size):
            dx = (x + 0.5 - size / 2) / (size / 2)
            dy = (y + 0.5 - size / 2) / (size / 2)
            alpha = max(0.0, min(1.0, (1.0 - dx * dx - dy * dy) * 2.4))
            image.setXelA(x, y, 1.0, 1.0, 1.0, alpha)
    texture = Texture(name)
    texture.load(image)
    texture.setMinfilter(Texture.FTLinear)
    texture.setMagfilter(Texture.FTLinear)
    return texture


class _Particle:
    __slots__ = ("node", "age", "lifetime", "vx", "vy", "vz", "size", "color", "alpha")

    def __init__(self, node):
        self.node = node
        self.age = 1.0
        self.lifetime = 1.0
        self.vx = self.vy = self.vz = 0.0
        self.size = 1.0
        self.color = (1.0, 1.0, 1.0)
        self.alpha = 1.0


class VisualEffects:
    def __init__(self, render, quality="medium", seed=71, weather="day"):
        self.render = render
        self.quality = quality
        if weather not in WEATHER_PRESETS:
            raise ValueError("Unknown visual weather: %s" % weather)
        self.weather = weather
        self.count = GRAPHICS_PROFILES[quality]["particles"]
        self.rng = random.Random(seed)
        self.root = render.attachNewNode("race-effects")
        self.sprite = self.root.attachNewNode("particle-sprite")
        cm = CardMaker("particle-card")
        cm.setFrame(-1, 1, -1, 1)
        card = self.sprite.attachNewNode(cm.generate())
        card.setTexture(_sprite_texture("smoke-sprite"))
        card.setTransparency(True)
        card.setDepthWrite(False)
        card.setLightOff()
        card.hide()
        self.card_template = card
        self.particles = []
        self.by_car = {}
        self.emit_timers = {}
        self.sparks = []

    def _pool_for(self, car):
        if car in self.by_car:
            return self.by_car[car]
        pool = []
        for _ in range(self.count):
            node = self.card_template.copyTo(self.root)
            node.hide()
            node.setBillboardPointEye()
            particle = _Particle(node)
            pool.append(particle)
            self.particles.append(particle)
        self.by_car[car] = pool
        self.emit_timers[car] = {"skid": 0.0, "dust": 0.0, "spray": 0.0, "exhaust": 0.0}
        return pool

    @staticmethod
    def _available(pool):
        return next((particle for particle in pool if particle.age >= particle.lifetime), None)

    def _emit(self, car, effect, elevation=0.0):
        particle = self._available(self._pool_for(car))
        if particle is None:
            return
        body = car.body
        fx, fy = body.forward()
        particle.age = 0.0
        if effect == "dust":
            particle.lifetime = self.rng.uniform(0.45, 0.80)
            particle.size = self.rng.uniform(0.34, 0.62)
            particle.color, particle.alpha = (0.48, 0.36, 0.24), 0.42
            back_speed, height = 1.0, 0.42
        elif effect == "spray":
            particle.lifetime = self.rng.uniform(0.30, 0.58)
            particle.size = self.rng.uniform(0.20, 0.38)
            particle.color, particle.alpha = (0.66, 0.78, 0.88), 0.30
            back_speed, height = 2.1, 0.34
        elif effect == "exhaust":
            particle.lifetime = self.rng.uniform(0.32, 0.58)
            particle.size = self.rng.uniform(0.14, 0.25)
            particle.color, particle.alpha = (0.32, 0.34, 0.37), 0.20
            back_speed, height = 1.4, 0.38
        else:
            particle.lifetime = self.rng.uniform(0.55, 1.0)
            particle.size = self.rng.uniform(0.34, 0.62)
            particle.color, particle.alpha = (0.34, 0.36, 0.39), 0.42
            back_speed, height = 1.0, 0.56
        particle.vx = -fx * self.rng.uniform(0.3, back_speed) + self.rng.uniform(-0.7, 0.7)
        particle.vy = -fy * self.rng.uniform(0.3, back_speed) + self.rng.uniform(-0.7, 0.7)
        particle.vz = (self.rng.uniform(0.12, 0.52) if effect in ("spray", "exhaust")
                       else self.rng.uniform(0.45, 1.2))
        particle.node.setPos(body.x - fx * 2.0, body.y - fy * 2.0, elevation + height)
        particle.node.setColorScale(particle.color[0], particle.color[1], particle.color[2],
                                   particle.alpha)
        particle.node.show()
        particle.node.setScale(particle.size)

    def set_weather(self, weather):
        if weather not in WEATHER_PRESETS:
            raise ValueError("Unknown visual weather: %s" % weather)
        self.weather = weather

    def update(self, cars, track, dt):
        for car in cars:
            body = car.body
            lateral_speed = abs(body.vr)
            offroad = abs(car.proj.lateral) > track.half_width if car.proj else False
            speed = abs(body.vf)
            controls = car.controls
            active = (
                ("dust", offroad and speed > 4.0, 0.09),
                ("skid", not offroad and lateral_speed > 3.5 and speed > 7.0, 0.11),
                ("spray", self.weather == "rain" and not offroad and speed > 12.0, 0.12),
                ("exhaust", controls.throttle > 0.65 and speed > 5.0, 0.22),
            )
            timers = self.emit_timers.get(car)
            if timers is None:
                if not any(enabled for _, enabled, _ in active):
                    continue
                self._pool_for(car)
                timers = self.emit_timers[car]
            for effect in timers:
                timers[effect] -= dt
            elevation = track.height_at(car.proj.s) if car.proj else 0.0
            for effect, enabled, interval in active:
                if enabled and timers[effect] <= 0.0:
                    self._emit(car, effect, elevation)
                    timers[effect] = interval

        for particle in self.particles:
            if particle.age >= particle.lifetime:
                continue
            particle.age += dt
            t = min(1.0, particle.age / particle.lifetime)
            pos = particle.node.getPos(self.render)
            particle.node.setPos(self.render, pos.x + particle.vx * dt,
                                 pos.y + particle.vy * dt, pos.z + particle.vz * dt)
            particle.size += dt * 0.55
            alpha = (1.0 - t) * particle.alpha
            particle.node.setScale(particle.size)
            particle.node.setColorScale(particle.color[0], particle.color[1], particle.color[2], alpha)
            if t >= 1.0:
                particle.node.hide()

        for particle in self.sparks:
            if particle.age >= particle.lifetime:
                continue
            particle.age += dt
            pos = particle.node.getPos(self.render)
            particle.node.setPos(self.render, pos.x + particle.vx * dt,
                                 pos.y + particle.vy * dt, pos.z + particle.vz * dt)
            particle.vz -= 8.0 * dt
            particle.node.setColorScale(1.0, 0.55 + 0.35 * math.sin(particle.age * 60),
                                        0.12, max(0.0, 1.0 - particle.age / particle.lifetime))
            if particle.age >= particle.lifetime:
                particle.node.hide()

    def emit_sparks(self, x, y, z, impact):
        limit = 8 if self.quality == "low" else 16 if self.quality == "medium" else 24
        if not self.sparks:
            line = self._make_spark_line()
            for _ in range(limit):
                node = line.copyTo(self.root)
                node.setRenderModeThickness(2.0)
                particle = _Particle(node)
                self.sparks.append(particle)
        for particle in self.sparks[:limit]:
            if particle.age < particle.lifetime:
                continue
            angle = self.rng.uniform(0.0, math.tau)
            speed = self.rng.uniform(2.0, min(13.0, impact))
            particle.age = 0.0
            particle.lifetime = self.rng.uniform(0.12, 0.30)
            particle.vx = math.cos(angle) * speed
            particle.vy = math.sin(angle) * speed
            particle.vz = self.rng.uniform(1.0, 5.0)
            particle.alpha = 1.0
            particle.node.setPos(x, y, z + 0.5)
            particle.node.setColorScale(1.0, 0.78, 0.25, 1.0)
            particle.node.show()

    def _make_spark_line(self):
        data = GeomVertexData("spark", GeomVertexFormat.getV3(), Geom.UHStatic)
        vertex = GeomVertexWriter(data, "vertex")
        vertex.addData3(0, 0, 0)
        vertex.addData3(0, 0, 0.30)
        lines = GeomLines(Geom.UHStatic)
        lines.addVertices(0, 1)
        geom = Geom(data)
        geom.addPrimitive(lines)
        node = GeomNode("spark")
        node.addGeom(geom)
        spark = NodePath(node)
        spark.hide()
        return spark

    def destroy(self):
        self.root.removeNode()
        self.particles.clear()
        self.sparks.clear()
        self.by_car.clear()
        self.emit_timers.clear()
