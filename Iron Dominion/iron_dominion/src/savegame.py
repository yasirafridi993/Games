"""Save / load system for multi-faction matches."""

import json
import os
import time

from . import config as C
from .buildings import Building
from .missions import MISSION_LIBRARY
from .tech import TechState
from .units import Unit, WorkerTask, BuildTask


SAVE_VERSION = 2
MAX_SLOTS = 8
SAVE_DIRNAME = "saves"


def _save_dir():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, SAVE_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def slot_path(slot):
    return os.path.join(_save_dir(), f"slot_{int(slot)}.json")


def slot_exists(slot):
    return os.path.isfile(slot_path(slot))


def delete_slot(slot):
    p = slot_path(slot)
    if os.path.isfile(p):
        os.remove(p)


def list_slots():
    out = []
    for i in range(1, MAX_SLOTS + 1):
        p = slot_path(i)
        if not os.path.isfile(p):
            out.append(None); continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("meta", {})
            out.append({
                "slot": i,
                "mission_key": meta.get("mission_key", "?"),
                "mission_name": meta.get("mission_name", "?"),
                "difficulty": meta.get("difficulty", "?"),
                "num_enemies": meta.get("num_enemies", 1),
                "team_mode": meta.get("team_mode", "ffa"),
                "elapsed": float(meta.get("elapsed", 0.0)),
                "saved_at": float(data.get("saved_at", 0.0)),
                "corrupt": False,
            })
        except Exception:
            out.append({"slot": i, "mission_key": "?", "mission_name": "(corrupt)",
                        "difficulty": "?", "num_enemies": 0, "team_mode": "?",
                        "elapsed": 0.0, "saved_at": 0.0, "corrupt": True})
    return out


# ---------------------------------------------------------------------------
def _prop_to_dict(p):
    return {
        "kind": int(p.kind), "col": int(p.col), "row": int(p.row),
        "ox": float(p.ox), "oy": float(p.oy), "variant": int(p.variant),
        "amount": int(p.amount), "max_amount": int(p.max_amount),
        "alive": bool(p.alive),
    }


def _prop_from_dict(data):
    from .props import Prop
    p = Prop(data["kind"], data["col"], data["row"],
             data["ox"], data["oy"], data["variant"])
    p.amount = int(data.get("amount", p.amount))
    p.max_amount = int(data.get("max_amount", p.max_amount))
    p.alive = bool(data.get("alive", True))
    return p


def _building_to_dict(b):
    queue = []
    if b.queue is not None:
        for it in b.queue.items:
            queue.append({"unit_kind": it.unit_kind,
                          "time_total": float(it.time_total),
                          "time_left": float(it.time_left)})
    rq = []
    if b.research_queue is not None:
        for it in b.research_queue.items:
            rq.append({"key": it.key,
                       "time_total": float(it.time_total),
                       "time_left": float(it.time_left)})
    return {
        "kind": b.kind, "col": int(b.col), "row": int(b.row),
        "owner": int(b.owner), "hp": int(b.hp), "max_hp": int(b.max_hp),
        "complete": bool(b.complete), "progress": float(b.progress),
        "build_work": float(b.build_work),
        "queue": queue, "research_queue": rq,
        "food_reserve": float(getattr(b, "food_reserve", 0.0)),
        "food_max": float(getattr(b, "food_max", 0.0)),
        "food_regen": float(getattr(b, "food_regen", 0.0)),
    }


def _building_from_dict(data, world):
    b = Building(data["kind"], data["col"], data["row"], world=world,
                 owner=data["owner"])
    b.hp = int(data.get("hp", b.max_hp))
    b.max_hp = int(data.get("max_hp", b.max_hp))
    b.complete = bool(data.get("complete", True))
    b.progress = float(data.get("progress", 1.0))
    b.build_work = float(data.get("build_work", 0.0))
    if b.kind == "farm":
        b.food_reserve = float(data.get("food_reserve", 500.0))
        b.food_max = float(data.get("food_max", 500.0))
        b.food_regen = float(data.get("food_regen", 4.0))
    if b.queue is not None:
        b.queue.items.clear()
        from .production import ProductionItem
        for qd in data.get("queue", []):
            it = ProductionItem(qd["unit_kind"])
            it.time_total = float(qd.get("time_total", it.time_total))
            it.time_left = float(qd.get("time_left", it.time_total))
            b.queue.items.append(it)
    if b.research_queue is not None:
        from .tech import TechItem
        b.research_queue.items.clear()
        for rd in data.get("research_queue", []):
            it = TechItem(rd["key"])
            it.time_total = float(rd.get("time_total", it.time_total))
            it.time_left = float(rd.get("time_left", it.time_total))
            b.research_queue.items.append(it)
    return b


