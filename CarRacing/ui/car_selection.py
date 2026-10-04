"""Garage screen for inspecting and selecting a car profile."""
from game.car_model import CarModel
from game.cars import CARS
from panda3d.core import AmbientLight, DirectionalLight, Vec4
from . import theme


class CarSelectionScreen(theme.Screen):
    def __init__(self, app, setup, on_next, on_back):
        super().__init__(app, 0.58, (3.0, 2.0))
        self.panel["frameColor"] = (*theme.PANEL[:3], 0.34)
        self.app, self.setup = app, setup
        self.on_next, self.on_back = on_next, on_back
        self.index = next((i for i, car in enumerate(CARS) if car.car_id == setup.car_id), 0)
        self.preview_model = None
        self.rotation = 0.0
        self.preview_ambient = self.app.camera.attachNewNode(AmbientLight("garage-preview-ambient"))
        self.preview_ambient.node().setColor(Vec4(0.62, 0.66, 0.74, 1.0))
        self.preview_key = DirectionalLight("garage-preview-key")
        self.preview_key.setColor(Vec4(1.0, 0.91, 0.76, 1.0))
        self.preview_key_np = self.app.camera.attachNewNode(self.preview_key)
        self.preview_key_np.setPos(-5.0, -4.0, 8.0)
        self.preview_key_np.lookAt(0.8, 9.0, -1.0)
        p = self.panel
        theme.label(p, "GARAGE", (0, 0.80), scale=0.11, fg=theme.TEXT)
        theme.label(p, "CAR PREVIEW", (-0.74, 0.52), scale=0.045, fg=theme.MUTED)
        self.name = theme.label(p, "", (0.63, 0.42), scale=0.075, fg=theme.ACCENT,
                                may_change=True)
        self.category = theme.label(p, "", (0.63, 0.26), scale=0.048, fg=theme.GOLD,
                                    may_change=True)
        self.description = theme.label(p, "", (0.63, 0.08), scale=0.036, fg=theme.MUTED,
                                       may_change=True)
        self.stats = theme.label(p, "", (0.63, -0.22), scale=0.039, fg=theme.TEXT,
                                 may_change=True)
        self.previous = theme.button(p, "PREVIOUS", self._previous, (-0.48, 0, -0.48),
                                     width=0.8, height=0.11, text_scale=0.043)
        self.next = theme.button(p, "NEXT", self._next, (0.48, 0, -0.48),
                                 width=0.8, height=0.11, text_scale=0.043)
        theme.button(p, "BACK", on_back, (-0.66, 0, -0.76),
                     width=0.72, height=0.11, text_scale=0.046)
        theme.button(p, "SELECT CAR", on_next, (0.66, 0, -0.76),
                     width=0.96, height=0.11, text_scale=0.046)
        self._refresh()

    def _previous(self):
        self.index = (self.index - 1) % len(CARS)
        self._refresh()

    def _next(self):
        self.index = (self.index + 1) % len(CARS)
        self._refresh()

    def _refresh(self):
        definition = CARS[self.index]
        self.setup.car_id = definition.car_id
        self.name.setText(definition.name)
        self.category.setText(definition.category.upper())
        self.description.setText(definition.description)
        self.stats.setText("SPEED   %3d%%\nACCEL   %3d%%\nHANDLING   %3d%%\nBRAKING   %3d%%\nGRIP   %3d%%" %
                           tuple(round(value * 100) for value in
                                 (definition.speed, definition.acceleration, definition.handling,
                                  definition.braking, definition.grip)))
        if self.preview_model is not None:
            self.preview_model.destroy()
        self.preview_model = CarModel(self.app.camera, definition.color, definition)
        self.preview_model.root.setPos(-2.35, 9.0, -0.55)
        self.preview_model.root.setScale(0.66)
        self.preview_model.root.setH(self.rotation)
        self.preview_model.root.setLight(self.preview_ambient)
        self.preview_model.root.setLight(self.preview_key_np)

    def update(self, dt):
        if self.visible and self.preview_model is not None:
            self.rotation = (self.rotation + dt * 12.0) % 360.0
            self.preview_model.root.setH(self.rotation)

    def hide(self):
        super().hide()
        if self.preview_model is not None:
            self.preview_model.root.hide()

    def show(self):
        super().show()
        if self.preview_model is not None:
            self.preview_model.root.show()

    def destroy(self):
        if self.preview_model is not None:
            self.preview_model.destroy()
        self.preview_ambient.removeNode()
        self.preview_key_np.removeNode()
