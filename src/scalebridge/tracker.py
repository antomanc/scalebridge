"""Collapse the stream of readings into one result per weigh-in.

Scales repeat the same final value for minutes after you step off, and some send the
weight before the impedance. The tracker opens a session on the first stable reading,
closes it when a decoder marks a reading complete (or after `settle`), and then ignores
repeats of that value until the scale starts a new measurement. A result that is only ever
seen after the person stepped off is a leftover from an earlier weigh-in and is ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from scalebridge.models import Reading


@dataclass
class _Done:
    weight_kg: float
    last_seen: datetime


class SessionTracker:
    def __init__(
        self,
        settle: timedelta = timedelta(seconds=10),
        repeat_window: timedelta = timedelta(minutes=10),
        same_weight_kg: float = 0.5,
    ) -> None:
        self.settle = settle
        self.repeat_window = repeat_window
        self.same_weight_kg = same_weight_kg
        self._open: dict[str, tuple[datetime, Reading]] = {}
        self._done: dict[str, _Done] = {}

    def feed(self, reading: Reading) -> list[Reading]:
        addr = reading.address
        done = self._done.get(addr)
        if not reading.stable:
            # A different, unsettled weight means someone stepped on again. Flicker around
            # the value we already reported does not.
            if done and abs(reading.weight_kg - done.weight_kg) >= self.same_weight_kg:
                del self._done[addr]
            return []

        if (
            done
            and abs(reading.weight_kg - done.weight_kg) < self.same_weight_kg
            and reading.received_at - done.last_seen < self.repeat_window
        ):
            done.last_seen = reading.received_at
            return []

        if reading.load_removed and addr not in self._open:
            # Scales keep repeating the last result long after the weigh-in. Seeing only that
            # (e.g. after a restart) means we missed the weigh-in or reported it already.
            self._done[addr] = _Done(reading.weight_kg, reading.received_at)
            return []

        opened, best = self._open.get(addr, (reading.received_at, reading))
        if reading.impedance_ohm is not None or best.impedance_ohm is None:
            best = reading
        self._open[addr] = (opened, best)
        return [self._close(addr)] if reading.complete else []

    def tick(self, now: datetime) -> list[Reading]:
        """Close sessions that never got a complete reading within `settle`."""
        expired = [a for a, (opened, _) in self._open.items() if now - opened >= self.settle]
        return [self._close(a) for a in expired]

    def _close(self, addr: str) -> Reading:
        _, best = self._open.pop(addr)
        self._done[addr] = _Done(best.weight_kg, best.received_at)
        return best
