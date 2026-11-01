"""Iron Dominion - entry point.

Top-level scene loop:

    MainMenu  ->  NewGameMenu  ->  Game
       ^              |             |
       |              v             v
       +-- back / main_menu --------+

    MainMenu  ->  LoadBrowser  ->  Game

Optional CLI shortcuts:
    python main.py skirmish [medium] [num_enemies] [team_mode]
    python main.py --load 1
"""

import sys

import pygame

from src import config as C
from src import savegame
from src.game import Game
from src.main_menu import MainMenu
from src.match_config import MatchConfig
from src.missions import MISSION_LIBRARY, MISSION_ORDER
from src.new_game_menu import NewGameMenu
from src.slot_browser import SlotBrowser


def _pick_next(current_key):
    try:
        i = MISSION_ORDER.index(current_key)
    except ValueError:
        i = -1
    return MISSION_ORDER[(i + 1) % len(MISSION_ORDER)]


def _make_window():
    pygame.init()
    pygame.font.init()
    pygame.display.set_caption(C.WINDOW_TITLE)
    return pygame.display.set_mode(
        (C.WINDOW_WIDTH, C.WINDOW_HEIGHT),
        pygame.RESIZABLE | pygame.DOUBLEBUF)


# ---------------------------------------------------------------------------
# In-game loop with save/load integration
# ---------------------------------------------------------------------------
def _play_game(screen, game):
    """Run a match until it ends. Returns a directive for the caller:
    'quit' | 'restart' | 'next_mission' | 'main_menu' | ('load', slot)"""
    while True:
        action = game.run()

        if action == "quit":
            return "quit"
        if action == "restart":
            return "restart"
        if action == "next_mission":
            return "next_mission"
        if action == "main_menu":
            return "main_menu"
        if action == "quickload":
            if savegame.slot_exists(1):
                return ("load", 1)
            continue

        # Pause menu asked for the save browser
        if getattr(game, "_open_save_browser", False):
            game._open_save_browser = False
            result = SlotBrowser(screen, mode="save").run()
            if result[0] == "slot":
                game.save(result[1])
            game.paused = False
            game.running = True
            continue

        return "quit"


# ---------------------------------------------------------------------------
def main():
    screen = _make_window()

    # -------------------- CLI: --load ----------------------------------
    if len(sys.argv) > 1 and sys.argv[1] == "--load":
        slot = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        if not savegame.slot_exists(slot):
            print(f"No save in slot {slot}.")
            pygame.quit()
            return
        try:
            data = savegame.load_game_data(slot)
        except Exception as e:
            print(f"Failed to load slot {slot}: {e}")
            pygame.quit()
            return
        game = Game(screen, saved_state=data)
        _play_game(screen, game)
        pygame.quit()
        return

    # -------------------- CLI: direct mission --------------------------
    if len(sys.argv) > 1 and sys.argv[1] in MISSION_LIBRARY:
        mission = sys.argv[1]
        difficulty = sys.argv[2] if len(sys.argv) > 2 else None
        try:
            num_enemies = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        except ValueError:
            num_enemies = 1
        team_mode = sys.argv[4] if len(sys.argv) > 4 else "ffa"
        mc = MatchConfig(num_enemies=num_enemies, team_mode=team_mode)
        game = Game(screen, mission_key=mission, difficulty=difficulty,
                    match_config=mc)
        _play_game(screen, game)
        pygame.quit()
        return

    # -------------------- Scene loop -----------------------------------
    scene = "main_menu"
    last_mission = "skirmish"
    last_difficulty = "medium"
    last_num_enemies = 1
    last_team_mode = "ffa"

    while True:
        if scene == "main_menu":
            result = MainMenu(screen).run()
            if result[0] == "quit":
                break
            if result[0] == "new_game":
                scene = "new_game_menu"
            elif result[0] == "load_game":
                scene = "load_browser"

        elif scene == "new_game_menu":
            result = NewGameMenu(screen).run()
            if result[0] == "back":
                scene = "main_menu"
            elif result[0] == "start":
                _, (last_mission, last_difficulty,
                    last_num_enemies, last_team_mode) = result
                scene = "in_game"

        elif scene == "load_browser":
            result = SlotBrowser(screen, mode="load").run()
            if result[0] == "cancel":
                scene = "main_menu"
            elif result[0] == "slot":
                slot = result[1]
                try:
                    data = savegame.load_game_data(slot)
                except Exception as e:
                    print(f"Failed to load slot {slot}: {e}")
                    scene = "main_menu"
                    continue
                game = Game(screen, saved_state=data)
                action = _play_game(screen, game)
                if action == "quit":
                    break
                elif action == "main_menu":
                    scene = "main_menu"
                elif action == "restart":
                    last_mission = game.mission.key
                    last_difficulty = game.mission.enemy_difficulty
                    last_num_enemies = game.match_config.num_enemies
                    last_team_mode = game.match_config.team_mode
                    scene = "in_game"
                elif action == "next_mission":
                    last_mission = _pick_next(game.mission.key)
                    last_difficulty = game.mission.enemy_difficulty
                    last_num_enemies = game.match_config.num_enemies
                    last_team_mode = game.match_config.team_mode
                    scene = "in_game"
                elif isinstance(action, tuple) and action[0] == "load":
                    try:
                        data = savegame.load_game_data(action[1])
                    except Exception as e:
                        print(f"Failed to load: {e}")
                        scene = "main_menu"
                        continue
                    game2 = Game(screen, saved_state=data)
                    action2 = _play_game(screen, game2)
                    if action2 == "quit":
                        break
                    scene = "main_menu"
                else:
                    scene = "main_menu"

        elif scene == "in_game":
            mc = MatchConfig(num_enemies=last_num_enemies,
                             team_mode=last_team_mode)
            game = Game(screen, mission_key=last_mission,
                        difficulty=last_difficulty, match_config=mc)
            action = _play_game(screen, game)

            if action == "quit":
                break
            elif action == "main_menu":
                scene = "main_menu"
            elif action == "restart":
                scene = "in_game"
            elif action == "next_mission":
                last_mission = _pick_next(last_mission)
                scene = "in_game"
            elif isinstance(action, tuple) and action[0] == "load":
                try:
                    data = savegame.load_game_data(action[1])
                except Exception as e:
                    print(f"Failed to load: {e}")
                    scene = "main_menu"
                    continue
                game2 = Game(screen, saved_state=data)
                action2 = _play_game(screen, game2)
                if action2 == "quit":
                    break
                elif action2 == "main_menu":
                    scene = "main_menu"
                elif action2 == "restart":
                    last_mission = game2.mission.key
                    last_difficulty = game2.mission.enemy_difficulty
                    last_num_enemies = game2.match_config.num_enemies
                    last_team_mode = game2.match_config.team_mode
                    scene = "in_game"
                elif action2 == "next_mission":
                    last_mission = _pick_next(game2.mission.key)
                    last_difficulty = game2.mission.enemy_difficulty
                    last_num_enemies = game2.match_config.num_enemies
                    last_team_mode = game2.match_config.team_mode
                    scene = "in_game"
                else:
                    scene = "main_menu"
            else:
                scene = "main_menu"

    pygame.quit()


if __name__ == "__main__":
    main()