"""Decoders turn a scale's BLE service data into a `Reading`.

To support a new scale, add a `Decoder` to a module in this package and list it in `DECODERS`.
"""

from __future__ import annotations

from typing import Protocol

from scalebridge.decoders import xiaomi
from scalebridge.models import Advertisement, Reading


class Decoder(Protocol):
    id: str  # stable identifier, shared with the firmware and spec/vectors
    model: str
    service_uuid: str

    def decode(self, payload: bytes, adv: Advertisement) -> Reading | None: ...


DECODERS: list[Decoder] = [xiaomi.MiScale(), xiaomi.MiBodyCompositionScale()]


def decode(adv: Advertisement) -> Reading | None:
    """Return the first successful decoding of `adv`, or None if no decoder understands it."""
    for decoder in DECODERS:
        payload = adv.service_data.get(decoder.service_uuid)
        if payload is not None and (reading := decoder.decode(payload, adv)):
            return reading
    return None
