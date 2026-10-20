"""Sources deliver raw advertisements. The built-in one listens with the local Bluetooth
adapter; another transport (e.g. an ESP32 relaying advertisements over the network) only
has to implement `Source`."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from scalebridge.models import Advertisement

OnAdvertisement = Callable[[Advertisement], None]


class Source(Protocol):
    async def start(self, on_advertisement: OnAdvertisement) -> None: ...

    async def stop(self) -> None: ...
