"""Local race and best-time records stored in data/progression.json."""
import json
import math

from .config import DATA_DIR

PROGRESSION_FILE = DATA_DIR / "progression.json"


class ProgressionStore:
    def __init__(self, path=PROGRESSION_FILE):
        self.path = path
        self.data = {"completed_races": 0, "tracks": {}}
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as stream:
                data = json.load(stream)
        except FileNotFoundError:
            return
        except (OSError, ValueError, TypeError) as exc:
            print("Could not load race progression:", exc)
            return
        if isinstance(data, dict):
            tracks = data.get("tracks", {})
            if isinstance(tracks, dict):
                self.data["tracks"] = tracks
            try:
                self.data["completed_races"] = max(0, int(data.get("completed_races", 0)))
            except (ValueError, TypeError):
                print("Invalid completed-race count in progression file; using zero.")

    def track_record(self, track_id):
        record = self.data["tracks"].get(track_id, {})
        if not isinstance(record, dict):
            return {}
        for key in ("best_time", "best_lap"):
            value = record.get(key)
            if value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                print("Invalid %s value in progression record for %s." % (key, track_id))
                record[key] = None
                continue
            record[key] = value if math.isfinite(value) else None
        return record

    def record_race(self, track_id, race_time, best_lap, won):
        record = self.track_record(track_id)
        if not record:
            self.data["tracks"][track_id] = record
        try:
            record["completed_races"] = max(0, int(record.get("completed_races", 0))) + 1
            record["wins"] = max(0, int(record.get("wins", 0)))
        except (ValueError, TypeError):
            print("Invalid track progression record for %s; resetting counters." % track_id)
            record.update({"completed_races": 1, "wins": 0})
        self.data["completed_races"] += 1
        if won:
            record["wins"] = int(record.get("wins", 0)) + 1
        self._update_best(record, "best_time", race_time)
        self._update_best(record, "best_lap", best_lap)
        self.save()

    @staticmethod
    def _update_best(record, key, candidate):
        if candidate is None:
            return
        try:
            candidate = float(candidate)
        except (TypeError, ValueError):
            print("Invalid %s value in race result; skipping record." % key)
            return
        current = record.get(key)
        try:
            current = float(current) if current is not None else None
        except (TypeError, ValueError):
            current = None
        if not math.isfinite(candidate) or (current is not None and not math.isfinite(current)):
            return
        if current is None or candidate < current:
            record[key] = round(candidate, 3)

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as stream:
                json.dump(self.data, stream, indent=2)
        except OSError as exc:
            print("Could not save race progression:", exc)