def _unit_to_dict(u, unit_index, building_index, prop_index):
    target = None
    if u.attack_target is not None:
        if isinstance(u.attack_target, Unit):
            idx = unit_index.get(id(u.attack_target))
            if idx is not None:
                target = ["unit", idx]
        else:
            idx = building_index.get(id(u.attack_target))
            if idx is not None:
                target = ["building", idx]

    task = None
    if u.task is not None:
        if isinstance(u.task, WorkerTask):
            task = {"type": "worker",
                    "node_idx": prop_index.get(id(u.task.node))
                                if u.task.node is not None else None,
                    "drop_idx": building_index.get(id(u.task.dropoff))
                                if u.task.dropoff is not None else None,
                    "node_wx": float(u.task.node_wx),
                    "node_wy": float(u.task.node_wy),
                    "drop_wx": float(u.task.drop_wx),
                    "drop_wy": float(u.task.drop_wy),
                    "mode": u.task.mode,
                    "timer": float(u.task.timer)}
        elif isinstance(u.task, BuildTask):
            task = {"type": "build",
                    "building_idx": building_index.get(id(u.task.building))
                                    if u.task.building is not None else None,
                    "stand_x": float(u.task.stand_x),
                    "stand_y": float(u.task.stand_y)}

    return {
        "kind": u.kind, "x": float(u.x), "y": float(u.y),
        "hp": int(u.hp), "max_hp": int(u.max_hp),
        "owner": int(u.owner), "state": u.state, "facing": int(u.facing),
        "path": [[float(a), float(b)] for a, b in u.path],
        "anim_state": u.anim_state, "anim_timer": float(u.anim_timer),
        "anim_phase": int(u.anim_phase), "selected": bool(u.selected),
        "attack_timer": float(u.attack_timer),
        "attack_repath_timer": float(u.attack_repath_timer),
        "hit_flash": float(u.hit_flash),
        "carrying": int(u.carrying), "carrying_type": u.carrying_type,
        "gather_buffer": float(u.gather_buffer),
        "attack_target": target, "task": task,
    }


def _unit_from_dict(data, tech_state):
    u = Unit(data["kind"], data["x"], data["y"], owner=data["owner"])
    u.hp = int(data.get("hp", u.max_hp))
    u.max_hp = int(data.get("max_hp", u.max_hp))
    u.state = data.get("state", "idle")
    u.facing = int(data.get("facing", 0))
    u.path = [(float(p[0]), float(p[1])) for p in data.get("path", [])]
    u.anim_state = data.get("anim_state", "idle")
    u.anim_timer = float(data.get("anim_timer", 0.0))
    u.anim_phase = int(data.get("anim_phase", 0))
    u.selected = bool(data.get("selected", False))
    u.attack_timer = float(data.get("attack_timer", 0.0))
    u.attack_repath_timer = float(data.get("attack_repath_timer", 0.0))
    u.hit_flash = float(data.get("hit_flash", 0.0))
    u.carrying = int(data.get("carrying", 0))
    u.carrying_type = data.get("carrying_type", None)
    u.gather_buffer = float(data.get("gather_buffer", 0.0))
    if tech_state is not None:
        u.apply_tech(tech_state)
        u.hp = int(data.get("hp", u.max_hp))
    return u


def _resolve_unit_refs(u, data, units, buildings, props):
    at = data.get("attack_target")
    if at is not None:
        kind, idx = at
        if kind == "unit" and 0 <= idx < len(units):
            u.attack_target = units[idx]
        elif kind == "building" and 0 <= idx < len(buildings):
            u.attack_target = buildings[idx]

    td = data.get("task")
    if td is None:
        u.task = None; return
    if td["type"] == "worker":
        node = props[td["node_idx"]] if td.get("node_idx") is not None \
            and 0 <= td["node_idx"] < len(props) else None
        drop = buildings[td["drop_idx"]] if td.get("drop_idx") is not None \
            and 0 <= td["drop_idx"] < len(buildings) else None
        task = WorkerTask(node, td["node_wx"], td["node_wy"],
                          drop, td["drop_wx"], td["drop_wy"])
        task.mode = td.get("mode", WorkerTask.MODE_TO_NODE)
        task.timer = float(td.get("timer", 0.0))
        u.task = task
    elif td["type"] == "build":
        b = buildings[td["building_idx"]] \
            if td.get("building_idx") is not None \
            and 0 <= td["building_idx"] < len(buildings) else None
        u.task = BuildTask(b, td["stand_x"], td["stand_y"])


