"""YAML configuration. `${VAR}` anywhere in the file is replaced by the environment variable."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScaleConfig(_Model):
    mac: str
    name: str | None = None

    @field_validator("mac")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class GarminSinkConfig(_Model):
    type: Literal["garmin"]
    # Token directory, relative to data_dir. Defaults to garmin/<user>.
    tokens: str | None = None
    is_cn: bool = False


class JsonlSinkConfig(_Model):
    type: Literal["jsonl"]
    # File path, relative to data_dir.
    path: str = "weighins.jsonl"


SinkConfig = Annotated[GarminSinkConfig | JsonlSinkConfig, Field(discriminator="type")]


class UserConfig(_Model):
    name: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    height_cm: float | None = Field(default=None, gt=0)
    # Hard limits: readings outside are never attributed to this user.
    min_weight_kg: float | None = None
    max_weight_kg: float | None = None
    # Overrides matching.tolerance_kg for this user.
    tolerance_kg: float | None = None
    sinks: list[SinkConfig] = Field(min_length=1)


class MatchingConfig(_Model):
    # A reading is attributed to a user when it is this close to their last weigh-in.
    tolerance_kg: float = Field(default=3.0, gt=0)
    # Accept an out-of-tolerance weight after this many matching readings (0 = never).
    confirm_after: int = Field(default=2, ge=0)
    confirm_window_hours: float = Field(default=24, gt=0)
    # On startup, seed an empty baseline from the user's latest weight in a sink (e.g. Garmin).
    seed_from_sinks: bool = True


class TrackerConfig(_Model):
    settle_seconds: float = 10
    repeat_window_minutes: float = 10
    empty_below_kg: float = 10


NotifyEvent = Literal["uploaded", "rejected", "error"]


class NotifyConfig(_Model):
    # Apprise URLs, e.g. tgram://BOT_TOKEN/CHAT_ID or ntfy://topic. See https://appriseit.com
    urls: list[str] = []
    events: list[NotifyEvent] = ["uploaded", "rejected", "error"]


class BleConfig(_Model):
    adapter: str | None = None  # e.g. hci0; None = system default


class Config(_Model):
    data_dir: Path = Path("data")
    # Only these scales are listened to. Empty = any supported scale (not recommended:
    # advertisements are public, so a neighbour's scale would be picked up too).
    scales: list[ScaleConfig] = []
    users: list[UserConfig] = Field(min_length=1)
    matching: MatchingConfig = MatchingConfig()
    tracker: TrackerConfig = TrackerConfig()
    notify: NotifyConfig = NotifyConfig()
    ble: BleConfig = BleConfig()
    retry_interval_minutes: float = 15

    @model_validator(mode="after")
    def _unique_users(self) -> Config:
        names = [u.name for u in self.users]
        if len(names) != len(set(names)):
            raise ValueError("user names must be unique")
        return self

    def user(self, name: str) -> UserConfig:
        for u in self.users:
            if u.name == name:
                return u
        raise KeyError(f"no user named {name!r} in the config")


def _expand_env(text: str) -> str:
    def sub(m: re.Match[str]) -> str:
        if (value := os.environ.get(m[1])) is None:
            raise ValueError(f"environment variable {m[1]} is referenced in the config but not set")
        return value

    return _ENV_RE.sub(sub, text)


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(_expand_env(path.read_text())) or {}
    cfg = Config.model_validate(raw)
    if not cfg.data_dir.is_absolute():
        cfg.data_dir = (path.parent / cfg.data_dir).resolve()
    return cfg
