"""Sinks receive finished weigh-ins. Add a new one by implementing `Sink` and registering a
config model in `scalebridge.config.SinkConfig` and a constructor in `build_sink`."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from scalebridge.config import GarminSinkConfig, JsonlSinkConfig, SinkConfig
from scalebridge.models import WeighIn


class SinkError(Exception):
    """Delivery failed; the weigh-in is queued and retried later."""


class SinkAuthError(SinkError):
    """Credentials are missing or expired; a human has to act."""


class Sink(Protocol):
    name: str

    async def send(self, weighin: WeighIn) -> None: ...

    async def latest_weight(self) -> tuple[float, datetime] | None:
        """The user's most recent weight known to this sink, if it can tell."""
        ...


def build_sink(cfg: SinkConfig, user: str, data_dir: Path) -> Sink:
    match cfg:
        case GarminSinkConfig():
            from scalebridge.sinks.garmin import GarminSink

            return GarminSink(data_dir / (cfg.tokens or f"garmin/{user}"), is_cn=cfg.is_cn)
        case JsonlSinkConfig():
            from scalebridge.sinks.jsonl import JsonlSink

            return JsonlSink(data_dir / cfg.path)
