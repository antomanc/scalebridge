"""End-to-end through the Bridge with a fake source and an in-memory sink."""

import asyncio
from datetime import timedelta

import pytest

from scalebridge.app import Bridge, bmi
from scalebridge.config import Config, NotifyConfig
from scalebridge.sinks import SinkError

from .conftest import MAC, T0, adv


class FakeSource:
    async def start(self, on_advertisement):
        self.on_advertisement = on_advertisement

    async def stop(self):
        pass


class MemorySink:
    name = "memory"

    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    async def send(self, weighin):
        if self.fail:
            raise SinkError("offline")
        self.sent.append(weighin)

    async def latest_weight(self):
        return None


class Recorder:
    def __init__(self):
        self.messages = []

    async def send(self, event, title, body):
        self.messages.append((event, title))


def make_bridge(tmp_path, sink, scales=None):
    cfg = Config(
        data_dir=tmp_path,
        scales=scales if scales is not None else [{"mac": MAC.lower()}],
        users=[{"name": "me", "height_cm": 180, "sinks": [{"type": "jsonl"}]}],
        notify=NotifyConfig(),
    )
    bridge = Bridge(cfg, FakeSource(), Recorder())
    bridge.sinks["me"] = [sink]
    return bridge


async def weigh(bridge, payloads, start=T0):
    for i, p in enumerate(payloads):
        for r in bridge._feed(adv(p, at=start + timedelta(seconds=i))):
            await bridge.handle(r)


def test_weigh_in_reaches_sink_with_bmi(tmp_path):
    sink = MemorySink()
    bridge = make_bridge(tmp_path, sink)
    asyncio.run(weigh(bridge, ["02b63ab2070101000725", "22ac3ab2070101000726"] * 3))
    [w] = sink.sent
    assert w.user == "me" and w.weight_kg == pytest.approx(75.1) and w.bmi == 23.2
    assert bridge.notifier.messages == [("uploaded", "me: 75.1 kg")]


def test_other_scales_are_ignored(tmp_path):
    sink = MemorySink()
    bridge = make_bridge(tmp_path, sink, scales=[{"mac": "00:11:22:33:44:55"}])
    asyncio.run(weigh(bridge, ["22ac3ab2070101000726"]))
    assert sink.sent == []


def test_failed_upload_is_retried(tmp_path):
    sink = MemorySink(fail=True)
    bridge = make_bridge(tmp_path, sink)
    asyncio.run(weigh(bridge, ["22ac3ab2070101000726"]))
    assert len(bridge.state.outbox) == 1

    sink.fail = False
    asyncio.run(bridge.retry_outbox())
    assert bridge.state.outbox == [] and len(sink.sent) == 1


def test_bmi():
    assert bmi(75.1, 180) == 23.2
    assert bmi(75.1, None) is None
