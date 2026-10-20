"""Small JSON state file: per-user baselines, unconfirmed readings, and failed uploads to retry."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Sample:
    weight_kg: float
    at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {"weight_kg": self.weight_kg, "at": self.at.isoformat()}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Sample:
        return cls(d["weight_kg"], datetime.fromisoformat(d["at"]))


@dataclass
class OutboxItem:
    user: str
    sink: int  # index in the user's sink list
    weighin: dict[str, Any]
    attempts: int = 0


@dataclass
class State:
    path: Path
    baselines: dict[str, Sample] = field(default_factory=dict)
    pending: list[Sample] = field(default_factory=list)
    outbox: list[OutboxItem] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> State:
        if not path.exists():
            return cls(path)
        d = json.loads(path.read_text())
        return cls(
            path,
            baselines={k: Sample.from_dict(v) for k, v in d.get("baselines", {}).items()},
            pending=[Sample.from_dict(s) for s in d.get("pending", [])],
            outbox=[OutboxItem(**o) for o in d.get("outbox", [])],
        )

    def save(self) -> None:
        d = {
            "baselines": {k: v.to_dict() for k, v in self.baselines.items()},
            "pending": [s.to_dict() for s in self.pending],
            "outbox": [asdict(o) for o in self.outbox],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=2))
        os.replace(tmp, self.path)
