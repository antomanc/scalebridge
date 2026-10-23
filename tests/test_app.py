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


def test_garmin_retries_once_on_connection_reset(tmp_path):
    from scalebridge.sinks.garmin import GarminSink

    sink = GarminSink(tmp_path)
    calls = []

    def flaky(_client):
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionResetError(104, "Connection reset by peer")
        return "ok"

    sink._connect = lambda: object()
    assert sink._call(flaky) == "ok" and len(calls) == 2


def test_weigh_in_seen_only_after_stepping_off_is_uploaded_once(tmp_path):
    # Settling, then (stable readings lost) the empty scale and the repeated result.
    sink = MemorySink()
    bridge = make_bridge(tmp_path, sink)
    payloads = ["02b63ab2070101000725", "821400b20701030f3736"] + ["a2ac3ab2070101000727"] * 20
    asyncio.run(weigh(bridge, payloads))
    assert [w.weight_kg for w in sink.sent] == [pytest.approx(75.1)]


def test_empty_scale_wobble_then_repeats_is_not_uploaded_twice(tmp_path):
    # Captured: result, a 0.15 kg wobble on the empty scale, then the result repeated.
    sink = MemorySink()
    bridge = make_bridge(tmp_path, sink)
    payloads = [
        "022837b2070103172a0c",
        "222837b2070103172a0c",
        "a22837b2070103172a10",
        "021e00b207010317320d",
        "821e00b207010317320d",
        "a22837b2070103172a10",
    ]
    asyncio.run(weigh(bridge, payloads))
    assert [w.weight_kg for w in sink.sent] == [pytest.approx(70.6)]


# Every distinct advertisement an XMTZC04HM sent on 2026-10-23 (seconds, payload): a
# weigh-in, the same weight again 8 minutes later, stepping off before the weight settled,
# and a third weigh-in.
CAPTURE = [
    (0.0, "821400b20701030f3736"),
    (1.1, "024637b2070103172a0a"),
    (2.4, "022837b2070103172a0b"),
    (2.8, "022837b2070103172a0c"),
    (5.2, "222837b2070103172a0c"),
    (7.1, "a22837b2070103172a10"),
    (478.3, "222837b2070103173206"),
    (480.2, "a22837b2070103173209"),
    (484.3, "021e00b207010317320d"),
    (484.6, "821e00b207010317320d"),
    (486.2, "021e00b207010317320f"),
    (486.5, "821400b207010317320f"),
    (488.5, "020c12b2070103173211"),
    (488.7, "02a636b2070103173212"),
    (489.2, "022837b2070103173212"),
    (489.5, "020a37b2070103173212"),
    (490.0, "022837b2070103173213"),
    (490.4, "02ea15b2070103173213"),
    (490.7, "82ea15b2070103173214"),
    (663.7, "022837b207010317350c"),
    (664.6, "222837b207010317350d"),
    (669.6, "a22837b2070103173512"),
]


async def replay(bridge, capture):
    for seconds, payload in capture:
        for r in bridge._feed(adv(payload, at=T0 + timedelta(seconds=seconds))):
            await bridge.handle(r)


def test_captured_morning_uploads_every_weigh_in_once(tmp_path):
    sink = MemorySink()
    bridge = make_bridge(tmp_path, sink)
    asyncio.run(replay(bridge, CAPTURE))
    assert [round(w.weight_kg, 2) for w in sink.sent] == [70.6, 70.6, 70.6]


def test_captured_morning_without_any_stable_reading_while_standing(tmp_path):
    sink = MemorySink()
    bridge = make_bridge(tmp_path, sink)
    asyncio.run(replay(bridge, [(s, p) for s, p in CAPTURE if not p.startswith("22")]))
    assert [round(w.weight_kg, 2) for w in sink.sent] == [70.6, 70.6, 70.6]
