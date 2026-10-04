"""Checkpoint / lap validation (pure Python).

Checkpoints are gates across the track at fixed arc-length positions.  Gate 0
is the finish line.  A car must pass gates 1, 2, ... N-1 in order and then the
finish line before a lap counts, so shortcuts and reversing over the line
cannot create false laps.
"""


def wrap_delta(d, length):
    return (d + length / 2.0) % length - length / 2.0


class CheckpointTracker:
    def __init__(self, track, total_laps, start_s):
        self.gates = track.checkpoint_s
        self.length = track.length
        self.total_laps = total_laps
        self.next_cp = 1               # the start/finish line is not required at the start
        self.laps_done = 0
        self.finished = False
        self.prev_s = start_s
        # distance travelled along the track, relative to the start line (< 0 on the grid)
        self.progress = wrap_delta(start_s, self.length)

    @property
    def lap(self):
        return min(self.laps_done + 1, self.total_laps)

    def update(self, s):
        """Feed the car's arc-length position. Returns a list of events."""
        events = []
        delta = wrap_delta(s - self.prev_s, self.length)
        if delta > 0.0 and not self.finished:
            gate = self.gates[self.next_cp]
            gap = (gate - self.prev_s) % self.length
            if 0.0 < gap <= delta:
                if self.next_cp == 0:
                    self.laps_done += 1
                    if self.laps_done >= self.total_laps:
                        self.finished = True
                        events.append("finish")
                    else:
                        events.append("lap")
                        self.next_cp = 1
                else:
                    events.append("checkpoint")
                    self.next_cp = (self.next_cp + 1) % len(self.gates)
        self.prev_s = s
        self.progress += delta
        return events

    def last_gate_s(self):
        return self.gates[(self.next_cp - 1) % len(self.gates)]

    def teleport(self, s, to_last_gate=False):
        """Move the reference position after a respawn without crossing gates."""
        if to_last_gate:
            s = self.last_gate_s()
            self.progress = self.laps_done * self.length + s
        else:
            self.progress += wrap_delta(s - self.prev_s, self.length)
        self.prev_s = s
