"""Keyboard / mouse input collection and command dispatch."""

import math

import pygame

from . import config as C
from . import iso
from .building_defs import BUILDING_DEFS
from .tech import TECH_DEFS
from .unit_defs import UNIT_DEFS, WORKER


class InputHandler:
    def __init__(self, game):
        self.game = game

        self.quit_requested = False
        self.pause_requested = False
        self.mouse_pos = (0, 0)
        self._wheel_delta = 0.0

        self._dragging_pan = False
        self._drag_last = (0, 0)

        self._drag_start = None
        self._dragging_select = False
        self._select_box = None

        self._dragging_minimap = False

        # Set True when MOUSEDOWN was consumed by a UI element so the
        # matching MOUSEUP is not interpreted as a world click.
        self._ui_click_consumed = False

        self.move_marker = None
        self.edge_scroll = True
        self.show_grid = False
        self.show_paths = False
        self.show_fog = True
        self.attack_move_armed = False

        self.placement_kind = None
        self.placement_anchor = None
        self.placement_valid = False

        self.build_menu = None
        self.training_menu = None
        self.research_menu = None

        self.restart_requested = False
        self.next_mission_requested = False

        self.quicksave_requested = False
        self.quickload_requested = False

        self.control_groups = None
        self.notifications = None

    # ------------------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.quit_requested = True
            return
        if event.type == pygame.KEYDOWN:
            self._on_key_down(event)
            return
        if event.type == pygame.MOUSEMOTION:
            self.mouse_pos = event.pos
            if self._dragging_pan:
                dx = event.pos[0] - self._drag_last[0]
                dy = event.pos[1] - self._drag_last[1]
                self._drag_last = event.pos
                self.game.camera.pan_screen(-dx, -dy)
            elif self._dragging_minimap:
                self._minimap_recenter(event.pos)
            elif self._dragging_select:
                self._update_select_box(event.pos)
            if self.placement_kind is not None:
                self._update_placement(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._on_mouse_down(event)
            return
        if event.type == pygame.MOUSEBUTTONUP:
            self._on_mouse_up(event)
            return
        if event.type == pygame.MOUSEWHEEL:
            self._wheel_delta += event.y
            return

    # ------------------------------------------------------------------
    def _on_key_down(self, event):
        # Control groups handle plain-number / ctrl-number keys first
        if self.control_groups is not None:
            if self.control_groups.handle_key(event.key, event.mod):
                return

        if event.key == pygame.K_ESCAPE:
            if self.placement_kind is not None:
                self._cancel_placement()
                return
            if self.attack_move_armed:
                self.attack_move_armed = False
                return
            self.pause_requested = True
        elif event.key == pygame.K_F1:
            self.edge_scroll = not self.edge_scroll
        elif event.key == pygame.K_g:
            self.show_grid = not self.show_grid
        elif event.key == pygame.K_p:
            self.show_paths = not self.show_paths
        elif event.key == pygame.K_f:
            self.show_fog = not self.show_fog
        elif event.key == pygame.K_r:
            self.restart_requested = True
        elif event.key == pygame.K_n:
            self.next_mission_requested = True
        elif event.key == pygame.K_F5:
            self.quicksave_requested = True
        elif event.key == pygame.K_F9:
            self.quickload_requested = True
        elif event.key == pygame.K_F11:
            try:
                pygame.display.toggle_fullscreen()
            except pygame.error:
                pass
        elif event.key == pygame.K_a and (event.mod & pygame.KMOD_CTRL):
            player_units = [u for u in self.game.units.units
                            if not u.dead and u.owner == C.FACTION_PLAYER]
            self.game.units.select_units(player_units, additive=False)
        elif event.key == pygame.K_a:
            if self.game.units.selected:
                self.attack_move_armed = True
        elif event.key == pygame.K_h:
            self.game.units.issue_stop(self.game.units.selected)
        elif event.key == pygame.K_z and (event.mod & pygame.KMOD_CTRL):
            self.game.units.issue_stop(self.game.units.selected)
        elif event.key == pygame.K_PERIOD:
            self.game.units.issue_stop(self.game.units.selected)

    # ------------------------------------------------------------------
    # Mouse down
    # ------------------------------------------------------------------
    def _on_mouse_down(self, event):
        if event.button == 1:
            self._ui_click_consumed = False

        if event.button == 2:
            self._dragging_pan = True
            self._drag_last = event.pos
            return

        if event.button == 1:
            # --- Placement confirm ---
            if self.placement_kind is not None:
                self._try_place(event.pos)
                self._ui_click_consumed = True
                return

            # --- Training menu ---
            tm = self.training_menu
            if tm is not None and tm.is_active():
                kind = tm.hit_test_unit(event.pos)
                if kind is not None:
                    self._try_enqueue(kind)
                    self._ui_click_consumed = True
                    return
                if tm._panel_rect.collidepoint(event.pos):
                    self._ui_click_consumed = True
                    return

            # --- Research menu ---
            rm = self.research_menu
            if rm is not None and rm.is_active():
                key = rm.hit_test_tech(event.pos)
                if key is not None:
                    self._try_research(key)
                    self._ui_click_consumed = True
                    return
                if rm._panel_rect.collidepoint(event.pos):
                    self._ui_click_consumed = True
                    return

            # --- Build menu ---
            if self.build_menu is not None:
                kind = self.build_menu.hit_test(event.pos)
                if kind is not None:
                    self._start_placement(kind)
                    self._ui_click_consumed = True
                    return
                if self.build_menu._panel_rect.collidepoint(event.pos):
                    self._ui_click_consumed = True
                    return

            # --- Minimap ---
            minimap = self.game.minimap
            if minimap is not None and minimap.hit_test(event.pos):
                self._dragging_minimap = True
                self._minimap_recenter(event.pos)
                self._ui_click_consumed = True
                return

            # --- World: begin drag-select ---
            self._drag_start = event.pos
            self._dragging_select = False
            self._select_box = None
            return

        if event.button == 3:
            # --- Placement cancel ---
            if self.placement_kind is not None:
                self._cancel_placement()
                return
            if self.attack_move_armed:
                self.attack_move_armed = False
                return

            # --- Training panel: cancel last queue item ---
            tm = self.training_menu
            if (tm is not None and tm.is_active()
                    and tm._panel_rect.collidepoint(event.pos)):
                b = tm.active_building()
                if b is not None and b.queue is not None and b.queue.items:
                    cancelled = b.queue.cancel_last()
                    if cancelled is not None:
                        self._refund(cancelled.unit_kind)
                return

            # --- Research panel: cancel current research ---
            rm = self.research_menu
            if (rm is not None and rm.is_active()
                    and rm._panel_rect.collidepoint(event.pos)):
                b = rm.active_building()
                if (b is not None and b.research_queue is not None
                        and b.research_queue.items):
                    cancelled = b.research_queue.cancel_last()
                    if cancelled is not None:
                        self._refund_tech(cancelled.key)
                return

            # --- Build panel: swallow ---
            if (self.build_menu is not None
                    and self.build_menu._panel_rect.collidepoint(event.pos)):
                return

            # --- Minimap ---
            minimap = self.game.minimap
            if minimap is not None and minimap.hit_test(event.pos):
                self._dragging_minimap = True
                self._minimap_recenter(event.pos)
                return

            # --- World: context command ---
            self._issue_context_command(event.pos)
            return

    # ------------------------------------------------------------------
    def _on_mouse_up(self, event):
        if event.button == 2:
            self._dragging_pan = False
            return

        if self._dragging_minimap and event.button in (1, 3):
            self._dragging_minimap = False
            return

        if event.button == 1:
            # The matching mouse-down was on a UI element: swallow the up
            # event so it does not trigger a world click.
            if self._ui_click_consumed:
                self._ui_click_consumed = False
                self._drag_start = None
                self._dragging_select = False
                self._select_box = None
                return

            if self.placement_kind is not None:
                return

            shift = (pygame.key.get_pressed()[pygame.K_LSHIFT]
                     or pygame.key.get_pressed()[pygame.K_RSHIFT])
            if self._dragging_select and self._select_box:
                units = self.game.units.units_in_screen_rect(
                    self.game.camera, self._select_box,
                    owner_filter=C.FACTION_PLAYER)
                self.game.units.select_units(units, additive=shift)
            else:
                b = self.game.buildings.building_at_screen(
                    self.game.camera, event.pos[0], event.pos[1],
                    owner_filter=C.FACTION_PLAYER)
                if b is not None:
                    self.game.units.clear_selection()
                    self.game.selected_building = b
                    for other in self.game.buildings.buildings:
                        other.selected = (other is b)
                    self._dragging_select = False
                    self._select_box = None
                    self._drag_start = None
                    return
                unit = self.game.units.unit_at_screen(
                    self.game.camera, event.pos[0], event.pos[1],
                    owner_filter=C.FACTION_PLAYER)
                if unit:
                    self.game.units.select_single(unit, additive=shift)
                    for other in self.game.buildings.buildings:
                        other.selected = False
                    self.game.selected_building = None
                else:
                    if not shift:
                        self.game.units.clear_selection()
                        for other in self.game.buildings.buildings:
                            other.selected = False
                        self.game.selected_building = None
            self._dragging_select = False
            self._select_box = None
            self._drag_start = None
            return

    # ------------------------------------------------------------------
    def _minimap_recenter(self, pos):
        wx, wy = self.game.minimap.screen_to_world(pos)
        self.game.camera.x = wx
        self.game.camera.y = wy
        self.game.camera.vel_x = 0.0
        self.game.camera.vel_y = 0.0
        self.game.camera.clamp()

    def _update_select_box(self, pos):
        x0, y0 = self._drag_start
        x1, y1 = pos
        self._select_box = pygame.Rect(
            min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))

    # ------------------------------------------------------------------
    def _issue_context_command(self, pos):
        game = self.game
        wx, wy = game.camera.screen_to_world(*pos)
        selected = game.units.selected
        if not selected:
            return

        # Attack-move armed
        if self.attack_move_armed:
            game.units.issue_attack_move(selected, wx, wy)
            self.move_marker = [wx, wy, C.ATTACK_MARKER_TTL, "attack"]
            self.attack_move_armed = False
            return

        # Enemy unit under cursor -> attack
        enemy_unit = game.units.enemy_unit_at_screen(
            game.camera, pos[0], pos[1], C.FACTION_PLAYER)
        if enemy_unit is not None:
            game.units.issue_attack(selected, enemy_unit)
            self.move_marker = [wx, wy, C.ATTACK_MARKER_TTL, "attack"]
            return

        # Enemy building under cursor -> attack
        enemy_b = game.buildings.enemy_building_at_screen(
            game.camera, pos[0], pos[1], C.FACTION_PLAYER)
        if enemy_b is not None:
            game.units.issue_attack(selected, enemy_b)
            self.move_marker = [wx, wy, C.ATTACK_MARKER_TTL, "attack"]
            return

        # Friendly building under cursor
        tile_col, tile_row = iso.world_to_tile(wx, wy)
        b = game.buildings.building_at_tile(tile_col, tile_row)

        # 1. Incomplete friendly foundation -> send workers to build
        if (b is not None and not b.complete
                and b.owner == C.FACTION_PLAYER):
            workers = [u for u in selected if u.kind == WORKER]
            if workers:
                game.units.issue_build(workers, b)
                self.move_marker = [wx, wy, C.BUILD_MARKER_TTL, "build"]
                return

        # 2. Completed friendly Farm -> gather food from it
        if (b is not None and b.complete
                and b.owner == C.FACTION_PLAYER
                and b.kind == "farm"):
            workers = [u for u in selected if u.kind == WORKER]
            if workers:
                game.units.issue_gather(workers, b)
                self.move_marker = [wx, wy, C.GATHER_MARKER_TTL, "gather"]
                return

        # 3. Resource node -> gather
        node = game.world.pick_prop(wx, wy)
        if node is not None:
            workers = [u for u in selected if u.kind == WORKER]
            if workers:
                game.units.issue_gather(workers, node)
                self.move_marker = [wx, wy, C.GATHER_MARKER_TTL, "gather"]
                return

        # 4. Move
        game.units.issue_move(selected, wx, wy)
        self.move_marker = [wx, wy, C.MOVE_MARKER_TTL, "move"]

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------
    def _start_placement(self, kind):
        if not BUILDING_DEFS[kind]["buildable"]:
            return
        if not self.game.stockpile.can_afford(BUILDING_DEFS[kind]["cost"]):
            if self.notifications:
                self.notifications.warn("Not enough resources")
            return
        self.game.units.clear_selection()
        for other in self.game.buildings.buildings:
            other.selected = False
        self.game.selected_building = None
        self.placement_kind = kind
        self._update_placement(self.mouse_pos)

    def _cancel_placement(self):
        self.placement_kind = None
        self.placement_anchor = None
        self.placement_valid = False

    def _update_placement(self, pos):
        kind = self.placement_kind
        if kind is None:
            return
        wx, wy = self.game.camera.screen_to_world(*pos)
        cf, rf = iso.world_to_tile_f(wx, wy)
        col = int(math.floor(cf))
        row = int(math.floor(rf))
        fp_w, fp_h = BUILDING_DEFS[kind]["footprint"]
        anchor_col = col - (fp_w - 1) // 2
        anchor_row = row - (fp_h - 1) // 2
        self.placement_anchor = (anchor_col, anchor_row)
        self.placement_valid = (
            self.game.buildings.is_area_valid(anchor_col, anchor_row,
                                              fp_w, fp_h)
            and self.game.stockpile.can_afford(BUILDING_DEFS[kind]["cost"]))

    def _try_place(self, pos):
        self._update_placement(pos)
        if not self.placement_valid or self.placement_anchor is None:
            if self.notifications:
                self.notifications.error("Cannot build here")
            return
        game = self.game
        kind = self.placement_kind
        defn = BUILDING_DEFS[kind]
        if not game.stockpile.spend(defn["cost"]):
            return
        col, row = self.placement_anchor
        fp_w, fp_h = defn["footprint"]
        game.world.clear_props_in_rect(col, row, fp_w, fp_h)

        from .buildings import Building
        b = Building(kind, col, row, world=game.world,
                     owner=C.FACTION_PLAYER)
        game.buildings.add(b)
        game.pathfinder.refresh()
        game.units.repath_blocked_units()

        workers = [u for u in game.units.selected if u.kind == WORKER]
        if workers:
            game.units.issue_build(workers, b)

        shift = (pygame.key.get_pressed()[pygame.K_LSHIFT]
                 or pygame.key.get_pressed()[pygame.K_RSHIFT])
        if shift and game.stockpile.can_afford(defn["cost"]):
            self._update_placement(pos)
        else:
            self._cancel_placement()

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    def _try_enqueue(self, unit_kind):
        game = self.game
        b = game.selected_building
        if b is None or b.queue is None or not b.complete:
            return
        if b.owner != C.FACTION_PLAYER:
            return
        defn = UNIT_DEFS[unit_kind]
        if not game.stockpile.can_afford(defn["cost"]):
            if self.notifications:
                self.notifications.warn(
                    f"Not enough resources for {defn['name']}")
            return
        if not game.units.can_train_more(unit_kind, game.buildings):
            if self.notifications:
                self.notifications.warn("Population cap reached")
            return
        if not b.queue.can_enqueue():
            if self.notifications:
                self.notifications.info("Training queue full")
            return
        if not game.stockpile.spend(defn["cost"]):
            return
        b.queue.enqueue(unit_kind)

    def _refund(self, unit_kind):
        defn = UNIT_DEFS[unit_kind]
        for r, amt in defn["cost"].items():
            self.game.stockpile.add(r, amt)

    # ------------------------------------------------------------------
    # Research
    # ------------------------------------------------------------------
    def _try_research(self, key):
        game = self.game
        b = game.selected_building
        if b is None or b.research_queue is None or not b.complete:
            return
        if b.owner != C.FACTION_PLAYER:
            return
        ts = game.tech_states.get(C.FACTION_PLAYER)
        if ts is None:
            return
        if not ts.is_available(key):
            return
        defn = TECH_DEFS[key]
        if not game.stockpile.can_afford(defn.cost):
            if self.notifications:
                self.notifications.warn(
                    f"Not enough resources for {defn.name}")
            return
        if not b.research_queue.can_enqueue():
            if self.notifications:
                self.notifications.info("Already researching")
            return
        if not game.stockpile.spend(defn.cost):
            return
        b.research_queue.enqueue(key)

    def _refund_tech(self, key):
        for r, amt in TECH_DEFS[key].cost.items():
            self.game.stockpile.add(r, amt)

    # ------------------------------------------------------------------
    def update(self, dt):
        if self._wheel_delta:
            factor = C.ZOOM_STEP ** self._wheel_delta
            self.game.camera.zoom_by(factor, self.mouse_pos)
            self._wheel_delta = 0.0

        if self._drag_start is not None and not self._dragging_select:
            mx, my = self.mouse_pos
            sx, sy = self._drag_start
            if (mx - sx) ** 2 + (my - sy) ** 2 > 25:
                self._dragging_select = True
                self._update_select_box(self.mouse_pos)

        if self.move_marker is not None:
            self.move_marker[2] -= dt
            if self.move_marker[2] <= 0:
                self.move_marker = None

        tm = self.training_menu
        rm = self.research_menu
        bm = self.build_menu
        if tm is not None and tm.is_active():
            tm.hovered = tm.hit_test_unit(self.mouse_pos)
            if rm is not None:
                rm.hovered = None
            if bm is not None:
                bm.hovered = None
        elif rm is not None and rm.is_active():
            rm.hovered = rm.hit_test_tech(self.mouse_pos)
            if tm is not None:
                tm.hovered = None
            if bm is not None:
                bm.hovered = None
        else:
            if bm is not None:
                bm.hovered = bm.hit_test(self.mouse_pos)
            if tm is not None:
                tm.hovered = None
            if rm is not None:
                rm.hovered = None

    def get_selection_box(self):
        return self._select_box if self._dragging_select else None

    # ------------------------------------------------------------------
    def camera_velocity(self):
        cam = self.game.camera
        key_speed = C.KEY_CAMERA_SPEED / cam.zoom
        vx = 0.0
        vy = 0.0
        keys = pygame.key.get_pressed()
        kx = ky = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            kx -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            kx += 1.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            ky -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            ky += 1.0
        mag = math.hypot(kx, ky)
        if mag > 0.0:
            vx += kx / mag * key_speed
            vy += ky / mag * key_speed
        if self.edge_scroll:
            ex, ey = self._edge_vector()
            if ex or ey:
                vx += ex * C.EDGE_SCROLL_SPEED / cam.zoom
                vy += ey * C.EDGE_SCROLL_SPEED / cam.zoom
        cap = max(C.KEY_CAMERA_SPEED, C.EDGE_SCROLL_SPEED) / cam.zoom
        mag = math.hypot(vx, vy)
        if mag > cap:
            vx = vx / mag * cap
            vy = vy / mag * cap
        return vx, vy

    def _edge_vector(self):
        cam = self.game.camera
        vw, vh = cam.view_w, cam.view_h
        mx, my = self.mouse_pos
        if not pygame.mouse.get_focused():
            return 0.0, 0.0
        if not (0 <= mx < vw and 0 <= my < vh):
            return 0.0, 0.0
        m = float(C.EDGE_SCROLL_MARGIN)
        ex = ey = 0.0
        if mx < m:
            ex = -(1.0 - mx / m)
        elif mx > vw - m:
            ex = 1.0 - (vw - mx) / m
        if my < m:
            ey = -(1.0 - my / m)
        elif my > vh - m:
            ey = 1.0 - (vh - my) / m
        return ex, ey