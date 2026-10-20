# scalebridge on an ESP32 (planned)

Goal: an ESP-IDF firmware that does everything the Python service does, with no server.
This directory holds the parts that already exist and the plan for the rest.

## Status

| Piece | Python (`src/scalebridge/`) | ESP32 (here) |
|---|---|---|
| BLE source | `sources/ble.py` (BlueZ) | to do: NimBLE passive scan |
| Decoders | `decoders/` | **done**: `components/scale_decoders`, passes `spec/vectors/decoders.json` |
| Session tracker | `tracker.py` | to do |
| User matching | `matching.py` | to do |
| State | `state.py` (JSON file) | to do: NVS |
| Garmin sink | `sinks/garmin.py` (python-garminconnect) | to do, see the risk below |
| Notifications | `notify.py` (Apprise) | to do: Telegram / ntfy over HTTPS |
| Config | `config.yaml` | to do: Kconfig defaults + NVS, set over a provisioning page |

## How to grow this

The module boundaries are the same as the Python package's, so each piece is ported
by reading one Python file, and **each port is tested against the same vectors**:

1. Port a module as a plain C component under `components/`, without ESP-IDF calls
   (time is passed in, storage goes through a small interface). That keeps it buildable on a PC.
2. Add or extend a vector file in `../../spec/vectors/` so the behaviour is written down once.
3. Add a host test in `../../tests/` that compiles the component and runs the vectors
   (see `tests/test_firmware_decoders.py`), so CI checks both implementations.
4. The app itself (`main/`, `CMakeLists.txt`, `sdkconfig.defaults`) only wires components
   to NimBLE, Wi-Fi, NVS and HTTPS.

Planned layout:

```
firmware/esp32/
├── CMakeLists.txt            ESP-IDF project
├── sdkconfig.defaults
├── main/                     wiring: NimBLE scan -> tracker -> matcher -> sinks
└── components/
    ├── scale_decoders/       done
    ├── weigh_tracker/        port of tracker.py
    ├── user_matcher/         port of matching.py
    └── garmin_sink/          token refresh + FIT upload
```

## The hard part: Garmin

Garmin has no public API for personal accounts. Reading the scale is easy; staying
logged in to Garmin is not:

- **Login with password and 2FA** is a multi-step flow behind bot protection. The Python
  library imitates a Chrome TLS fingerprint and retries several strategies. This will not
  run on the ESP32. Plan: log in once with the Python CLI (`scalebridge login`) and copy
  the resulting token file to the device over the provisioning page.
- **Refreshing the token and uploading** are plain HTTPS requests (OAuth2 refresh to
  `diauth.garmin.com`, then a FIT upload). These can run on the ESP32, as long as Garmin
  doesn't start rejecting non-browser TLS clients on those endpoints too.
- **Garmin changes things.** python-garminconnect ships fixes often. On a server that
  means pulling a new image; on the ESP32 it means porting the fix and flashing. Expect
  the Garmin sink to need the most upkeep.

A middle ground that is already supported: keep the Python service running somewhere,
and have the ESP32 act only as a Bluetooth relay for scales out of the server's range.
