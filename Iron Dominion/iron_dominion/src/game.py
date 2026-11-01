"""The Game object: window, main loop, orchestration.

Multi-faction aware. Supports N opponents, teams (FFA / 2v2 / 3v3 / 4v4),
random spawns around the map, per-faction stockpiles and tech states,
per-faction AI controllers, and save/load for the whole match.
"""

import math
import random

import pygame

from . import combat
from . import config as C
from . import iso
from . import savegame
from .ai import AIController
from .build_menu import BuildMenu
from .building_defs import TOWN_CENTER, HOUSE
from .buildings import Building, BuildingManager
from .camera import Camera
from .factions import FactionManager
from .fog import FogOfWar
from .game_over import GameOverOverlay
from .hud import Hud
from .input_handler import InputHandler
from .match_config import MatchConfig
from .minimap import Minimap
from .mission_hud import MissionHud
from .missions import MISSION_LIBRARY, MISSION_ORDER
from .particles import ParticleManager
from .pathfinding import Pathfinder
from .pause_menu import PauseMenu
from .projectiles import ProjectileManager
from .renderer import TerrainRenderer
from .resources import Stockpile
from .tech import TechState
from .tech_menu import ResearchMenu
from .training_menu import TrainingMenu
from .unit_defs import WORKER, SWORDSMAN, SPEARMAN, ARCHER, CAVALRY
from .unit_manager import UnitManager
from .world import World
from .world_fx import WorldFx


