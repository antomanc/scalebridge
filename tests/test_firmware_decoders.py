"""Run the ESP32 firmware's C decoders on the host against the same vectors as the Python ones."""

import ctypes
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "firmware/esp32/components/scale_decoders"
VECTORS = json.loads((ROOT / "spec/vectors/decoders.json").read_text())

pytestmark = pytest.mark.skipif(shutil.which("cc") is None, reason="no C compiler")


class Reading(ctypes.Structure):
    _fields_ = [
        ("weight_kg", ctypes.c_float),
        ("stable", ctypes.c_bool),
        ("complete", ctypes.c_bool),
        ("load_removed", ctypes.c_bool),
        ("impedance_ohm", ctypes.c_int32),
        ("scale_clock", ctypes.c_int64),
    ]


@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    so = tmp_path_factory.mktemp("c") / "libscale_decoders.so"
    subprocess.run(
        [
            "cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
            "-I", str(COMPONENT / "include"), str(COMPONENT / "scale_decoders.c"), "-o", str(so),
        ],
        check=True,
    )  # fmt: skip
    lib = ctypes.CDLL(str(so))
    lib.sb_decode.argtypes = [
        ctypes.c_uint16,
        ctypes.c_char_p,
        ctypes.c_size_t,
        ctypes.POINTER(Reading),
    ]
    lib.sb_decoder_id.restype = ctypes.c_char_p
    return lib


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda c: c["name"])
def test_vector(lib, case):
    payload = bytes.fromhex(case["payload"])
    r = Reading()
    decoder = lib.sb_decode(int(case["service"], 16), payload, len(payload), ctypes.byref(r))
    expect = case["expect"]
    if expect is None:
        assert decoder == 0
        return
    assert lib.sb_decoder_id(decoder).decode() == expect["decoder"]
    assert r.weight_kg == pytest.approx(expect["weight_kg"], abs=0.01)
    impedance = None if r.impedance_ohm < 0 else r.impedance_ohm
    assert (r.stable, r.complete, r.load_removed, impedance) == (
        expect["stable"],
        expect["complete"],
        expect["load_removed"],
        expect["impedance_ohm"],
    )
    clock = expect["scale_clock"]
    assert r.scale_clock == (-1 if clock is None else int(clock, 16))
