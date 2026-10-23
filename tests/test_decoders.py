import json
from pathlib import Path

import pytest

from scalebridge.decoders import DECODERS, decode

from .conftest import adv

VECTORS = json.loads((Path(__file__).parents[1] / "spec/vectors/decoders.json").read_text())
MODELS = {d.id: d.model for d in DECODERS}


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda c: c["name"])
def test_vector(case):
    r = decode(adv(case["payload"], uuid=int(case["service"], 16)))
    expect = case["expect"]
    if expect is None:
        assert r is None
        return
    assert r is not None
    assert r.model == MODELS[expect["decoder"]]
    assert r.weight_kg == pytest.approx(expect["weight_kg"], abs=0.01)
    assert (r.stable, r.complete, r.load_removed, r.impedance_ohm) == (
        expect["stable"],
        expect["complete"],
        expect["load_removed"],
        expect["impedance_ohm"],
    )
    clock = expect["scale_clock"]
    assert r.scale_clock == (None if clock is None else int(clock, 16))
