"""Authored track data. Geometry is resampled and derived by TrackData."""
from dataclasses import dataclass

from .track import CONTROL_POINTS


@dataclass(frozen=True)
class TrackDefinition:
    track_id: str
    name: str
    description: str
    environment: str
    control_points: tuple
    width: float
    track_type: str
    weather: str = "day"
    checkpoint_count: int = 12
    grid_start_distance: float = 12.0
    grid_row_spacing: float = 10.0
    grid_lateral: float = 3.5


TRACKS = (
    TrackDefinition("harbor_run", "Harbor City Circuit",
                    "Wide urban roads, long straights and sharp technical junctions.",
                    "city", tuple(CONTROL_POINTS), 24.0, "City Circuit"),
    TrackDefinition("mountain_pass", "Mountain Pass",
                    "A narrow alpine route with climbing switchbacks and cliffside drops.",
                    "mountain", (
                        (-15, -250, 5), (100, -240, 10), (170, -190, 17), (95, -150, 25),
                        (-30, -130, 34), (-130, -95, 45), (-180, -25, 51), (-95, 5, 37),
                        (30, -15, 30), (145, 20, 35), (230, 80, 43), (280, 155, 52),
                        (240, 220, 58), (150, 255, 66), (40, 240, 58), (-70, 200, 45),
                        (-155, 230, 30), (-230, 160, 18), (-260, 60, 12), (-210, -25, 18),
                        (-235, -130, 15), (-160, -210, 9), (-75, -245, 5)),
                    13.0, "Mountain Pass"),
    TrackDefinition("desert_rally", "Sirocco Rally",
                    "Fast desert sweepers, open sandy shoulders and a sudden rocky hairpin.",
                    "desert", (
                        (-250, -70), (-175, -190), (15, -235), (210, -185), (280, -75),
                        (235, 40), (150, 85), (90, 155), (15, 205), (-100, 225),
                        (-215, 165), (-270, 65), (-195, 5), (-85, -10), (5, 45), (130, 30),
                        (190, -25), (95, -95), (-30, -125), (-155, -95)),
                    19.0, "Desert Rally"),
    TrackDefinition("forest_challenge", "Blackpine Forest",
                    "A narrow, foggy ribbon of asphalt with linked S-bends and blind corners.",
                    "forest", (
                        (-35, -250), (30, -220), (110, -235), (160, -185), (95, -140),
                        (10, -165), (-75, -130), (-110, -65), (-45, -25), (45, -60),
                        (125, -25), (105, 45), (15, 70), (-85, 45), (-155, 95),
                        (-105, 165), (-5, 145), (80, 205), (35, 255), (-75, 225),
                        (-175, 250), (-235, 185), (-205, 100), (-255, 15), (-205, -75),
                        (-130, -165), (-105, -235)),
                    12.0, "Forest Challenge", "rain"),
    TrackDefinition("coastal_highway", "Azure Coast Highway",
                    "A broad ocean highway of fast curves, cliff roads and a raised bridge.",
                    "coastal", (
                        (-270, -140, 0), (-165, -205, 2), (-20, -230, 3), (140, -205, 4),
                        (255, -145, 7), (305, -45, 12), (295, 70, 18), (350, 160, 22),
                        (305, 245, 23), (195, 275, 20), (55, 270, 15), (-95, 230, 10),
                        (-205, 165, 8), (-280, 75, 9), (-300, -30, 6), (-280, -100, 2)),
                    22.0, "Coastal Highway"),
    TrackDefinition("industrial_circuit", "Foundry Loop",
                    "Tight warehouse alleys, short straights and repeated heavy braking zones.",
                    "industrial", (
                        (-155, -150), (-30, -150), (-5, -115), (105, -115), (125, -150),
                        (235, -150), (235, -40), (165, -25), (165, 55), (235, 75),
                        (235, 165), (105, 165), (85, 105), (5, 105), (-10, 165),
                        (-155, 165), (-155, 65), (-75, 45), (-75, -20), (-155, -35)),
                    14.0, "Industrial Circuit"),
    TrackDefinition("neon_city", "Neon Afterdark",
                    "A compact night-city route of close walls, chicanes and short bursts.",
                    "neon_city", (
                        (-145, -125), (-20, -125), (5, -85), (110, -85), (145, -120),
                        (205, -75), (165, -15), (75, -5), (50, 40), (175, 65),
                        (190, 135), (65, 150), (20, 105), (-70, 125), (-155, 85),
                        (-120, 25), (-35, 10), (-5, -35), (-145, -55)),
                    15.0, "Night Neon City", "night"),
    TrackDefinition("extreme_mountain", "Razorback Extreme",
                    "A narrow expert course combining cliff bridges, steep climbs and brutal hairpins.",
                    "extreme_mountain", (
                        (-40, -285, 8), (80, -260, 16), (170, -205, 27), (105, -155, 42),
                        (-15, -170, 58), (-125, -125, 65), (-185, -55, 50), (-105, -10, 38),
                        (15, -35, 49), (130, 5, 67), (200, 85, 81), (290, 150, 73),
                        (310, 220, 59), (220, 270, 45), (95, 260, 31), (-30, 220, 20),
                        (-150, 245, 12), (-240, 170, 22), (-300, 70, 35), (-265, -20, 25),
                        (-210, -100, 18), (-270, -185, 14), (-160, -245, 9)),
                    10.5, "Extreme Mountain", "sunset"),
)

TRACK_BY_ID = {definition.track_id: definition for definition in TRACKS}
