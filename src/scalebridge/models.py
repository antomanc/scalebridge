"""Data passed between pipeline stages: source -> decoder -> tracker -> matcher -> sinks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Advertisement:
    """One raw BLE advertisement, independent of how it was received."""

    address: str  # upper-case MAC, "AA:BB:CC:DD:EE:FF"
    service_data: Mapping[str, bytes]  # full 128-bit lower-case UUID -> payload
    received_at: datetime  # timezone-aware
    name: str | None = None
    rssi: int | None = None


@dataclass(frozen=True, slots=True)
class Reading:
    """What a decoder understood from a single advertisement."""

    address: str
    model: str
    weight_kg: float
    received_at: datetime
    stable: bool  # the scale considers the weight settled
    complete: bool  # nothing more will follow for this weigh-in (e.g. impedance done)
    load_removed: bool = False
    impedance_ohm: int | None = None
    # The scale's own timestamp, opaque: not a usable date, but it changes with every new
    # measurement and stays the same while the scale repeats one. None if not reported.
    scale_clock: int | None = None


@dataclass(frozen=True, slots=True)
class WeighIn:
    """A finished weigh-in attributed to a user, ready for the sinks."""

    user: str
    weight_kg: float
    taken_at: datetime
    scale: str
    bmi: float | None = None
    impedance_ohm: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["taken_at"] = self.taken_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> WeighIn:
        return cls(**{**d, "taken_at": datetime.fromisoformat(d["taken_at"])})
