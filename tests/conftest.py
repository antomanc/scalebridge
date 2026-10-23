from datetime import UTC, datetime, timedelta

import pytest

from scalebridge.decoders.xiaomi import uuid16
from scalebridge.models import Advertisement, Reading

T0 = datetime(2026, 10, 20, 7, 0, tzinfo=UTC)
MAC = "AA:BB:CC:DD:EE:01"


def adv(hex_payload: str, uuid: int = 0x181D, at: datetime = T0, mac: str = MAC) -> Advertisement:
    return Advertisement(mac, {uuid16(uuid): bytes.fromhex(hex_payload)}, at)


def reading(
    weight: float,
    seconds: float = 0,
    stable: bool = True,
    complete: bool | None = None,
    removed: bool = False,
    impedance: int | None = None,
    clock: int | None = None,
) -> Reading:
    return Reading(
        address=MAC,
        model="test",
        weight_kg=weight,
        received_at=T0 + timedelta(seconds=seconds),
        stable=stable,
        complete=stable if complete is None else complete,
        load_removed=removed,
        impedance_ohm=impedance,
        scale_clock=clock,
    )


@pytest.fixture
def t0() -> datetime:
    return T0
