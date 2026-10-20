"""Garmin Connect, through python-garminconnect (unofficial; Garmin has no public API for this).

Tokens are created once with `scalebridge login <user>` and refreshed automatically.
"""

from __future__ import annotations

import asyncio
import getpass
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from scalebridge.models import WeighIn
from scalebridge.sinks import SinkAuthError, SinkError

log = logging.getLogger(__name__)


class GarminSink:
    name = "garmin"

    def __init__(self, tokens: Path, is_cn: bool = False) -> None:
        self.tokens = tokens
        self.is_cn = is_cn
        self._client: Garmin | None = None

    def _connect(self) -> Garmin:
        if self._client is None:
            if not self.tokens.exists():
                raise SinkAuthError(f"no Garmin tokens at {self.tokens}; run `scalebridge login`")
            client = Garmin(is_cn=self.is_cn)
            try:
                client.login(tokenstore=str(self.tokens))
            except GarminConnectAuthenticationError as e:
                raise SinkAuthError(f"Garmin login expired, run `scalebridge login`: {e}") from e
            self._client = client
        return self._client

    def _call(self, fn):
        try:
            return fn(self._connect())
        except GarminConnectAuthenticationError as e:
            self._client = None
            raise SinkAuthError(f"Garmin rejected the tokens, run `scalebridge login`: {e}") from e
        except (GarminConnectConnectionError, GarminConnectTooManyRequestsError, OSError) as e:
            self._client = None
            raise SinkError(f"Garmin request failed: {e}") from e
        except SinkError:
            raise
        except Exception as e:  # the library is unofficial; don't let surprises lose a weigh-in
            self._client = None
            raise SinkError(f"unexpected Garmin error: {e!r}") from e

    async def send(self, weighin: WeighIn) -> None:
        def upload(g: Garmin) -> None:
            g.add_body_composition(
                timestamp=weighin.taken_at.isoformat(),
                weight=round(weighin.weight_kg, 2),
                bmi=weighin.bmi,
            )

        await asyncio.to_thread(self._call, upload)

    async def latest_weight(self) -> tuple[float, datetime] | None:
        def fetch(g: Garmin) -> tuple[float, datetime] | None:
            end = g.today()
            start = end - timedelta(days=365)
            data = g.get_body_composition(start.isoformat(), end.isoformat())
            entries = [e for e in data.get("dateWeightList") or [] if e.get("weight")]
            if not entries:
                return None
            last = max(entries, key=lambda e: e["date"])
            return last["weight"] / 1000, datetime.fromtimestamp(last["date"] / 1000, UTC)

        return await asyncio.to_thread(self._call, fetch)


def interactive_login(tokens: Path, is_cn: bool = False) -> str:
    """Prompt for credentials (and an MFA code if the account has one) and save tokens."""
    email = input("Garmin email: ").strip()
    password = getpass.getpass("Garmin password: ")
    tokens.mkdir(parents=True, exist_ok=True)
    client = Garmin(email, password, is_cn=is_cn, prompt_mfa=lambda: input("MFA code: ").strip())
    client.login(tokenstore=str(tokens))
    return client.get_full_name() or email
