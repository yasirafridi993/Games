"""HUD: resource bar, population, debug panel, selection, hints."""

import pygame

from . import config as C
from .building_defs import BUILDING_DEFS
from .resources import RESOURCE_ORDER, RESOURCE_NAMES, RESOURCE_COLORS
from .terrain import TILE_NAMES
from .tech import TECH_DEFS
from .unit_defs import UNIT_DEFS, WORKER


class Hud:
    def __init__(self, game):
        self.game = game
        self.font = pygame.font.SysFont("consolas,couriernew,monospace", 15)
        self.small = pygame.font.SysFont("consolas,couriernew,monospace", 13)
        self.title_font = pygame.font.SysFont(
            "consolas,couriernew,monospace", 22, bold=True)
        self.resource_font = pygame.font.SysFont(
            "consolas,couriernew,monospace", 17, bold=True)

    def draw(self, surface):
        self._draw_resource_bar(surface)
        self._draw_info_panel(surface)
        self._draw_selection_panel(surface)
        self._draw_hints(surface)

    # ------------------------------------------------------------------
    def _draw_resource_bar(self, surface):
        game = self.game
        sp = game.stockpile
        pop = game.units.total_population()
        cap = game.buildings.total_pop_capacity()
        pop_label = self.font.render("Population", True, (200, 210, 224))
        pop_val = self.resource_font.render(f"{pop} / {cap}", True,
                                            (238, 240, 246))

        cells = [(
            max(pop_label.get_width(), pop_val.get_width()) + 30,
            pop_label.get_height() + pop_val.get_height() + 12,
            (110, 200, 230), pop_label, pop_val,
        )]
        for r in RESOURCE_ORDER:
            label = RESOURCE_NAMES[r]
            amount = sp.get(r)
            color = RESOURCE_COLORS[r]
            name_s = self.font.render(label, True, color)
            amt_s = self.resource_font.render(f"{amount}", True,
                                              (238, 240, 246))
            cw = max(name_s.get_width(), amt_s.get_width()) + 30
            ch = name_s.get_height() + amt_s.get_height() + 12
            cells.append((cw, ch, color, name_s, amt_s))

        pad = 10
        total_w = sum(c[0] for c in cells) + pad * (len(cells) - 1)
        x = (surface.get_width() - total_w) // 2
        y = 12
        for cw, ch, color, name_s, amt_s in cells:
            panel = pygame.Surface((cw, ch), pygame.SRCALPHA)
            panel.fill((10, 12, 18, 190))
            pygame.draw.rect(panel, (92, 112, 142, 220),
                             panel.get_rect(), 1)
            pygame.draw.rect(panel, color, (6, 8, 10, ch - 16))
            pygame.draw.rect(panel, (0, 0, 0, 120), (6, 8, 10, ch - 16), 1)
            panel.blit(name_s, (22, 4))
            panel.blit(amt_s, (22, 4 + name_s.get_height()))
            surface.blit(panel, (x, y))
            x += cw + pad

    # ------------------------------------------------------------------
    def _draw_info_panel(self, surface):
        game = self.game
        cam = game.camera
        col, row = game.hovered_tile()
        world = game.world
        if world.in_bounds(col, row):
            t, _ = world.terrain.get(col, row)
            tile_name = TILE_NAMES.get(t, "?")
            blocked = game.pathfinder.grid.is_blocked(col, row)
        else:
            tile_name = "-"
            blocked = True

        queued = game.buildings.queued_unit_count()
        n_player = sum(1 for u in game.units.units
                       if not u.dead and u.owner == C.FACTION_PLAYER)
        n_enemy = sum(1 for u in game.units.units
                      if not u.dead and u.owner == C.FACTION_ENEMY)

        ts = game.tech_states.get(C.FACTION_PLAYER)
        b_atk = ts.bonuses["attack"] if ts else 0
        b_arm = ts.bonuses["armor"] if ts else 0
        b_spd = ts.bonuses["speed_mult"] if ts else 1.0
        b_gth = ts.bonuses["gather_rate_mult"] if ts else 1.0
        n_techs = len(ts.researched) if ts else 0

        ai = game.ai
        if ai is not None:
            ai_pop = game.units.total_population(C.FACTION_ENEMY)
            ai_cap = game.buildings.total_pop_capacity(C.FACTION_ENEMY)
            ai_line = (f"AI {ai.difficulty_name[:3].upper()} "
                       f"{ai.state[:4].upper()} {ai.phase[:4].upper()} "
                       f"{ai_pop}/{ai_cap}")
        else:
            ai_line = "AI  off"

        lines = [
            f"FPS        {game.clock.get_fps():5.1f}",
            f"Zoom       {cam.zoom:5.2f}x",
            f"Tile       {col:>4} , {row:>4}  {'BLK' if blocked else 'walk'}",
            f"Terrain    {tile_name}",
            f"Player     {n_player:>4} units   Enemy {n_enemy:>4}",
            f"Queued     {queued:>4}",
            f"Techs      {n_techs}  +{b_atk}a +{b_arm}ar "
            f"x{b_spd:.2f}spd x{b_gth:.2f}gth",
            ai_line,
        ]
        rendered = [self.font.render(t, True, (224, 232, 242)) for t in lines]
        w = max(s.get_width() for s in rendered) + 20
        h = sum(s.get_height() for s in rendered) + 16
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((10, 12, 18, 170))
        pygame.draw.rect(panel, (92, 112, 142, 200), panel.get_rect(), 1)
        y = 8
        for s in rendered:
            panel.blit(s, (10, y))
            y += s.get_height()
        surface.blit(panel, (10, 10))

    # ------------------------------------------------------------------
    def _draw_selection_panel(self, surface):
        game = self.game
        sel = game.units.selected
        sel_building = game.selected_building
        if not sel and sel_building is None:
            return

        lines = []
        if sel_building is not None and not sel:
            defn = BUILDING_DEFS[sel_building.kind]
            lines.append(defn["name"])
            lines.append(f"HP      {sel_building.hp}/{sel_building.max_hp}")
            if sel_building.complete:
                lines.append("Status  Complete")
            else:
                pct = int(sel_building.progress * 100)
                lines.append(f"Building {pct}%")
            if sel_building.queue is not None:
                qn = len(sel_building.queue.items)
                lines.append(f"Queue   {qn}/{sel_building.queue.max_size}")
            if sel_building.research_queue is not None:
                if sel_building.research_queue.items:
                    cur = sel_building.research_queue.items[0]
                    nm = TECH_DEFS[cur.key].name
                    pct = int(sel_building.research_queue.current_progress() * 100)
                    lines.append(f"Research {nm} {pct}%")
                else:
                    lines.append("Research idle")
        elif len(sel) == 1:
            u = sel[0]
            defn = UNIT_DEFS[u.kind]
            lines.append(defn["name"])
            lines.append(f"HP      {u.hp}/{u.max_hp}")
            lines.append(f"State   {u.state}")
            lines.append(f"Dmg {u.damage}  Arm {u.armor}")
            if u.kind == WORKER:
                lines.append(f"Carry   {u.carrying}/{u.carry_capacity}")
                lines.append(f"Gather  x{u.gather_rate_mult:.2f}")
            if u.attack_target is not None:
                try:
                    t_name = u.attack_target.kind
                except AttributeError:
                    t_name = "?"
                lines.append(f"Target  {t_name}")
        else:
            counts = {}
            for u in sel:
                counts[u.kind] = counts.get(u.kind, 0) + 1
            lines.append(f"{len(sel)} units selected")
            for k, n in sorted(counts.items()):
                lines.append(f"  {UNIT_DEFS[k]['name']:<10} x{n}")

        rendered = [self.font.render(t, True, (224, 232, 242)) for t in lines]
        w = max(s.get_width() for s in rendered) + 20
        h = sum(s.get_height() for s in rendered) + 16
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((10, 12, 18, 200))
        pygame.draw.rect(panel, (92, 112, 142, 220), panel.get_rect(), 1)
        y = 8
        for s in rendered:
            panel.blit(s, (10, y))
            y += s.get_height()
        surface.blit(panel, (10, surface.get_height() - h - 44))

    # ------------------------------------------------------------------
    def _draw_hints(self, surface):
        text = (
            "LMB: select / box  |  RMB: move / gather / build / attack / cancel-research  |  "
            "A: attack-move  |  H: stop  |  P: paths  |  G: grid  |  Esc: quit"
        )
        s = self.small.render(text, True, (198, 208, 224))
        pad = 8
        w = s.get_width() + pad * 2
        h = s.get_height() + pad
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((10, 12, 18, 150))
        panel.blit(s, (pad, pad // 2))
        surface.blit(panel, (10, surface.get_height() - h - 10))