# Behaviour spec

Language-neutral test vectors. Every implementation of scalebridge (the Python package
in `src/`, the ESP32 firmware in `firmware/esp32/`) is tested against these files, so they
cannot drift apart.

- `vectors/decoders.json`: BLE service data → decoded reading. Cases marked `captured`
  come from real scales (weights altered for privacy, flags and layout untouched); `synthetic` ones are built from the documented byte layout.

When you add support for a scale, add captures here first. `scalebridge scan --raw` prints
raw payloads (`--all` shows devices no decoder understands yet).
