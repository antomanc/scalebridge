"""Wire a source, the decoders, the tracker, the matcher and the sinks together."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta

from scalebridge.config import Config
from scalebridge.decoders import decode
from scalebridge.matching import Decision, Matcher
from scalebridge.models import Advertisement, Reading, WeighIn
from scalebridge.notify import Notifier
from scalebridge.sinks import Sink, SinkAuthError, SinkError, build_sink
from scalebridge.sources import Source
from scalebridge.state import OutboxItem, Sample, State
from scalebridge.tracker import SessionTracker

log = logging.getLogger(__name__)


def bmi(weight_kg: float, height_cm: float | None) -> float | None:
    return round(weight_kg / (height_cm / 100) ** 2, 1) if height_cm else None


class Bridge:
    def __init__(self, cfg: Config, source: Source, notifier: Notifier | None = None) -> None:
        self.cfg = cfg
        self.source = source
        self.notifier = notifier or Notifier(cfg.notify)
        self.state = State.load(cfg.data_dir / "state.json")
        self.matcher = Matcher(cfg.users, cfg.matching, self.state)
        self.tracker = SessionTracker(
            settle=timedelta(seconds=cfg.tracker.settle_seconds),
            repeat_window=timedelta(minutes=cfg.tracker.repeat_window_minutes),
        )
        self.sinks: dict[str, list[Sink]] = {
            u.name: [build_sink(s, u.name, cfg.data_dir) for s in u.sinks] for u in cfg.users
        }
        self.scales = {s.mac: s.name or s.mac for s in cfg.scales}
        self._queue: asyncio.Queue[Advertisement] = asyncio.Queue()

    async def run(self) -> None:
        if self.cfg.matching.seed_from_sinks:
            await self.seed_baselines()
        if self.state.outbox:
            await self.retry_outbox()
        await self.source.start(self._queue.put_nowait)
        log.info("listening for %s", ", ".join(self.scales.values()) or "any supported scale")
        retry = asyncio.create_task(self._retry_loop())
        try:
            while True:
                with contextlib.suppress(TimeoutError):
                    adv = await asyncio.wait_for(self._queue.get(), timeout=1)
                    for reading in self._feed(adv):
                        await self.handle(reading)
                for reading in self.tracker.tick(datetime.now(UTC)):
                    await self.handle(reading)
        finally:
            retry.cancel()
            await self.source.stop()

    def _feed(self, adv: Advertisement) -> list[Reading]:
        if self.scales and adv.address not in self.scales:
            return []
        reading = decode(adv)
        if reading is None:
            return []
        log.debug("%s %.2f kg stable=%s", reading.address, reading.weight_kg, reading.stable)
        return self.tracker.feed(reading)

    async def seed_baselines(self) -> None:
        for user in self.cfg.users:
            if user.name in self.state.baselines:
                continue
            for sink in self.sinks[user.name]:
                try:
                    latest = await sink.latest_weight()
                except Exception as e:
                    log.warning("%s: no latest weight from %s: %s", user.name, sink.name, e)
                    continue
                if latest:
                    weight, at = latest
                    self.state.baselines[user.name] = Sample(weight, at)
                    log.info("%s: baseline %.1f kg from %s", user.name, weight, sink.name)
                    break
        self.state.save()

    async def handle(self, reading: Reading) -> None:
        scale = self.scales.get(reading.address, reading.address)
        decision = self.matcher.assign(reading.weight_kg, reading.received_at)
        self.state.save()
        if decision.user is None:
            await self._rejected(reading, decision, scale)
            return

        user = self.cfg.user(decision.user)
        weighin = WeighIn(
            user=user.name,
            weight_kg=reading.weight_kg,
            taken_at=reading.received_at,
            scale=scale,
            bmi=bmi(reading.weight_kg, user.height_cm),
            impedance_ohm=reading.impedance_ohm,
        )
        log.info("%s: %.2f kg (%s)", user.name, weighin.weight_kg, decision.reason)
        delivered = []
        for i, sink in enumerate(self.sinks[user.name]):
            if await self._deliver(sink, weighin):
                delivered.append(sink.name)
            else:
                self.state.outbox.append(OutboxItem(user.name, i, weighin.to_dict()))
        self.state.save()

        note = " (new baseline after repeated readings)" if decision.reason == "confirmed" else ""
        where = ", ".join(delivered) or "nothing yet, will retry"
        await self.notifier.send(
            "uploaded",
            f"{user.name}: {weighin.weight_kg:.1f} kg",
            f"Sent to {where}{note}.",
        )

    async def _rejected(self, reading: Reading, decision: Decision, scale: str) -> None:
        if decision.reason == "ambiguous":
            why = "it could belong to more than one user without a baseline yet"
        elif decision.baseline_kg is not None:
            why = f"it is too far from the last weigh-in ({decision.baseline_kg:.1f} kg)"
        else:
            why = "it is outside every user's limits"
        log.info("rejected %.2f kg from %s: %s", reading.weight_kg, scale, why)
        await self.notifier.send(
            "rejected",
            f"Ignored {reading.weight_kg:.1f} kg",
            f"Not uploaded because {why}. If it was you, weigh again: "
            f"{self.cfg.matching.confirm_after} similar readings within "
            f"{self.cfg.matching.confirm_window_hours:g} h are accepted.",
        )

    async def _deliver(self, sink: Sink, weighin: WeighIn) -> bool:
        try:
            await sink.send(weighin)
            return True
        except SinkAuthError as e:
            log.error("%s: %s", sink.name, e)
            await self.notifier.send("error", f"{sink.name}: action needed", str(e))
        except SinkError as e:
            log.warning("%s: %s", sink.name, e)
        except Exception:
            log.exception("%s failed unexpectedly", sink.name)
        return False

    async def retry_outbox(self) -> None:
        remaining = []
        for item in self.state.outbox:
            sink = self.sinks[item.user][item.sink]
            weighin = WeighIn.from_dict(item.weighin)
            try:
                await sink.send(weighin)
                log.info("retried %s upload of %.2f kg", sink.name, weighin.weight_kg)
            except Exception as e:
                item.attempts += 1
                remaining.append(item)
                log.warning("retry %d for %s failed: %s", item.attempts, sink.name, e)
        self.state.outbox = remaining
        self.state.save()

    async def _retry_loop(self) -> None:
        while True:
            await asyncio.sleep(self.cfg.retry_interval_minutes * 60)
            if self.state.outbox:
                await self.retry_outbox()
