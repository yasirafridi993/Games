"""Unit manager: spawn, update, selection, tasks, pathfinding, combat.

Phase 15 additions:
  * Throttled repath queue — `repath_blocked_units` only queues units,
    `process_repath_queue` consumes up to N per frame from `update`.
"""

import math

from . import combat
from . import config as C
from . import iso
from .pathfinding import path_to_waypoints, smooth_path
from .unit_defs import UNIT_DEFS, WORKER
from .units import (
    Unit, UnitState, WorkerTask, BuildTask,
    facing_from_world_velocity,
)


class UnitManager:
    def __init__(self, world, buildings, stockpiles, pathfinder,
                 projectiles, particles, tech_states):
        self.world = world
        self.buildings = buildings
        self.stockpiles = stockpiles
        self.pathfinder = pathfinder
        self.projectiles = projectiles
        self.particles = particles
        self.tech_states = tech_states

        self.units = []
        self.selected = []
        self.by_diagonal = {}
        self._pending_prop_culls = []

        # Cumulative death counter per faction (used by mission objectives)
        self.deaths_by_faction = {C.FACTION_PLAYER: 0, C.FACTION_ENEMY: 0}

        # Phase 15: throttled repath queue
        self._repath_queue = []

    # ------------------------------------------------------------------
    # Spawning
    # ------------------------------------------------------------------
    def spawn(self, kind, wx, wy, owner=0):
        u = Unit(kind, wx, wy, owner=owner)
        ts = self.tech_states.get(owner)
        if ts is not None:
            u.apply_tech(ts)
        self.units.append(u)
        return u

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------
    def update(self, dt):
        for u in self.units:
            if u.dead:
                continue
            u.update(dt)
            if u.kind == WORKER and u.task is not None:
                if isinstance(u.task, WorkerTask):
                    self._update_worker_gather(u, dt)
                elif isinstance(u.task, BuildTask):
                    self._update_worker_build(u, dt)

        for u in self.units:
            if u.dead:
                continue
            self._update_combat(u, dt)

        impacts = self.projectiles.update(dt)
        self._resolve_projectile_impacts(impacts)

        if any(u.dead for u in self.units):
            self._remove_dead()

        self._rebuild_diagonals()
        self._cull_props()

        # Phase 15: spend a slice of the frame repathing blocked units
        self.process_repath_queue()

    # ------------------------------------------------------------------
    def apply_tech_to_faction(self, tech_state, owner):
        for u in self.units:
            if u.dead:
                continue
            if u.owner != owner:
                continue
            u.apply_tech(tech_state)

    # ------------------------------------------------------------------
    def _rebuild_diagonals(self):
        by = {}
        for u in self.units:
            if u.dead:
                continue
            by.setdefault(u.diagonal(), []).append(u)
        self.by_diagonal = by

    def _cull_props(self):
        if not self._pending_prop_culls:
            return
        for prop in self._pending_prop_culls:
            try:
                self.world.props.remove(prop)
            except ValueError:
                pass
            d = prop.col + prop.row
            lst = self.world.props_by_diag.get(d)
            if lst is not None:
                try:
                    lst.remove(prop)
                except ValueError:
                    pass
        self._pending_prop_culls.clear()

    def _schedule_prop_cull(self, prop):
        if prop not in self._pending_prop_culls:
            self._pending_prop_culls.append(prop)

    # ------------------------------------------------------------------
    def _remove_dead(self):
        alive = []
        for u in self.units:
            if u.dead:
                self.particles.spawn_death(u.x, u.y, u.owner)
                self.deaths_by_faction[u.owner] = (
                    self.deaths_by_faction.get(u.owner, 0) + 1)
                if u.selected:
                    try:
                        self.selected.remove(u)
                    except ValueError:
                        pass
            else:
                alive.append(u)
        self.units = alive

    # ------------------------------------------------------------------
    # Combat
    # ------------------------------------------------------------------
    def _update_combat(self, unit, dt):
        if unit.hit_flash > 0:
            unit.hit_flash -= dt

        if unit.state == UnitState.ATTACKING:
            target = unit.attack_target
            if target is None:
                unit.set_idle()
                return

            from .units import Unit as _Unit
            if isinstance(target, _Unit):
                if target.dead or not combat.is_hostile(unit, target):
                    unit.set_idle()
                    return
                tx, ty, tr = target.x, target.y, target.radius
            else:
                if not getattr(target, "alive", False) \
                        or not combat.is_hostile(unit, target):
                    unit.set_idle()
                    return
                fp = max(target.fp_w, target.fp_h)
                tx, ty, tr = target.x, target.y, fp * C.TILE_HALF_W * 0.55

            dx = tx - unit.x
            dy = ty - unit.y
            dist = math.hypot(dx, dy)
            reach = unit.attack_range + tr

            if dist <= reach:
                if unit.path:
                    unit.path.clear()
                unit.facing = facing_from_world_velocity(dx, dy)
                if unit.attack_timer > 0:
                    unit.attack_timer -= dt
                if unit.attack_timer <= 0:
                    self._perform_attack(unit, target)
                    unit.attack_timer = unit.attack_cooldown
            else:
                unit.attack_repath_timer -= dt
                if (not unit.path) or unit.attack_repath_timer <= 0:
                    self._assign_destination(unit, tx, ty)
                    unit.attack_repath_timer = C.COMBAT_REPATH_INTERVAL
            return

        if not self._can_auto_acquire(unit):
            return

        target = combat.find_best_target(
            unit, self.units, self.buildings.buildings, unit.aggro_range
        )
        if target is not None:
            unit.set_attacking(target)

    def _can_auto_acquire(self, unit):
        if unit.kind == WORKER:
            return False
        if unit.owner is None:
            return False
        if unit.state != UnitState.IDLE:
            return False
        if unit.task is not None:
            return False
        if unit.aggro_range <= 0:
            return False
        return True

    def _perform_attack(self, attacker, target):
        from .units import Unit as _Unit
        if isinstance(target, _Unit):
            dmg = combat.compute_damage(attacker.kind, target.kind,
                                        attacker.damage, target.armor)
            proj = UNIT_DEFS[attacker.kind].get("projectile")
            if proj:
                self.projectiles.spawn(
                    attacker.x, attacker.y - 20.0, target, dmg,
                    attacker.kind, attacker.owner)
            else:
                target.take_damage(dmg)
                self.particles.spawn_hit(target.x, target.y, target.kind)
            return

        dmg = combat.compute_damage(attacker.kind, "building",
                                    attacker.damage, 3)
        proj = UNIT_DEFS[attacker.kind].get("projectile")
        if proj:
            self.projectiles.spawn(
                attacker.x, attacker.y - 20.0, target, dmg,
                attacker.kind, attacker.owner)
        else:
            target.take_damage(dmg)
            self.particles.spawn_building_hit(target.x, target.y)

    def _resolve_projectile_impacts(self, impacts):
        from .units import Unit as _Unit
        for p in impacts:
            t = p.target
            if t is None:
                continue
            if isinstance(t, _Unit):
                if t.dead:
                    continue
                t.take_damage(p.damage)
                self.particles.spawn_hit(t.x, t.y, t.kind)
            else:
                if not getattr(t, "alive", False):
                    continue
                t.take_damage(p.damage)
                self.particles.spawn_building_hit(t.x, t.y)

    # ------------------------------------------------------------------
    # Pathfinding
    # ------------------------------------------------------------------
    def _assign_destination(self, unit, wx, wy):
        start_cf, start_rf = unit.tile_position()
        start_col = int(math.floor(start_cf))
        start_row = int(math.floor(start_rf))

        goal_cf, goal_rf = iso.world_to_tile_f(wx, wy)
        goal_col = int(math.floor(goal_cf))
        goal_row = int(math.floor(goal_rf))

        tiles = self.pathfinder.find_path(start_col, start_row,
                                          goal_col, goal_row)
        if tiles is None:
            unit.set_path([(float(wx), float(wy))])
            return

        tiles = smooth_path(self.pathfinder.grid, tiles)
        waypoints = path_to_waypoints(tiles, final_world_xy=(wx, wy))
        if not waypoints:
            waypoints = [(float(wx), float(wy))]
        unit.set_path(waypoints)

    # ------------------------------------------------------------------
    def repath_blocked_units(self):
        """Queue every unit whose path is blocked for a fresh path.

        Called immediately when a new building appears. The actual A*
        re-search happens gradually in `process_repath_queue`.
        """
        grid = self.pathfinder.grid
        queue = self._repath_queue
        queue.clear()
        for u in self.units:
            if u.dead or not u.path:
                continue
            needs = False
            for (wx, wy) in u.path:
                cf, rf = iso.world_to_tile_f(wx, wy)
                c = int(math.floor(cf))
                r = int(math.floor(rf))
                if grid.is_blocked(c, r):
                    needs = True
                    break
            if needs:
                queue.append(u)

    def process_repath_queue(self, max_per_frame=8):
        """Repath up to `max_per_frame` queued units this frame."""
        if not self._repath_queue:
            return
        budget = max_per_frame
        while self._repath_queue and budget > 0:
            u = self._repath_queue.pop(0)
            if u.dead or not u.path:
                continue
            dest = u.path[-1]
            self._assign_destination(u, dest[0], dest[1])
            budget -= 1

    # ------------------------------------------------------------------
    # Worker gather
    # ------------------------------------------------------------------
    def _update_worker_gather(self, worker, dt):
        task = worker.task

        # ---------- Walking to the node --------------------------------
        if task.mode == task.MODE_TO_NODE:
            if task.node is None or not task.node.has_resources():
                # Node vanished or was depleted on our way here. Try to
                # pick a different node of the same type; if none, deposit
                # what we have or idle.
                if self._redirect_to_next_node(worker, task,
                                               exclude=task.node):
                    return
                if worker.carrying > 0 and task.dropoff is not None:
                    task.mode = task.MODE_TO_DROPOFF
                    self._assign_destination(worker, task.drop_wx,
                                             task.drop_wy)
                else:
                    self._finish_task(worker)
                return
            if worker.state == UnitState.IDLE:
                task.mode = task.MODE_GATHERING
                worker.set_working()
                task.timer = 0.0
            return

        # ---------- Harvesting ----------------------------------------
        if task.mode == task.MODE_GATHERING:
            node = task.node
            if node is None or not node.has_resources():
                # Node depleted. If it was a Prop and no longer alive,
                # cull it from the world.
                if (node is not None and not node.alive
                        and not getattr(node, "is_resource", lambda: False)()
                        or (node is not None and not node.alive
                            and hasattr(node, "kind"))):
                    # Only cull real props, never buildings
                    from .buildings import Building as _B
                    if not isinstance(node, _B):
                        self._schedule_prop_cull(node)
                # Still have room in the backpack? Try the next node.
                if worker.carrying < worker.carry_capacity:
                    if self._redirect_to_next_node(worker, task,
                                                   exclude=node):
                        return
                # Full or no next node -> head home
                if worker.carrying > 0:
                    task.mode = task.MODE_TO_DROPOFF
                    self._assign_destination(worker, task.drop_wx,
                                             task.drop_wy)
                else:
                    self._finish_task(worker)
                return

            dx = task.node_wx - worker.x
            dy = task.node_wy - worker.y
            worker.facing = facing_from_world_velocity(dx, dy)
            worker.gather_buffer += (dt * worker.gather_rate_mult
                                     / C.WORKER_GATHER_TIME)
            while (worker.gather_buffer >= 1.0
                   and worker.carrying < worker.carry_capacity):
                worker.gather_buffer -= 1.0
                got = node.harvest(1)
                if got <= 0:
                    break
                worker.carrying += got

            # Full backpack, or node completely exhausted
            if (worker.carrying >= worker.carry_capacity
                    or not node.has_resources()):
                # If the node is a prop and it's now dead, cull it
                if node is not None and not node.alive:
                    from .buildings import Building as _B
                    if not isinstance(node, _B):
                        self._schedule_prop_cull(node)
                # Not full, still room: try to continue at a nearby node
                if (worker.carrying < worker.carry_capacity
                        and self._redirect_to_next_node(worker, task,
                                                        exclude=node)):
                    return
                # Otherwise head to the drop-off
                task.mode = task.MODE_TO_DROPOFF
                self._assign_destination(worker, task.drop_wx,
                                         task.drop_wy)
            return

        # ---------- Returning to drop-off -----------------------------
        if task.mode == task.MODE_TO_DROPOFF:
            if task.dropoff is None or not task.dropoff.alive:
                self._finish_task(worker)
                return
            if worker.state == UnitState.IDLE:
                task.mode = task.MODE_DEPOSIT
                worker.set_working()
                task.timer = 0.0
            return

        # ---------- Depositing ----------------------------------------
        if task.mode == task.MODE_DEPOSIT:
            task.timer += dt
            if task.timer >= C.WORKER_DEPOSIT_TIME:
                if worker.carrying > 0 and worker.carrying_type is not None:
                    sp = self.stockpiles.get(worker.owner)
                    if sp is not None:
                        sp.add(worker.carrying_type, worker.carrying)
                    worker.carrying = 0
                # Loop back to a resource. Prefer the original node; if
                # it's depleted, find the nearest replacement.
                if (task.node is not None and task.node.has_resources()
                        and task.node.alive):
                    task.mode = task.MODE_TO_NODE
                    self._assign_destination(worker, task.node_wx,
                                             task.node_wy)
                elif self._redirect_to_next_node(worker, task,
                                                 exclude=task.node,
                                                 next_mode="to_node"):
                    return
                else:
                    self._finish_task(worker)
            return

    # ------------------------------------------------------------------
    def _redirect_to_next_node(self, worker, task, exclude=None,
                               next_mode="to_node"):
        """Find the nearest node of the same resource and send the worker
        there. Returns True on success, False if no replacement exists.
        """
        rtype = worker.carrying_type
        if rtype is None:
            rtype = getattr(task.node, "resource_type", None)
        if rtype is None:
            return False
        next_node = self.world.pick_nearest_resource(
            rtype, worker.x, worker.y, max_dist=520.0, exclude=exclude)
        if next_node is None:
            return False
        nwx, nwy = next_node.world_position()
        # Stand slightly to the side of the node so workers don't stack
        # exactly on top of it.
        import random as _r
        off = _r.uniform(0, 6.28)
        stand_r = C.WORKER_NODE_STANDOFF
        tx = nwx + math.cos(off) * stand_r
        ty = nwy + math.sin(off) * stand_r
        task.node = next_node
        task.node_wx = tx
        task.node_wy = ty
        task.mode = task.MODE_TO_NODE
        worker.gather_buffer = 0.0
        self._assign_destination(worker, tx, ty)
        return True

    def _update_worker_build(self, worker, dt):
        task = worker.task
        b = task.building
        if b is None or not b.alive or b.complete:
            self._finish_task(worker)
            return
        if worker.state == UnitState.IDLE:
            worker.set_working()
        if worker.state == UnitState.WORKING:
            dx = b.x - worker.x
            dy = b.y - worker.y
            worker.facing = facing_from_world_velocity(dx, dy)
            if b.add_build_work(dt):
                self._finish_task(worker)

    def _finish_task(self, worker):
        worker.task = None
        worker.carrying = 0
        worker.carrying_type = None
        worker.gather_buffer = 0.0
        worker.set_idle()

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    def clear_selection(self):
        for u in self.selected:
            u.selected = False
        self.selected.clear()

    def select_single(self, unit, additive=False):
        if not additive:
            self.clear_selection()
            unit.selected = True
            self.selected.append(unit)
        else:
            if unit.selected:
                unit.selected = False
                try:
                    self.selected.remove(unit)
                except ValueError:
                    pass
            else:
                unit.selected = True
                self.selected.append(unit)

    def select_units(self, units, additive=False):
        if not additive:
            self.clear_selection()
        for u in units:
            if not u.selected:
                u.selected = True
                self.selected.append(u)

    # ------------------------------------------------------------------
    # Picking
    # ------------------------------------------------------------------
    def unit_at_screen(self, camera, sx, sy, owner_filter=None):
        best = None
        best_y = -float("inf")
        zoom = camera.zoom
        world = self.world
        terrain = world.terrain
        for u in self.units:
            if u.dead:
                continue
            if owner_filter is not None and u.owner != owner_filter:
                continue
            col, row = u.tile_position()
            c, r = int(math.floor(col)), int(math.floor(row))
            e = terrain.get_elevation(c, r) if world.in_bounds(c, r) else 0
            ux, uy = camera.world_to_screen(u.x, u.y - e * C.ELEVATION_PIXELS)
            cxp = ux
            cyp = uy - 14.0 * zoom
            rx = max(4.0, u.radius * 1.15 * zoom)
            ry = max(6.0, u.radius * 1.85 * zoom)
            nx = (sx - cxp) / rx
            ny = (sy - cyp) / ry
            if nx * nx + ny * ny <= 1.0 and u.y > best_y:
                best_y = u.y
                best = u
        return best

    def enemy_unit_at_screen(self, camera, sx, sy, attacker_owner):
        best = None
        best_y = -float("inf")
        zoom = camera.zoom
        world = self.world
        terrain = world.terrain
        for u in self.units:
            if u.dead:
                continue
            if u.owner == attacker_owner:
                continue
            col, row = u.tile_position()
            c, r = int(math.floor(col)), int(math.floor(row))
            e = terrain.get_elevation(c, r) if world.in_bounds(c, r) else 0
            ux, uy = camera.world_to_screen(u.x, u.y - e * C.ELEVATION_PIXELS)
            cxp = ux
            cyp = uy - 14.0 * zoom
            rx = max(4.0, u.radius * 1.15 * zoom)
            ry = max(6.0, u.radius * 1.85 * zoom)
            nx = (sx - cxp) / rx
            ny = (sy - cyp) / ry
            if nx * nx + ny * ny <= 1.0 and u.y > best_y:
                best_y = u.y
                best = u
        return best

    def units_in_screen_rect(self, camera, rect, owner_filter=None):
        result = []
        world = self.world
        terrain = world.terrain
        for u in self.units:
            if u.dead:
                continue
            if owner_filter is not None and u.owner != owner_filter:
                continue
            col, row = u.tile_position()
            c, r = int(math.floor(col)), int(math.floor(row))
            e = terrain.get_elevation(c, r) if world.in_bounds(c, r) else 0
            sx, sy = camera.world_to_screen(u.x, u.y - e * C.ELEVATION_PIXELS)
            if rect.collidepoint(sx, sy):
                result.append(u)
        return result

    # ------------------------------------------------------------------
    # Formations
    # ------------------------------------------------------------------
    def _formation_slots(self, center_col, center_row, n):
        if n <= 0:
            return []
        if n == 1:
            slot = self._snap_walkable(center_col, center_row)
            return [slot] if slot else []

        cols = int(math.ceil(math.sqrt(n)))
        rows = int(math.ceil(n / cols))
        sx = C.FORMATION_SPACING_COLS
        sy = C.FORMATION_SPACING_ROWS

        result = []
        for i in range(n):
            gx = i % cols
            gy = i // cols
            dx = int((gx - (cols - 1) * 0.5) * sx)
            dy = int((gy - (rows - 1) * 0.5) * sy)
            slot = self._snap_walkable(center_col + dx, center_row + dy)
            if slot is not None:
                result.append(slot)
        while len(result) < n:
            slot = self._snap_walkable(center_col, center_row)
            if slot is None:
                break
            result.append(slot)
        return result

    def _snap_walkable(self, col, row):
        if not self.pathfinder.grid.is_blocked(col, row):
            return (col, row)
        return self.pathfinder._nearest_walkable(col, row, max_radius=5)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def issue_move(self, units, target_wx, target_wy):
        if not units:
            return
        for u in units:
            u.cancel_task()
            u.attack_target = None

        cf, rf = iso.world_to_tile_f(target_wx, target_wy)
        center_col = int(math.floor(cf))
        center_row = int(math.floor(rf))

        if len(units) == 1:
            units[0].state = UnitState.MOVING
            self._assign_destination(units[0], target_wx, target_wy)
            return

        slots = self._formation_slots(center_col, center_row, len(units))
        units_sorted = sorted(
            units,
            key=lambda u: (u.x - target_wx) ** 2 + (u.y - target_wy) ** 2)
        for i, u in enumerate(units_sorted):
            u.state = UnitState.MOVING
            if i < len(slots):
                c, r = slots[i]
                wx, wy = iso.tile_to_world(c, r)
            else:
                wx = target_wx + (i - len(units) * 0.5) * 6.0
                wy = target_wy + (i - len(units) * 0.5) * 6.0
            self._assign_destination(u, wx, wy)

    def issue_attack(self, units, target):
        if not units or target is None:
            return
        for u in units:
            u.cancel_task()
            u.set_attacking(target)

    def issue_attack_move(self, units, target_wx, target_wy):
        for u in units:
            u.cancel_task()
            u.attack_target = None
            nearest = combat.find_best_target(
                u, self.units, self.buildings.buildings, u.aggro_range)
            if nearest is not None:
                u.set_attacking(nearest)
            else:
                u.state = UnitState.MOVING
                self._assign_destination(u, target_wx, target_wy)

    def issue_gather(self, workers, node):
        if not workers or not node.is_resource() or not node.has_resources():
            return
        dropoff = self.buildings.find_nearest_dropoff(
            workers[0].x, workers[0].y, owner=workers[0].owner)
        if dropoff is None:
            return

        node_wx, node_wy = node.world_position()
        ring_r = C.WORKER_NODE_STANDOFF
        drop_r = C.WORKER_DROPOFF_STANDOFF
        n = len(workers)
        for i, w in enumerate(workers):
            angle = (2.0 * math.pi * i) / max(1, n)
            nx = node_wx + math.cos(angle) * ring_r
            ny = node_wy + math.sin(angle) * ring_r
            dx = dropoff.x + math.cos(angle) * drop_r
            dy = dropoff.y + math.sin(angle) * drop_r
            w.begin_gather_task(node, nx, ny, dropoff, dx, dy)
            self._assign_destination(w, nx, ny)

    def issue_build(self, workers, building):
        if not workers or building is None or building.complete:
            return
        for w in workers:
            if w.kind != WORKER:
                continue
            dx = w.x - building.x
            dy = w.y - building.y
            d = math.hypot(dx, dy) or 1.0
            standoff = max(building.fp_w, building.fp_h) * 30.0 + 12.0
            tx = building.x + dx / d * standoff
            ty = building.y + dy / d * standoff
            w.begin_build_task(building, tx, ty)
            self._assign_destination(w, tx, ty)

    def issue_stop(self, units):
        for u in units:
            u.cancel_task()
            u.set_idle()

    # ------------------------------------------------------------------
    # Population helpers
    # ------------------------------------------------------------------
    def total_population(self, owner=C.FACTION_PLAYER):
        total = 0
        for u in self.units:
            if u.dead:
                continue
            if u.owner != owner:
                continue
            total += UNIT_DEFS[u.kind]["pop_cost"]
        return total

    def can_train_more(self, unit_kind, buildings, owner=C.FACTION_PLAYER):
        cap = buildings.total_pop_capacity(owner)
        current = (self.total_population(owner)
                   + buildings.pop_cost_in_queue(owner))
        needed = UNIT_DEFS[unit_kind]["pop_cost"]
        return current + needed <= cap

    def can_train_more(self, unit_kind, buildings, owner=C.FACTION_PLAYER):
        cap = buildings.total_pop_capacity(owner)
        current = (self.total_population(owner)
                   + buildings.pop_cost_in_queue(owner))
        needed = UNIT_DEFS[unit_kind]["pop_cost"]
        return current + needed <= cap