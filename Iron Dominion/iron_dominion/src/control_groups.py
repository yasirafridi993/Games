"""Control groups: Ctrl+1..9 to assign, 1..9 to recall.

Double-tapping a group number in quick succession recentres the camera on
the group.
"""

import pygame

from . import config as C


_DOUBLE_TAP_WINDOW = 0.35


class ControlGroups:
    def __init__(self, game):
        self.game = game
        self.groups = {i: [] for i in range(1, 10)}
        self._last_tap_key = None
        self._last_tap_time = 0.0

    # ------------------------------------------------------------------
    def update(self, dt):
        if self._last_tap_key is not None:
            self._last_tap_time += dt
            if self._last_tap_time > _DOUBLE_TAP_WINDOW:
                self._last_tap_key = None
                self._last_tap_time = 0.0

    # ------------------------------------------------------------------
    def assign(self, index, units=None):
        if units is None:
            units = self.game.units.selected
        # Store a snapshot; each entry is a live Unit reference. Dead units
        # are pruned when the group is recalled.
        self.groups[index] = [u for u in units if not u.dead]

    def recall(self, index):
        group = [u for u in self.groups.get(index, []) if not u.dead]
        self.groups[index] = group
        if not group:
            return
        self.game.units.select_units(group, additive=False)

        # Double-tap -> center camera on the group's centroid
        now = pygame.time.get_ticks() / 1000.0
        if self._last_tap_key == index and \
                (now - self._last_tap_time) < _DOUBLE_TAP_WINDOW:
            self._center_on(group)
            self._last_tap_key = None
        else:
            self._last_tap_key = index
            self._last_tap_time = now

    def _center_on(self, group):
        if not group:
            return
        cx = sum(u.x for u in group) / len(group)
        cy = sum(u.y for u in group) / len(group)
        cam = self.game.camera
        cam.x = cx
        cam.y = cy
        cam.vel_x = 0.0
        cam.vel_y = 0.0
        cam.clamp()

    # ------------------------------------------------------------------
    def handle_key(self, key, mods):
        """Return True if this key was consumed by a control group action."""
        if pygame.K_1 <= key <= pygame.K_9:
            idx = key - pygame.K_0  # K_1 -> 1, ..., K_9 -> 9
            if mods & pygame.KMOD_CTRL:
                # Ctrl+number assigns
                if self.game.units.selected:
                    self.assign(idx)
                    self.game.notifications.info(f"Group {idx} set "
                                                 f"({len(self.groups[idx])})")
                return True
            else:
                # Plain number recalls
                self.recall(idx)
                return True
        return False