class Game:
    def __init__(self, screen, mission_key="skirmish", difficulty=None,
                 saved_state=None, match_config=None):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.running = True

        # ---- Mission selection ----------------------------------------
        if mission_key not in MISSION_LIBRARY:
            mission_key = MISSION_ORDER[0]
        self.mission = MISSION_LIBRARY[mission_key]()
        if difficulty is not None:
            self.mission.enemy_difficulty = difficulty

        if saved_state is not None:
            m = saved_state.get("mission", {})
            mkey = m.get("key")
            if mkey in MISSION_LIBRARY:
                self.mission = MISSION_LIBRARY[mkey]()
            if m.get("difficulty"):
                self.mission.enemy_difficulty = m["difficulty"]

        # ---- Match config (opponents & teams) -------------------------
        if match_config is None:
            if saved_state is not None:
                mc = saved_state.get("match_config", {})
                match_config = MatchConfig(
                    num_enemies=mc.get("num_enemies", 1),
                    team_mode=mc.get("team_mode", "ffa"),
                )
            else:
                match_config = MatchConfig(num_enemies=1, team_mode="ffa")
        self.match_config = match_config
        self.factions = match_config.build_faction_manager()
        combat.set_faction_manager(self.factions)

        # ---- World ----------------------------------------------------
        self.world = World(self.mission.map_cols, self.mission.map_rows,
                           self.mission.seed)
        self.camera = Camera(C.WINDOW_WIDTH, C.WINDOW_HEIGHT,
                             self.world.bounds())
        self.camera.center_on(*self.world.center())

        # ---- Per-faction state ----------------------------------------
        self.stockpiles = {}
        self.tech_states = {}
        for f in self.factions.factions():
            self.stockpiles[f] = Stockpile()
            self.tech_states[f] = TechState()
        self.stockpile = self.stockpiles[C.FACTION_PLAYER]

        self.buildings = BuildingManager(self.world)
        self.pathfinder = Pathfinder(self.world, self.buildings)
        self.projectiles = ProjectileManager()
        self.particles = ParticleManager(self.world)
        self.units = UnitManager(
            self.world, self.buildings, self.stockpiles,
            self.pathfinder, self.projectiles, self.particles,
            self.tech_states)

        self.selected_building = None

        # ---- Spawn ----------------------------------------------------
        if saved_state is None:
            self._spawn_all_factions()
        else:
            self._restore_saved_world(saved_state)
            self.pathfinder.refresh()

        # ---- Fog ------------------------------------------------------
        self.fog = FogOfWar(self.world)
        self._fog_timer = 0.0
        for f in self.factions.factions():
            self.fog.register_faction(f)
        if saved_state is None:
            for f in self.factions.factions():
                self.fog.update(f, self.units, self.buildings)

        # ---- AI -------------------------------------------------------
        self.ais = {}
        if not self.mission.disable_ai:
            for f in self.factions.ai_factions():
                ai = AIController(self, f, self.mission.enemy_difficulty)
                tc = next(
                    (b for b in self.buildings.buildings
                     if b.owner == f and b.kind == TOWN_CENTER),
                    None)
                if tc is not None:
                    ai.set_home(tc.col, tc.row)
                if saved_state is not None:
                    ai_state = saved_state.get("ai", {})
                    if str(f) in ai_state:
                        savegame._ai_load_into(ai, ai_state[str(f)])
                self.ais[f] = ai

        # ---- Objectives -----------------------------------------------
        self.objectives = []
        self.mission_state = "in_progress"
        self.mission_elapsed = 0.0
        self.mission_banner_timer = C.MISSION_BANNER_DURATION

        if saved_state is None:
            self._build_multi_objectives()
        else:
            self._restore_objectives(saved_state)

        # ---- UI -------------------------------------------------------
        self.renderer = TerrainRenderer(self.world, self.camera)
        self.world_fx = WorldFx(self.world, self.buildings)
        self.renderer.world_fx = self.world_fx
        self.build_menu = BuildMenu(self)
        self.training_menu = TrainingMenu(self)
        self.research_menu = ResearchMenu(self)
        self.minimap = Minimap(self)
        self.mission_hud = MissionHud(self)
        self.game_over = GameOverOverlay(self)
        self.input = InputHandler(self)
        self.input.build_menu = self.build_menu
        self.input.training_menu = self.training_menu
        self.input.research_menu = self.research_menu
        self.hud = Hud(self)

        self.paused = False
        self.pause_menu = PauseMenu(self.screen)

        # ---- Optional systems (notifications, control groups) ---------
        try:
            from .notifications import NotificationCenter
            self.notifications = NotificationCenter()
            self.input.notifications = self.notifications
        except Exception:
            self.notifications = None
        try:
            from .control_groups import ControlGroups
            self.control_groups = ControlGroups(self)
            self.input.control_groups = self.control_groups
        except Exception:
            self.control_groups = None

        self.pathfinder.refresh()

    # ==================================================================
    # Convenience accessors
    # ==================================================================
    def stockpile_for(self, owner):
        return self.stockpiles.get(owner, self.stockpiles[C.FACTION_PLAYER])

    @property
    def ai(self):
        """Compatibility shim: return the first AI controller (or None).

        The HUD and a few older call sites reference ``game.ai`` as if
        there were only one opponent. The real store is ``game.ais``
        (a dict keyed by faction id). This property keeps the old
        interface alive for single-opponent code paths.
        """
        if not self.ais:
            return None
        return next(iter(self.ais.values()))

    # ==================================================================
    # SPAWNING (multiple factions at random ring points)
    # ==================================================================
    def _compute_spawn_points(self, n, margin=10):
        """Return N tile coords distributed in a ring around the map
        centre, with per-seed jitter so positions aren't perfectly
        symmetric."""
        cols, rows = self.world.cols, self.world.rows
        cx, cy = cols / 2, rows / 2
        r_x = cols * 0.34
        r_y = rows * 0.34
        rng = random.Random(self.mission.seed ^ 0x5A1F)
        base_angle = rng.uniform(0, math.tau)
        pts = []
        for i in range(n):
            angle = base_angle + i * (math.tau / max(1, n))
            c = int(cx + math.cos(angle) * r_x)
            r = int(cy + math.sin(angle) * r_y)
            c += rng.randint(-3, 3)
            r += rng.randint(-3, 3)
            c = max(margin, min(cols - margin, c))
            r = max(margin, min(rows - margin, r))
            pts.append((c, r))
        return pts

    def _spawn_all_factions(self):
        factions = self.factions.factions()
        n = len(factions)
        spawns = self._compute_spawn_points(n)

        for idx, faction in enumerate(factions):
            target = spawns[idx]
            self._spawn_faction(faction, target)

        self.pathfinder.refresh()

    def _snap_to_valid_3x3(self, col, row):
        spot = self.find_area_near(col, row, 3, 3)
        return spot if spot is not None else (col, row)

    def _spawn_faction(self, faction, target):
        col, row = self._snap_to_valid_3x3(*target)

        # Clear props around the spawn
        self.world.clear_props_in_rect(col, row, 3, 3)
        self.world.clear_props_in_rect(col - 1, row - 1, 5, 5)

        # Town Center
        tc = Building(TOWN_CENTER, col, row, world=self.world,
                      owner=faction)
        self.buildings.add(tc)

        # Starting units near the TC
        cx, cy = iso.tile_to_world(col + 1, row + 1)
        for i in range(4):
            self.units.spawn(WORKER,
                             cx + (i - 1.5) * 26.0, cy + 66.0,
                             owner=faction)
        for i in range(4):
            self.units.spawn(SWORDSMAN,
                             cx + (i - 1.5) * 26.0, cy + 100.0,
                             owner=faction)

        # Guarantee a stone and iron deposit within ~7 tiles of every
        # spawn so no faction is starved of a resource type.
        self._guarantee_deposits_near(col, row)

    def _guarantee_deposits_near(self, col, row):
        from .props import STONE_DEPOSIT, IRON_DEPOSIT
        rng = random.Random(hash((col, row)) & 0xFFFFFF)
        for kind in (STONE_DEPOSIT, IRON_DEPOSIT):
            nearby = sum(
                1 for p in self.world.props
                if p.has_resources() and p.kind == kind
                and (p.col - col) ** 2 + (p.row - row) ** 2 <= 100
            )
            for _ in range(max(0, 2 - nearby)):
                if not self._place_deposit_near(col, row, kind, rng):
                    break

    def _place_deposit_near(self, col, row, kind, rng):
        from .props import Prop
        from .terrain import WATER_TILES, MOUNTAIN
        for _ in range(80):
            dc = rng.randint(-8, 8)
            dr = rng.randint(-8, 8)
            c, r = col + dc, row + dr
            if not self.world.in_bounds(c, r):
                continue
            if abs(dc) + abs(dr) < 4:
                continue
            if dc * dc + dr * dr > 100:
                continue
            tt = self.world.terrain.get(c, r)[0]
            if tt in WATER_TILES or tt == MOUNTAIN:
                continue
            if self.world.terrain.get_elevation(c, r) != 0:
                continue
            if any(p.alive and p.col == c and p.row == r
                   for p in self.world.props):
                continue
            self.world.props.append(Prop(kind, c, r, 0.0, 0.0,
                                         rng.randrange(6)))
            hh = C.TILE_HALF_H
            wy = (c + r) * hh
            d = int(math.floor(wy / hh))
            self.world.props_by_diag.setdefault(d, []).append(
                self.world.props[-1])
            return True
        return False

    # ------------------------------------------------------------------
    def _restore_saved_world(self, saved_state):
        savegame.apply_loaded_state(self, saved_state)

    def _restore_objectives(self, saved_state):
        for od in saved_state.get("objectives", []):
            obj = savegame._objective_from_dict(od)
            if obj is not None:
                self.objectives.append(obj)

    # ==================================================================
    # OBJECTIVES
    # ==================================================================
    def _build_multi_objectives(self):
        """Either use the mission's objectives (single-player story) or
        build a multi-opponent objective set for FFA / team matches."""
        if (self.match_config.num_enemies == 1
                and self.match_config.team_mode == "ffa"):
            base = self.mission.build_objectives(self)
            if base:
                self.objectives = base
                return

        enemies = self.factions.enemies_of(C.FACTION_PLAYER)

        from .missions import Objective

        class _EliminateAll(Objective):
            def __init__(self, enemies):
                super().__init__()
                self.enemies = list(enemies)
                self.text = ("Eliminate all enemy factions"
                             if len(enemies) > 1
                             else "Eliminate the enemy")

            def update(self, game, dt):
                if self.complete:
                    return
                # No hostiles? Never auto-complete; treat as an invalid
                # setup and let the player keep playing.
                if not self.enemies:
                    return
                for f in self.enemies:
                    has_b = any(b.alive and b.owner == f
                                for b in game.buildings.buildings)
                    has_u = any(not u.dead and u.owner == f
                                for u in game.units.units)
                    if has_b or has_u:
                        return
                self.complete = True

            def progress_text(self, game):
                alive = 0
                for f in self.enemies:
                    has_b = any(b.alive and b.owner == f
                                for b in game.buildings.buildings)
                    has_u = any(not u.dead and u.owner == f
                                for u in game.units.units)
                    if has_b or has_u:
                        alive += 1
                return f"{alive} / {len(self.enemies)} enemies remaining"

        self.objectives = [_EliminateAll(enemies)]

    # ==================================================================
    # Helpers used by missions
    # ==================================================================
    def find_spawn_center(self):
        return self.find_area_near(self.world.cols // 2,
                                   self.world.rows // 2, 3, 3) or \
               (self.world.cols // 2, self.world.rows // 2)

    def find_area_near(self, target_col, target_row, fp_w, fp_h,
                       max_radius=25):
        for radius in range(0, max_radius):
            for dc in range(-radius, radius + 1):
                for dr in range(-radius, radius + 1):
                    if radius > 0 and abs(dc) != radius and abs(dr) != radius:
                        continue
                    col = target_col + dc
                    row = target_row + dr
                    if self.buildings.is_area_valid(col, row, fp_w, fp_h):
                        return col, row
        return None

    # ------------------------------------------------------------------
    # Legacy spawn helpers used by missions.py
    # ------------------------------------------------------------------
    def spawn_player_town_center(self, starting_houses=0):
        col, row = self.find_spawn_center()
        self.world.clear_props_in_rect(col, row, 3, 3)
        self.world.clear_props_in_rect(col - 1, row - 1, 5, 5)
        tc = Building(TOWN_CENTER, col, row, world=self.world,
                      owner=C.FACTION_PLAYER)
        self.buildings.add(tc)
        for i in range(int(starting_houses)):
            spot = self.find_area_near(col + 5, row + 1 + i * 4, 2, 2)
            if spot is None:
                continue
            hc, hr = spot
            self.world.clear_props_in_rect(hc, hr, 2, 2)
            hb = Building(HOUSE, hc, hr, world=self.world,
                          owner=C.FACTION_PLAYER)
            hb.complete = True
            hb.progress = 1.0
            hb.build_work = hb.build_time
            self.buildings.add(hb)
        return tc

    def spawn_player_starting_units(self, extra_workers=0, extra_soldiers=0):
        col, row = self.find_spawn_center()
        cx, cy = iso.tile_to_world(col + 1, row + 1)
        n_w = 4 + int(extra_workers)
        n_s = 4 + int(extra_soldiers)
        for i in range(n_w):
            self.units.spawn(WORKER,
                             cx + (i - (n_w - 1) * 0.5) * 26.0,
                             cy + 66.0,
                             owner=C.FACTION_PLAYER)
        for i in range(n_s):
            self.units.spawn(SWORDSMAN,
                             cx + (i - (n_s - 1) * 0.5) * 26.0,
                             cy + 100.0,
                             owner=C.FACTION_PLAYER)

    def spawn_enemy_camp(self, include_army=True, offset=None):
        """Kept for backwards compatibility with missions.py.

        Multi-faction spawns are driven by _spawn_all_factions; this is
        a no-op so old mission setup code does nothing.
        """
        return None

    # ==================================================================
    # RUN LOOP
    # ==================================================================
    def run(self):
        result = "quit"
        while self.running:
            dt = self.clock.tick(C.TARGET_FPS) / 1000.0
            if dt > C.MAX_FRAME_TIME:
                dt = C.MAX_FRAME_TIME
            self._sync_viewport()
            if self.paused:
                self._update_paused(dt)
            else:
                self._handle_events()
                self._update(dt)
            self._draw()

            if self.input.quit_requested:
                result = "quit"
                break
            if self.input.restart_requested:
                result = "restart"
                break
            if self.input.next_mission_requested:
                result = "next_mission"
                break
            if getattr(self, "_leave_to_menu", False):
                result = "main_menu"
                break
            if getattr(self, "_quicksave_request", False):
                self._quicksave_request = False
                self.save(1)
            if getattr(self, "_quickload_request", False):
                self._quickload_request = False
                result = "quickload"
                break
        return result

    def _sync_viewport(self):
        w, h = self.screen.get_size()
        if (w, h) != (int(self.camera.view_w), int(self.camera.view_h)):
            self.camera.set_viewport(w, h)

    def _handle_events(self):
        for event in pygame.event.get():
            self.input.handle_event(event)
        if self.input.quit_requested:
            self.running = False
            return
        if self.input.pause_requested:
            self.input.pause_requested = False
            self.paused = True
        if self.input.quicksave_requested:
            self.input.quicksave_requested = False
            self._quicksave_request = True
        if self.input.quickload_requested:
            self.input.quickload_requested = False
            self._quickload_request = True

    def _update_paused(self, dt):
        self.pause_menu.update_hover()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.input.quit_requested = True
                return
            action = self.pause_menu.handle_event(event)
            if action == "resume":
                self.paused = False
                return
            if action == "restart":
                self.input.restart_requested = True
                self.running = False
                return
            if action == "main_menu":
                self._leave_to_menu = True
                self.running = False
                return
            if action == "quit":
                self.input.quit_requested = True
                return
            if action == "save":
                self.paused = False
                self._open_save_browser = True
                self.running = False
                return

    # ------------------------------------------------------------------
    def _update(self, dt):
        self.world_fx.update(dt)

        if self.mission_banner_timer > 0:
            self.mission_banner_timer = max(
                0.0, self.mission_banner_timer - dt)

        if self.mission_state != "in_progress":
            self.input.update(dt)
            self.particles.update(dt)
            self.projectiles.update(dt)
            return

        self.mission_elapsed += dt
        self.input.update(dt)
        self.units.update(dt)
        self.buildings.update_production(dt, self.units, self.tech_states)
        self.particles.update(dt)

        # Fog for every faction
        self._fog_timer -= dt
        if self._fog_timer <= 0:
            self._fog_timer = C.FOG_UPDATE_INTERVAL
            for f in self.factions.factions():
                self.fog.update(f, self.units, self.buildings)

        # AI for every AI faction
        for ai in self.ais.values():
            ai.update(dt)

        self.mission.tick(self, dt)

        # Building cleanup
        if any(not b.alive for b in self.buildings.buildings):
            destroyed, new_sel = self.buildings.remove_dead(
                self.particles, self.selected_building)
            if destroyed:
                self.pathfinder.refresh()
                self.units.repath_blocked_units()
            self.selected_building = new_sel

        vx, vy = self.input.camera_velocity()
        self.camera.update(dt, vx, vy)

        self._tick_objectives(dt)

    def _tick_objectives(self, dt):
        for obj in self.objectives:
            obj.update(self, dt)

        if self.objectives and all(o.complete for o in self.objectives):
            self.mission_state = "victory"
            return

        # Defeat: player has no buildings AND no units
        has_b = any(b.alive and b.owner == C.FACTION_PLAYER
                    for b in self.buildings.buildings)
        has_u = any(not u.dead and u.owner == C.FACTION_PLAYER
                    for u in self.units.units)
        if not has_b and not has_u:
            self.mission_state = "defeat"

    # ------------------------------------------------------------------
    def save(self, slot):
        try:
            ok, msg = savegame.save_game(self, slot)
            return ok, msg
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, str(e)

    # ==================================================================
    # DRAW
    # ==================================================================
    def _draw(self):
        self.screen.fill(C.BACKGROUND_COLOR)

        # World pass
        self.renderer.draw(self.screen, self.units, self.buildings,
                           fog=self.fog, faction=C.FACTION_PLAYER)

        # Mission world overlays (e.g. control areas)
        self.mission.draw_world_overlay(self.screen, self)

        # Fog veil
        if self.input.show_fog:
            self.renderer.draw_fog_overlay(self.screen, self.fog,
                                           C.FACTION_PLAYER)

        self.world_fx.draw_smoke(self.screen, self.camera,
                                 self.fog, C.FACTION_PLAYER)

        # Debug overlays
        if self.input.show_grid:
            self.renderer.draw_grid(self.screen)
        if self.input.show_paths:
            self.renderer.draw_unit_paths(self.screen, self.units)

        # Effects
        self.projectiles.draw(self.screen, self.camera)
        self.particles.draw(self.screen, self.camera)

        # Placement ghost or hover highlight
        if (self.input.placement_kind is not None
                and self.input.placement_anchor
                and self.mission_state == "in_progress"
                and not self.paused):
            ac, ar = self.input.placement_anchor
            self.renderer.draw_placement_ghost(
                self.screen, self.input.placement_kind,
                ac, ar, self.input.placement_valid)
        else:
            col, row = self.hovered_tile()
            self.renderer.draw_hover(self.screen, col, row)

        # Selection box + markers
        box = self.input.get_selection_box()
        if box is not None:
            self._draw_selection_box(self.screen, box)
        if self.input.move_marker is not None:
            self._draw_move_marker(self.screen)
        if self.input.attack_move_armed:
            self._draw_attack_move_cursor(self.screen)

        # Minimap
        if self.minimap is not None:
            self.minimap.draw(self.screen)

        # Right-side menus
        if self.training_menu.is_active():
            self.training_menu.draw(self.screen)
        elif self.research_menu.is_active():
            self.research_menu.draw(self.screen)
        else:
            self.build_menu.draw(self.screen)

        # HUD layers
        self.hud.draw(self.screen)
        self.mission_hud.draw(self.screen)
        self.game_over.draw(self.screen)

        # Notifications
        if self.notifications is not None:
            self.notifications.draw(self.screen)

        # Pause overlay
        if self.paused:
            self.pause_menu.draw(self.screen)

        pygame.display.flip()

    # ------------------------------------------------------------------
    def _draw_selection_box(self, surface, rect):
        if rect.width < 2 or rect.height < 2:
            return
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        overlay.fill(C.SELECTION_BOX_FILL)
        surface.blit(overlay, rect.topleft)
        pygame.draw.rect(surface, C.SELECTION_BOX_OUTLINE, rect, 1)

    def _draw_move_marker(self, surface):
        wx, wy, ttl, kind = self.input.move_marker
        total = {"move": C.MOVE_MARKER_TTL,
                 "gather": C.GATHER_MARKER_TTL,
                 "build": C.BUILD_MARKER_TTL,
                 "attack": C.ATTACK_MARKER_TTL}.get(kind, C.MOVE_MARKER_TTL)
        color = {"move": (110, 230, 130),
                 "gather": (255, 216, 110),
                 "build": (232, 196, 92),
                 "attack": (230, 90, 80)}.get(kind, (110, 230, 130))
        cam = self.camera
        col, row = iso.world_to_tile(wx, wy)
        if self.world.in_bounds(col, row):
            e = self.world.terrain.elevation[row][col]
            sx, sy = cam.world_to_screen(wx, wy - e * C.ELEVATION_PIXELS)
        else:
            sx, sy = cam.world_to_screen(wx, wy)
        progress = 1.0 - (ttl / total)
        radius = int((10 + progress * 18) * cam.zoom)
        alpha = int(220 * (1.0 - progress))
        if radius < 1:
            return
        size = radius * 2 + 6
        ring = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*color, alpha),
                           (size // 2, size // 2), radius,
                           max(2, int(2 * cam.zoom)))
        surface.blit(ring, (sx - size // 2, sy - size // 2))

    def _draw_attack_move_cursor(self, surface):
        mx, my = self.input.mouse_pos
        size = 12
        pygame.draw.line(surface, (230, 90, 80),
                         (mx - size, my), (mx + size, my), 2)
        pygame.draw.line(surface, (230, 90, 80),
                         (mx, my - size), (mx, my + size), 2)
        pygame.draw.circle(surface, (230, 90, 80), (mx, my), size, 2)

    def hovered_tile(self):
        wx, wy = self.camera.screen_to_world(*self.input.mouse_pos)
        return iso.world_to_tile(wx, wy)