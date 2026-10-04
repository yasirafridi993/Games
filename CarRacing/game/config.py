"""Central configuration: file paths and tuning constants."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
SOUNDS_DIR = ASSETS_DIR / "sounds"
TEXTURES_DIR = ASSETS_DIR / "textures"
MATERIALS_DIR = ASSETS_DIR / "materials"
MODELS_DIR = ASSETS_DIR / "models"
SKYBOXES_DIR = ASSETS_DIR / "skyboxes"
PARTICLES_DIR = ASSETS_DIR / "particles"
DATA_DIR = ROOT / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"

TOTAL_LAPS = 3
NUM_CHECKPOINTS = 12          # checkpoint 0 is the finish line
PHYSICS_DT = 1.0 / 120.0      # fixed simulation step (seconds)
DEFAULT_TRACK_ID = "harbor_run"

PLAYER_NAME = "You"
PLAYER_COLOR = (0.10, 0.35, 0.95)
PLAYER_GRID_SLOT = 2          # 0 = pole position

# Driver profiles tune AI behavior and preferred racing-line offset.
AI_PROFILES = [
    {"name": "Rex",  "corner": 0.97, "bias": -2.5},
    {"name": "Nova", "corner": 0.93, "bias": 2.5},
    {"name": "Bolt", "corner": 1.00, "bias": 0.0},
    {"name": "Echo", "corner": 0.96, "bias": -1.0},
    {"name": "Dash", "corner": 0.95, "bias": 1.0},
    {"name": "Mika", "corner": 0.98, "bias": -2.0},
    {"name": "Ace",  "corner": 0.94, "bias": 2.0},
]

AI_DIFFICULTIES = {
    "easy": {
        "aggression": 0.60,
        "mistake_interval": (18.0, 30.0), "mistake_duration": (0.8, 1.5),
    },
    "medium": {
        "aggression": 1.0,
        "mistake_interval": (55.0, 85.0), "mistake_duration": (0.3, 0.7),
    },
    "hard": {
        "aggression": 1.35,
        "mistake_interval": None, "mistake_duration": (0.0, 0.0),
    },
}
