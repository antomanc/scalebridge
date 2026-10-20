# Notes for AI agents

## Setting it up for someone

Follow "Quick start" in README.md. Let the user run `scalebridge login` themselves:
it asks for their Garmin password and 2FA code.

## Working on the code

- Python ≥ 3.12, managed with uv: `uv sync`, `uv run pytest`,
  `uv run ruff check . && uv run ruff format .`. CI runs all three.
- The pipeline and its extension points are described under "Architecture" in README.md.
  Keep modules independent: decoders know nothing about users, sinks know nothing about BLE.
- Behaviour shared with the ESP32 firmware is specified in `spec/vectors/`. When you
  change a decoder, change the vectors first, then make both the Python decoder and
  `firmware/esp32/components/scale_decoders` pass (`tests/test_firmware_decoders.py`
  compiles the C code with the host `cc`).
- Real BLE and Garmin are never touched by the tests. Use fakes like those in
  `tests/test_app.py`.
- `scalebridge scan` needs a Bluetooth adapter.
- Don't log weights at INFO for anything but finished weigh-ins, and never log tokens.
