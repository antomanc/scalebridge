"""Append weigh-ins to a JSON Lines file: a local history, and handy for trying things out."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

from scalebridge.models import WeighIn


class JsonlSink:
    name = "jsonl"

    def __init__(self, path: Path) -> None:
        self.path = path

    async def send(self, weighin: WeighIn) -> None:
        await asyncio.to_thread(self._append, weighin)

    def _append(self, weighin: WeighIn) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(weighin.to_dict()) + "\n")

    async def latest_weight(self) -> tuple[float, datetime] | None:
        return None
