"""Collapse the stream of readings into one result per weigh-in.

Scales repeat the same final value for minutes after you step off, and some send the
weight before the impedance. The tracker opens a session on the first stable reading,
closes it when a decoder marks a reading complete (or after `settle`), and then ignores
repeats of that value until the scale starts a new measurement. A result that is only ever
seen after the person stepped off is a leftover from an earlier weigh-in and is ignored,
unless the scale was settling at that weight moments before: then we just missed its
stable readings.

Scales that report their own clock (`Reading.scale_clock`) make this exact: the clock is
fixed while the scale repeats a result and changes with each new measurement (and once
more when the person steps off). A result with a new clock is a new weigh-in, even at the
same weight, and one with a known clock is a repeat, however late it comes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from scalebridge.models import Reading

log = logging.getLogger(__name__)


@dataclass
class _Done:
    weight_kg: float
    last_seen: datetime
    clocks: set[int] = field(default_factory=set)  # scale clocks of this result
    stepped_off: bool = False

    @classmethod
    def of(cls, reading: Reading) -> _Done:
        clocks = set() if reading.scale_clock is None else {reading.scale_clock}
        return cls(reading.weight_kg, reading.received_at, clocks, reading.load_removed)


class SessionTracker:
    def __init__(
        self,
        settle: timedelta = timedelta(seconds=10),
        repeat_window: timedelta = timedelta(minutes=10),
        same_weight_kg: float = 0.5,
        settling_window: timedelta = timedelta(minutes=1),
    ) -> None:
        self.settle = settle
        self.repeat_window = repeat_window
        self.same_weight_kg = same_weight_kg
        self.settling_window = settling_window
        self._open: dict[str, tuple[datetime, Reading]] = {}
        self._done: dict[str, _Done] = {}
        self._settling: dict[str, Reading] = {}

    def feed(self, reading: Reading) -> list[Reading]:
        addr = reading.address
        done = self._done.get(addr)
        if not reading.stable:
            if reading.load_removed:
                return []  # the scale emptying after a weigh-in
            self._settling[addr] = reading
            # Without a scale clock, a different unsettled weight means someone stepped on
            # again. Flicker around the value we already reported does not.
            if (
                done
                and reading.scale_clock is None
                and abs(reading.weight_kg - done.weight_kg) >= self.same_weight_kg
            ):
                del self._done[addr]
            return []

        if done and self._is_repeat(done, reading):
            done.last_seen = reading.received_at
            return []

        if reading.load_removed and addr not in self._open:
            settling = self._settling.get(addr)
            new_clock = done is not None and reading.scale_clock is not None
            settled_here = (
                settling is not None
                and reading.received_at - settling.received_at < self.settling_window
                and abs(reading.weight_kg - settling.weight_kg) < self.same_weight_kg
            )
            self._done[addr] = _Done.of(reading)
            if new_clock or settled_here:
                # A new result whose stable readings while standing got lost.
                return [reading]
            # Scales keep repeating the last result long after the weigh-in. Seeing only that
            # (e.g. after a restart) means we missed the weigh-in or reported it already.
            log.info("%s: ignored a result first seen after stepping off", addr)
            return []

        opened, best = self._open.get(addr, (reading.received_at, reading))
        if reading.impedance_ohm is not None or best.impedance_ohm is None:
            best = reading
        self._open[addr] = (opened, best)
        return [self._close(addr)] if reading.complete else []

    def _is_repeat(self, done: _Done, reading: Reading) -> bool:
        clock = reading.scale_clock
        if clock is not None and clock in done.clocks:
            return True
        same = (
            abs(reading.weight_kg - done.weight_kg) < self.same_weight_kg
            and reading.received_at - done.last_seen < self.repeat_window
        )
        if clock is None:
            return same
        if same and reading.load_removed and not done.stepped_off:
            # Stepping off after the result: the scale restamps it once.
            done.clocks.add(clock)
            done.stepped_off = True
            return True
        return False

    def tick(self, now: datetime) -> list[Reading]:
        """Close sessions that never got a complete reading within `settle`."""
        expired = [a for a, (opened, _) in self._open.items() if now - opened >= self.settle]
        return [self._close(a) for a in expired]

    def _close(self, addr: str) -> Reading:
        _, best = self._open.pop(addr)
        self._done[addr] = _Done.of(best)
        return best