def _objective_to_dict(obj):
    cls = type(obj).__name__
    d = {"class": cls, "complete": bool(obj.complete)}
    if cls == "EliminateFaction": d["owner"] = int(obj.owner)
    elif cls == "DestroyTownCenter": d["owner"] = int(obj.owner)
    elif cls == "KillUnits":
        d["owner"] = int(obj.owner); d["target"] = int(obj.target)
    elif cls == "GatherResource":
        d["resource"] = obj.resource; d["amount"] = int(obj.amount)
    elif cls == "Survive":
        d["duration"] = float(obj.duration); d["elapsed"] = float(obj.elapsed)
    elif cls == "ControlArea":
        d["col"] = int(obj.col); d["row"] = int(obj.row)
        d["radius_tiles"] = int(obj.radius_tiles)
        d["duration"] = float(obj.duration); d["held"] = float(obj.held)
    elif cls == "_EliminateAll":
        d["enemies"] = list(obj.enemies)
    return d


def _objective_from_dict(data):
    cls = data["class"]
    from . import missions as M
    try:
        if cls == "EliminateFaction":
            obj = M.EliminateFaction(data.get("owner", 1))
        elif cls == "DestroyTownCenter":
            obj = M.DestroyTownCenter(data.get("owner", 1))
        elif cls == "KillUnits":
            obj = M.KillUnits(data["target"], data.get("owner", 1))
        elif cls == "GatherResource":
            obj = M.GatherResource(data["resource"], data["amount"])
        elif cls == "Survive":
            obj = M.Survive(data["duration"])
            obj.elapsed = float(data.get("elapsed", 0.0))
        elif cls == "ControlArea":
            obj = M.ControlArea(data["col"], data["row"],
                                data["radius_tiles"], data["duration"])
            obj.held = float(data.get("held", 0.0))
        elif cls == "_EliminateAll":
            from .missions import Objective
            enemies = list(data.get("enemies", [1]))

            class _Elim(M.Objective):
                def __init__(self, enemies):
                    super().__init__()
                    self.enemies = enemies
                    self.text = "Eliminate all enemy factions"

                def update(self, g, d):
                    if self.complete:
                        return
                    for f in self.enemies:
                        if any(b.alive and b.owner == f
                               for b in g.buildings.buildings):
                            return
                        if any(not u.dead and u.owner == f
                               for u in g.units.units):
                            return
                    self.complete = True

            obj = _Elim(enemies)
        else:
            return None
    except Exception:
        return None
    obj.complete = bool(data.get("complete", False))
    return obj


def _ai_to_dict(ai):
    if ai is None:
        return None
    return {
        "difficulty_name": ai.difficulty_name,
        "home_col": int(ai.home_col), "home_row": int(ai.home_row),
        "home_wx": float(ai.home_wx), "home_wy": float(ai.home_wy),
        "phase": ai.phase, "state": ai.state,
        "decision_timer": float(ai.decision_timer),
        "build_delay_timer": float(ai.build_delay_timer),
        "scout_timer": float(ai.scout_timer),
        "remembered_enemy_positions":
            [[float(p[0]), float(p[1])]
             for p in ai.remembered_enemy_positions],
    }


def _ai_load_into(ai, data):
    if ai is None or data is None:
        return
    ai.home_col = int(data.get("home_col", ai.home_col))
    ai.home_row = int(data.get("home_row", ai.home_row))
    ai.home_wx = float(data.get("home_wx", ai.home_wx))
    ai.home_wy = float(data.get("home_wy", ai.home_wy))
    ai.phase = data.get("phase", ai.phase)
    ai.state = data.get("state", ai.state)
    ai.decision_timer = float(data.get("decision_timer", ai.decision_timer))
    ai.build_delay_timer = float(data.get("build_delay_timer",
                                          ai.build_delay_timer))
    ai.scout_timer = float(data.get("scout_timer", ai.scout_timer))
    ai.remembered_enemy_positions = [
        (float(p[0]), float(p[1]))
        for p in data.get("remembered_enemy_positions", [])]
    ai.known_enemy_units = []
    ai.known_enemy_buildings = []


def _fog_to_dict(fog):
    out = {}
    for faction, grid in fog._explored.items():
        out[str(faction)] = {"explored":
            [[1 if v else 0 for v in row] for row in grid]}
    return out


def _fog_load_into(fog, data):
    for k, d in data.items():
        try:
            faction = int(k)
        except ValueError:
            continue
        grid = d.get("explored")
        if not grid:
            continue
        fog.register_faction(faction)
        for r, row in enumerate(grid):
            if r >= fog.rows:
                break
            target = fog._explored[faction][r]
            for c, v in enumerate(row):
                if c >= fog.cols:
                    break
                target[c] = bool(v)


def _tech_to_dict(ts):
    return {"researched": list(ts.researched),
            "bonuses": dict(ts.bonuses)}


def _tech_load_into(ts, data):
    ts.researched = set(data.get("researched", []))
    for k, v in data.get("bonuses", {}).items():
        ts.bonuses[k] = v


