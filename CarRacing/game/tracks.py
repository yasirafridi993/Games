"""Track manager: validate catalog entries and build only the selected layout."""
from .config import DEFAULT_TRACK_ID
from .track import CONTROL_POINTS as CONTROL_POINTS
from .track import TrackData
from .track_catalog import TRACKS, TRACK_BY_ID, TrackDefinition as TrackDefinition


class TrackManager:
    """Catalog-backed factory; procedural geometry is built on demand."""

    definitions = TRACKS
    by_id = TRACK_BY_ID

    @classmethod
    def get(cls, track_id):
        try:
            return cls.by_id[track_id]
        except KeyError:
            raise ValueError("Unknown track: %s" % track_id)

    @classmethod
    def build(cls, track_id=DEFAULT_TRACK_ID):
        definition = cls.get(track_id)
        track = TrackData(
            control_points=definition.control_points,
            width=definition.width,
            num_checkpoints=definition.checkpoint_count,
            grid_start_distance=definition.grid_start_distance,
            grid_row_spacing=definition.grid_row_spacing,
            grid_lateral=definition.grid_lateral)
        curvature = sorted(abs(value) for value in track.kappa)
        p98 = curvature[int(0.98 * (len(curvature) - 1))]
        tight_fraction = sum(value > 0.025 for value in curvature) / len(curvature)
        narrow_factor = max(0.0, min(1.0, (20.0 - track.width) / 12.0))
        elevation_factor = max(0.0, track.max_elevation - track.min_elevation) / 60.0
        difficulty_score = (narrow_factor * 0.55 + elevation_factor * 0.80
                            + p98 / 0.04 * 0.75 + tight_fraction * 0.35)
        track.difficulty = (1 if difficulty_score < 0.5 else
                            2 if difficulty_score < 1.1 else
                            3 if difficulty_score < 1.9 else 4)
        track.track_id = definition.track_id
        track.name = definition.name
        track.description = definition.description
        track.environment = definition.environment
        track.track_type = definition.track_type
        track.preferred_weather = definition.weather
        return track


def track_definition(track_id):
    return TrackManager.get(track_id)


def build_track(track_id=DEFAULT_TRACK_ID):
    return TrackManager.build(track_id)
