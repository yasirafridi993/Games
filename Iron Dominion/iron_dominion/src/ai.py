"""Enemy AI: base building, economy, army, attack/defend, scouting, research.

The AI issues the exact same commands the player does (issue_gather,
issue_move, issue_attack, issue_build). Difficulty modifies *decisions* only:
how often it thinks, how many workers it wants, how big an army it needs
before attacking, how aggressive it is with buildings, and how far it can
"see". It never gets a damage, HP or speed bonus.

Phase 10 adds:
  * Blacksmith / Market to the build orders
  * _manage_research(), which queues techs at the AI's research buildings
    according to a fixed priority list.
"""

import math
import random

from . import config as C
from . import iso
from .building_defs import (
    TOWN_CENTER, HOUSE, BARRACKS, ARCHERY_RANGE, STABLE, TOWER,
    BLACKSMITH, MARKET, BUILDING_DEFS,
)
from .resources import FOOD, WOOD, STONE, IRON
from .tech import TECH_DEFS
from .unit_defs import (
    WORKER, SWORDSMAN, SPEARMAN, ARCHER, CAVALRY,
    UNIT_DEFS,
)
from .units import BuildTask


# ---------------------------------------------------------------------------
# Difficulty levels
# ---------------------------------------------------------------------------
DIFFICULTY_EASY = "easy"
DIFFICULTY_MEDIUM = "medium"
DIFFICULTY_HARD = "hard"

AI_DIFFICULTY = {
    DIFFICULTY_EASY: {
        "decision_interval": 2.0,
        "worker_target": 6,
        "house_buffer": 2,
        "army_attack_threshold": 10,
        "army_defend_threshold": 3,
        "army_max": 14,
        "scout_interval": 25.0,
        "aggression": 0.35,
        "build_delay": 6.0,
        "vision_tiles": 18.0,
        "resource_targets": {
            "early": {FOOD: 3, WOOD: 3, STONE: 0, IRON: 0},
            "mid":   {FOOD: 3, WOOD: 3, STONE: 1, IRON: 1},
            "late":  {FOOD: 3, WOOD: 3, STONE: 2, IRON: 2},
        },
        "build_order": [
            (HOUSE, 2), (BARRACKS, 1), (HOUSE, 3),
            (MARKET, 1), (ARCHERY_RANGE, 1), (BLACKSMITH, 1),
            (HOUSE, 4), (STABLE, 1),
        ],
        "unit_mix": {SWORDSMAN: 3, ARCHER: 2, SPEARMAN: 2, CAVALRY: 1},
    },
    DIFFICULTY_MEDIUM: {
        "decision_interval": 1.2,
        "worker_target": 10,
        "house_buffer": 4,
        "army_attack_threshold": 8,
        "army_defend_threshold": 4,
        "army_max": 22,
        "scout_interval": 15.0,
        "aggression": 0.6,
        "build_delay": 3.5,
        "vision_tiles": 22.0,
        "resource_targets": {
            "early": {FOOD: 4, WOOD: 4, STONE: 0, IRON: 0},
            "mid":   {FOOD: 4, WOOD: 4, STONE: 2, IRON: 2},
            "late":  {FOOD: 4, WOOD: 4, STONE: 3, IRON: 3},
        },
        "build_order": [
            (HOUSE, 2), (BARRACKS, 1), (MARKET, 1), (HOUSE, 3),
            (ARCHERY_RANGE, 1), (BLACKSMITH, 1), (HOUSE, 4),
            (STABLE, 1), (TOWER, 2), (HOUSE, 6), (BARRACKS, 2),
        ],
        "unit_mix": {SWORDSMAN: 3, ARCHER: 3, SPEARMAN: 2, CAVALRY: 2},
    },
    DIFFICULTY_HARD: {
        "decision_interval": 0.7,
        "worker_target": 14,
        "house_buffer": 6,
        "army_attack_threshold": 6,
        "army_defend_threshold": 5,
        "army_max": 30,
        "scout_interval": 10.0,
        "aggression": 0.85,
        "build_delay": 2.0,
        "vision_tiles": 26.0,
        "resource_targets": {
            "early": {FOOD: 5, WOOD: 5, STONE: 1, IRON: 1},
            "mid":   {FOOD: 5, WOOD: 5, STONE: 3, IRON: 3},
            "late":  {FOOD: 5, WOOD: 5, STONE: 4, IRON: 4},
        },
        "build_order": [
            (HOUSE, 2), (BARRACKS, 1), (MARKET, 1),
            (ARCHERY_RANGE, 1), (BLACKSMITH, 1), (HOUSE, 3),
            (STABLE, 1), (HOUSE, 4), (BARRACKS, 2), (MARKET, 2),
            (BLACKSMITH, 2), (TOWER, 3), (HOUSE, 8), (ARCHERY_RANGE, 2),
        ],
        "unit_mix": {SWORDSMAN: 3, ARCHER: 4, SPEARMAN: 3, CAVALRY: 3},
    },
}


