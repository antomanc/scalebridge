"""Listen for advertisements with a local adapter through BlueZ (via bleak and D-Bus)."""

from __future__ import annotations

from datetime import UTC, datetime

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from scalebridge.models import Advertisement
from scalebridge.sources import OnAdvertisement


class BleSource:
    def __init__(self, adapter: str | None = None) -> None:
        self.adapter = adapter
        self._scanner: BleakScanner | None = None

    async def start(self, on_advertisement: OnAdvertisement) -> None:
        def callback(device: BLEDevice, adv: AdvertisementData) -> None:
            if not adv.service_data:
                return
            on_advertisement(
                Advertisement(
                    address=device.address.upper(),
                    service_data={k.lower(): bytes(v) for k, v in adv.service_data.items()},
                    received_at=datetime.now(UTC),
                    name=adv.local_name,
                    rssi=adv.rssi,
                )
            )

        kwargs = {"bluez": {"adapter": self.adapter}} if self.adapter else {}
        self._scanner = BleakScanner(detection_callback=callback, **kwargs)
        await self._scanner.start()

    async def stop(self) -> None:
        if self._scanner:
            await self._scanner.stop()
            self._scanner = None