# ---------------------------------------------------------------------------
def save_game(game, slot):
    prop_idx = {id(p): i for i, p in enumerate(game.world.props)}
    b_idx = {id(b): i for i, b in enumerate(game.buildings.buildings)}
    u_idx = {id(u): i for i, u in enumerate(game.units.units)}

    data = {
        "version": SAVE_VERSION,
        "saved_at": time.time(),
        "meta": {
            "mission_key": game.mission.key,
            "mission_name": game.mission.name,
            "difficulty": game.mission.enemy_difficulty,
            "num_enemies": game.match_config.num_enemies,
            "team_mode": game.match_config.team_mode,
            "elapsed": float(game.mission_elapsed),
        },
        "mission": {
            "key": game.mission.key,
            "elapsed": float(game.mission_elapsed),
            "state": game.mission_state,
            "banner_timer": float(game.mission_banner_timer),
            "difficulty": game.mission.enemy_difficulty,
        },
        "match_config": {
            "num_enemies": game.match_config.num_enemies,
            "team_mode": game.match_config.team_mode,
        },
        "world": {"seed": int(game.world.seed),
                  "cols": int(game.world.cols),
                  "rows": int(game.world.rows)},
        "camera": {"x": float(game.camera.x),
                   "y": float(game.camera.y),
                   "zoom": float(game.camera.zoom)},
        "stockpiles": {str(f): dict(sp.amounts)
                       for f, sp in game.stockpiles.items()},
        "tech_states": {str(f): _tech_to_dict(ts)
                        for f, ts in game.tech_states.items()},
        "props": [_prop_to_dict(p) for p in game.world.props],
        "buildings": [_building_to_dict(b)
                      for b in game.buildings.buildings],
        "units": [_unit_to_dict(u, u_idx, b_idx, prop_idx)
                  for u in game.units.units],
        "objectives": [_objective_to_dict(o) for o in game.objectives],
        "ai": {str(f): _ai_to_dict(ai) for f, ai in game.ais.items()},
        "fog": _fog_to_dict(game.fog),
        "deaths_by_faction": {str(f): int(n)
                              for f, n in game.units.deaths_by_faction.items()},
    }
    try:
        with open(slot_path(slot), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, separators=(",", ": "))
    except Exception as e:
        return False, f"Failed to save: {e}"
    return True, "Game saved."


def load_game_data(slot):
    with open(slot_path(slot), "r", encoding="utf-8") as f:
        data = json.load(f)
    v = int(data.get("version", 0))
    if v > SAVE_VERSION:
        raise ValueError(f"Save version {v} is newer than {SAVE_VERSION}")
    return data


def apply_loaded_state(game, data):
    # Props
    game.world.props.clear()
    game.world.props_by_diag.clear()
    for pd in data.get("props", []):
        game.world.props.append(_prop_from_dict(pd))
    game.world._group_props()

    # Buildings
    game.buildings.buildings.clear()
    for bd in data.get("buildings", []):
        b = _building_from_dict(bd, game.world)
        game.buildings.add(b)

    # Units
    game.units.units.clear()
    game.units.selected.clear()
    for ud in data.get("units", []):
        ts = game.tech_states.get(int(ud.get("owner", 0)))
        u = _unit_from_dict(ud, ts)
        game.units.units.append(u)
    for i, ud in enumerate(data.get("units", [])):
        _resolve_unit_refs(game.units.units[i], ud,
                           game.units.units,
                           game.buildings.buildings,
                           game.world.props)
    for u in game.units.units:
        if u.selected:
            game.units.selected.append(u)

    # Stockpiles
    for k, amounts in data.get("stockpiles", {}).items():
        f = int(k)
        sp = game.stockpiles.get(f)
        if sp is not None:
            sp.amounts = dict(amounts)

    # Tech
    for k, td in data.get("tech_states", {}).items():
        f = int(k)
        ts = game.tech_states.get(f)
        if ts is not None:
            _tech_load_into(ts, td)

    # Fog
    if "fog" in data:
        _fog_load_into(game.fog, data["fog"])

    # Mission state
    m = data.get("mission", {})
    game.mission_elapsed = float(m.get("elapsed", 0.0))
    game.mission_state = m.get("state", "in_progress")
    game.mission_banner_timer = float(m.get("banner_timer", 0.0))

    # Camera
    cam = data.get("camera", {})
    game.camera.x = float(cam.get("x", game.camera.x))
    game.camera.y = float(cam.get("y", game.camera.y))
    game.camera.zoom = float(cam.get("zoom", game.camera.zoom))
    game.camera.vel_x = 0.0
    game.camera.vel_y = 0.0
    game.camera.clamp()

    # Deaths
    for k, n in data.get("deaths_by_faction", {}).items():
        game.units.deaths_by_faction[int(k)] = int(n)

    # Grid rebuild
    game.pathfinder.refresh()
    # Fog reveal
    for f in game.factions.factions():
        game.fog.update(f, game.units, game.buildings)
    game.units._rebuild_diagonals()