# ---------------------------------------------------------------------------
# AI controller
# ---------------------------------------------------------------------------
class AIController:
    def __init__(self, game, owner, difficulty=DIFFICULTY_MEDIUM):
        self.game = game
        self.owner = owner
        self.difficulty_name = difficulty
        self.cfg = AI_DIFFICULTY[difficulty]
        self.rng = random.Random(0xA1B2C3 ^ (owner * 7919))

        # Timers
        self.decision_timer = 0.5
        self.build_delay_timer = 0.0
        self.scout_timer = 5.0

        # Home base
        self.home_col = 0
        self.home_row = 0
        self.home_wx = 0.0
        self.home_wy = 0.0

        # Strategic state
        self.phase = "early"
        self.state = "developing"

        # Unit lists (refreshed every decision tick)
        self.workers = []
        self.army = []

        # Vision
        self.known_enemy_units = []
        self.known_enemy_buildings = []
        self.remembered_enemy_positions = []

        # Scouting
        self.scout_target = None

    def _is_own(self, entity):
        return entity.owner == self.owner

    def _is_enemy(self, entity):
        return self.game.factions.are_hostile(self.owner, entity.owner)
    # ------------------------------------------------------------------
    def set_home(self, col, row):
        self.home_col = col
        self.home_row = row
        self.home_wx, self.home_wy = iso.tile_to_world(col, row)

    # ------------------------------------------------------------------
    def update(self, dt):
        self.build_delay_timer = max(0.0, self.build_delay_timer - dt)
        self.scout_timer = max(0.0, self.scout_timer - dt)
        self.decision_timer -= dt
        if self.decision_timer <= 0:
            self.decision_timer = self.cfg["decision_interval"]
            try:
                self._think()
            except Exception as e:
                import traceback
                print(f"[AI:{self.owner}] {e}")
                traceback.print_exc()

    # ------------------------------------------------------------------
    def _think(self):
        self._classify_units()
        self._update_vision()
        self._update_phase()
        self._update_state()
        self._manage_economy()
        self._manage_worker_production()
        self._manage_build_order()
        self._manage_military_production()
        self._manage_research()
        self._manage_army()
        self._manage_scouting()

    # ------------------------------------------------------------------
    def _classify_units(self):
        self.workers = []
        self.army = []
        for u in self.game.units.units:
            if u.dead or u.owner != self.owner:
                continue
            if u.kind == WORKER:
                self.workers.append(u)
            else:
                self.army.append(u)

    # ------------------------------------------------------------------
    def _update_vision(self):
        our_positions = [
            (u.x, u.y) for u in self.game.units.units
            if not u.dead and self._is_enemy(u)
        ]
        our_positions += [
            (b.x, b.y) for b in self.game.buildings.buildings
            if b.alive and self._is_own(b)
        ]

        self.known_enemy_units = []
        self.known_enemy_buildings = []

        if not our_positions:
            return

        max_d2 = (self.cfg["vision_tiles"] * C.TILE_HALF_W) ** 2

        for u in self.game.units.units:
            if u.dead or u.owner == self.owner:
                continue
            for (ox, oy) in our_positions:
                dx = u.x - ox
                dy = u.y - oy
                if dx * dx + dy * dy <= max_d2:
                    self.known_enemy_units.append(u)
                    break

        for b in self.game.buildings.buildings:
            if not b.alive or b.owner == self.owner:
                continue
            for (ox, oy) in our_positions:
                dx = b.x - ox
                dy = b.y - oy
                if dx * dx + dy * dy <= max_d2:
                    self.known_enemy_buildings.append(b)
                    self._remember_enemy_position(b.x, b.y)
                    break

    def _remember_enemy_position(self, wx, wy):
        for (px, py) in self.remembered_enemy_positions:
            if (px - wx) ** 2 + (py - wy) ** 2 < (200.0 ** 2):
                return
        self.remembered_enemy_positions.append((wx, wy))
        if len(self.remembered_enemy_positions) > 6:
            self.remembered_enemy_positions.pop(0)

    # ------------------------------------------------------------------
    def _update_phase(self):
        pop = self.game.units.total_population(self.owner)
        if pop < 10:
            self.phase = "early"
        elif pop < 22:
            self.phase = "mid"
        else:
            self.phase = "late"

    # ------------------------------------------------------------------
    def _update_state(self):
        threat = self._detect_threat()
        n_army = len(self.army)

        if threat and n_army < self.cfg["army_defend_threshold"] + 4:
            self.state = "defending"
        elif n_army >= self.cfg["army_attack_threshold"]:
            self.state = "attacking"
        else:
            self.state = "developing"

    def _detect_threat(self):
        our_buildings = [
            (b.x, b.y) for b in self.game.buildings.buildings
            if b.alive and b.owner == self.owner
        ]
        if not our_buildings:
            return False
        radius_sq = (12 * C.TILE_HALF_W) ** 2
        for eu in self.game.units.units:
            if eu.dead or self._is_own(eu):
                continue
            for (bx, by) in our_buildings:
                dx = eu.x - bx
                dy = eu.y - by
                if dx * dx + dy * dy <= radius_sq:
                    return True
        return False

    # ------------------------------------------------------------------
    # Economy
    # ------------------------------------------------------------------
    def _manage_economy(self):
        desired = self.cfg["resource_targets"][self.phase]

        by_resource = {FOOD: 0, WOOD: 0, STONE: 0, IRON: 0}
        idle = []

        for w in self.workers:
            task = w.task
            if task is None:
                idle.append(w)
                continue
            if isinstance(task, BuildTask):
                continue
            node = getattr(task, "node", None)
            if node is not None and node.has_resources():
                r = node.resource_type
                if r in by_resource:
                    by_resource[r] += 1
                    continue
            idle.append(w)

        if not idle:
            return

        nodes_by_type = {FOOD: [], WOOD: [], STONE: [], IRON: []}
        for p in self.game.world.props:
            if not p.has_resources():
                continue
            r = p.resource_type
            if r in nodes_by_type:
                nodes_by_type[r].append(p)

        for w in idle:
            best_r = None
            best_short = -1
            for r, want in desired.items():
                short = want - by_resource.get(r, 0)
                if short > best_short:
                    best_short = short
                    best_r = r
            if best_r is None:
                best_r = FOOD

            node = self._nearest_node(nodes_by_type.get(best_r, []), w)
            if node is None:
                for r in (FOOD, WOOD, STONE, IRON):
                    node = self._nearest_node(nodes_by_type.get(r, []), w)
                    if node is not None:
                        best_r = r
                        break
            if node is None:
                continue

            self.game.units.issue_gather([w], node)
            by_resource[best_r] = by_resource.get(best_r, 0) + 1

    @staticmethod
    def _nearest_node(nodes, unit):
        if not nodes:
            return None
        best = None
        best_d2 = float("inf")
        for p in nodes:
            px, py = p.world_position()
            dx = px - unit.x
            dy = py - unit.y
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                best = p
        return best

    # ------------------------------------------------------------------
    # Production
    # ------------------------------------------------------------------
    def _manage_worker_production(self):
        tc = None
        for b in self.game.buildings.buildings:
            if (b.alive and b.owner == self.owner and b.complete
                    and b.kind == TOWN_CENTER):
                tc = b
                break
        if tc is None or tc.queue is None:
            return

        worker_count = len(self.workers)
        queued = sum(1 for it in tc.queue.items if it.unit_kind == WORKER)
        if worker_count + queued >= self.cfg["worker_target"]:
            return
        if len(tc.queue.items) >= 2:
            return

        defn = UNIT_DEFS[WORKER]
        sp = self.game.stockpile_for(self.owner)
        if not sp.can_afford(defn["cost"]):
            return
        if not self.game.units.can_train_more(
                WORKER, self.game.buildings, self.owner):
            return
        if not sp.spend(defn["cost"]):
            return
        tc.queue.enqueue(WORKER)

    # ------------------------------------------------------------------
    def _manage_build_order(self):
        # Ensure every incomplete building has a builder assigned
        for b in self.game.buildings.buildings:
            if not b.alive or b.owner != self.owner or b.complete:
                continue
            has_builder = False
            for w in self.workers:
                t = w.task
                if isinstance(t, BuildTask) and t.building is b:
                    has_builder = True
                    break
            if not has_builder:
                w = self._find_free_worker()
                if w is not None:
                    self.game.units.issue_build([w], b)

        if self.build_delay_timer > 0:
            return

        # Don't start a new building while one is in progress
        for b in self.game.buildings.buildings:
            if b.alive and b.owner == self.owner and not b.complete:
                return

        # If we're running out of pop, prioritize a house
        pop = self.game.units.total_population(self.owner)
        cap = self.game.buildings.total_pop_capacity(self.owner)
        if (cap - pop) <= self.cfg["house_buffer"]:
            if self._try_place_building(HOUSE):
                self.build_delay_timer = self.cfg["build_delay"]
                return

        for kind, target_count in self.cfg["build_order"]:
            have = sum(
                1 for b in self.game.buildings.buildings
                if b.alive and b.owner == self.owner and b.kind == kind
            )
            if have < target_count:
                if self._try_place_building(kind):
                    self.build_delay_timer = self.cfg["build_delay"]
                return

    def _try_place_building(self, kind):
        defn = BUILDING_DEFS[kind]
        sp = self.game.stockpile_for(self.owner)
        if not sp.can_afford(defn["cost"]):
            return False

        fp_w, fp_h = defn["footprint"]
        spot = self._find_build_spot(fp_w, fp_h)
        if spot is None:
            return False
        col, row = spot

        if not sp.spend(defn["cost"]):
            return False

        self.game.world.clear_props_in_rect(col, row, fp_w, fp_h)

        from .buildings import Building
        b = Building(kind, col, row, world=self.game.world, owner=self.owner)
        self.game.buildings.add(b)
        self.game.pathfinder.refresh()
        self.game.units.repath_blocked_units()

        w = self._find_free_worker()
        if w is not None:
            self.game.units.issue_build([w], b)
        return True

    def _find_build_spot(self, fp_w, fp_h):
        for radius in range(2, 22):
            for dc in range(-radius, radius + 1):
                for dr in range(-radius, radius + 1):
                    if max(abs(dc), abs(dr)) != radius:
                        continue
                    if abs(dc) <= 1 and abs(dr) <= 1:
                        continue
                    col = self.home_col + dc
                    row = self.home_row + dr
                    if not self.game.buildings.is_area_valid(
                            col, row, fp_w, fp_h):
                        continue
                    if self._rect_has_resource(col, row, fp_w, fp_h):
                        continue
                    return (col, row)
        return None

    def _rect_has_resource(self, col, row, w, h):
        for p in self.game.world.props:
            if not p.has_resources():
                continue
            if col <= p.col < col + w and row <= p.row < row + h:
                return True
        return False

    def _find_free_worker(self):
        for w in self.workers:
            if w.task is None:
                return w
        for r in (IRON, STONE, WOOD, FOOD):
            for w in self.workers:
                t = w.task
                node = getattr(t, "node", None) if t else None
                if node is not None and node.resource_type == r:
                    return w
        return self.workers[0] if self.workers else None

    # ------------------------------------------------------------------
    def _manage_military_production(self):
        for b in self.game.buildings.buildings:
            if not b.alive or b.owner != self.owner:
                continue
            if not b.complete or b.queue is None:
                continue
            if b.kind == TOWN_CENTER:
                continue
            if len(b.queue.items) >= 2:
                continue
            produces = BUILDING_DEFS[b.kind].get("produces", ())
            if not produces:
                continue

            sp = self.game.stockpile_for(self.owner)
            affordable = [
                k for k in produces if sp.can_afford(UNIT_DEFS[k]["cost"])
            ]
            affordable = [
                k for k in affordable
                if self.game.units.can_train_more(
                    k, self.game.buildings, self.owner)
            ]
            if not affordable:
                continue

            mix = self.cfg["unit_mix"]
            current = {}
            for u in self.army:
                current[u.kind] = current.get(u.kind, 0) + 1
            for ob in self.game.buildings.buildings:
                if ob.alive and ob.owner == self.owner and ob.queue:
                    for item in ob.queue.items:
                        if item.unit_kind == WORKER:
                            continue
                        current[item.unit_kind] = \
                            current.get(item.unit_kind, 0) + 1

            total_want = sum(mix.values()) or 1
            total_have = sum(current.values()) or 1
            best_kind = None
            best_gap = -1e9
            for k in affordable:
                want = mix.get(k, 0) / total_want
                have = current.get(k, 0) / total_have
                gap = want - have
                if gap > best_gap:
                    best_gap = gap
                    best_kind = k

            if best_kind is None:
                continue
            if not sp.spend(UNIT_DEFS[best_kind]["cost"]):
                continue
            b.queue.enqueue(best_kind)

    # ------------------------------------------------------------------
    # Research (Phase 10)
    # ------------------------------------------------------------------
    def _manage_research(self):
        tech_state = self.game.tech_states.get(self.owner)
        if tech_state is None:
            return
        sp = self.game.stockpile_for(self.owner)

        for b in self.game.buildings.buildings:
            if not b.alive or b.owner != self.owner or not b.complete:
                continue
            if b.research_queue is None or b.research_queue.items:
                continue
            for key in self._research_priority():
                defn = TECH_DEFS[key]
                if defn.building != b.kind:
                    continue
                if not tech_state.is_available(key):
                    continue
                if not sp.can_afford(defn.cost):
                    continue
                if not sp.spend(defn.cost):
                    continue
                b.research_queue.enqueue(key)
                break

    def _research_priority(self):
        # Economy techs first if worker count is high, then military.
        return [
            "better_tools", "improved_carts",
            "forged_weapons", "plated_armor",
            "swift_pack", "tempered_steel", "masterwork_armor",
        ]

    # ------------------------------------------------------------------
    # Army
    # ------------------------------------------------------------------
    def _manage_army(self):
        if not self.army:
            return

        if self.state == "defending":
            threats = self._find_threats_near_home()
            if threats:
                for u in self.army:
                    if u.attack_target is None:
                        t = min(threats, key=lambda e: (e.x - u.x) ** 2
                                                     + (e.y - u.y) ** 2)
                        self.game.units.issue_attack([u], t)
            else:
                self._send_army_to(self.home_wx + 90, self.home_wy + 90)

        elif self.state == "attacking":
            if self.known_enemy_buildings:
                target = min(
                    self.known_enemy_buildings,
                    key=lambda b: (b.x - self.home_wx) ** 2
                                  + (b.y - self.home_wy) ** 2,
                )
                for u in self.army:
                    if u.attack_target is None:
                        self.game.units.issue_attack([u], target)
                return

            if self.remembered_enemy_positions:
                tx, ty = self.remembered_enemy_positions[0]
                self._send_army_to(tx, ty)
                return

            mid_wx = (self.game.world.min_x + self.game.world.max_x) * 0.5
            mid_wy = (self.game.world.min_y + self.game.world.max_y) * 0.5
            self._send_army_to(mid_wx, mid_wy)

        else:
            self._send_army_to(self.home_wx + 90, self.home_wy + 90)

    def _send_army_to(self, wx, wy):
        idle = [
            u for u in self.army
            if u.attack_target is None and u.state == "idle"
        ]
        if idle:
            self.game.units.issue_move(idle, wx, wy)

    def _find_threats_near_home(self):
        out = []
        radius_sq = (14 * C.TILE_HALF_W) ** 2
        for eu in self.known_enemy_units:
            dx = eu.x - self.home_wx
            dy = eu.y - self.home_wy
            if dx * dx + dy * dy <= radius_sq:
                out.append(eu)
        return out

    # ------------------------------------------------------------------
    def _manage_scouting(self):
        if self.scout_timer > 0:
            return
        self.scout_timer = self.cfg["scout_interval"]

        if not self.army:
            return

        fastest = max(self.army, key=lambda u: u.speed)
        if fastest.state != "idle" or fastest.attack_target is not None:
            return

        angle = self.rng.uniform(0.0, 2.0 * math.pi)
        dist = self.rng.uniform(500.0, 1200.0)
        wx = self.home_wx + math.cos(angle) * dist
        wy = self.home_wy + math.sin(angle) * dist
        wx = max(self.game.world.min_x + 100,
                 min(self.game.world.max_x - 100, wx))
        wy = max(self.game.world.min_y + 100,
                 min(self.game.world.max_y - 100, wy))

        self.game.units.issue_move([fastest], wx, wy)