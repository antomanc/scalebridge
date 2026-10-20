# scalebridge

Step on your Bluetooth bathroom scale, and the weight shows up in Garmin Connect.

scalebridge listens for the measurements a scale broadcasts over Bluetooth Low Energy,
works out who stepped on it, and forwards the weigh-in to Garmin Connect (and other sinks).
It runs as one small, unprivileged container on any Linux machine with Bluetooth:
a home server, a NAS, a Raspberry Pi.

- **No pairing, no phone app.** Supported scales broadcast their readings; scalebridge just listens.
- **Guests don't pollute your data.** A weight is only attributed to you if it's close to
  your last one. Anything else is skipped and you get a notification.
- **Notifications anywhere** through [Apprise](https://appriseit.com): Telegram, ntfy,
  Discord, email and 100+ more.
- **Nothing lost when offline.** Failed uploads are queued and retried.

## Supported scales

| Scale | Model | Data |
|---|---|---|
| Xiaomi Mi Smart Scale 2 | XMTZC01HM, XMTZC04HM | weight |
| Xiaomi Mi Body Composition Scale 1/2 | XMTZC02HM, XMTZC05HM | weight, impedance |

The Smart Scale 2 decoder is tested against captures from a real XMTZC04HM. The Body
Composition decoder follows ESPHome's implementation but hasn't been tested on hardware
yet; reports are welcome. Body-fat estimates from impedance are not computed yet.
Adding a scale is one small class, see [Contributing](#contributing).

## Quick start (Docker)

You need a Linux host with a Bluetooth adapter and BlueZ (`sudo apt install bluez` on
Debian/Ubuntu). The container talks to BlueZ over the host's D-Bus socket, so it needs
no privileged mode and no host networking.

```sh
mkdir scalebridge && cd scalebridge
curl -LO https://raw.githubusercontent.com/antomanc/scalebridge/main/compose.yaml
curl -L -o config.yaml https://raw.githubusercontent.com/antomanc/scalebridge/main/config.example.yaml
mkdir data   # must be writable by uid 1000, or set PUID/PGID in .env

# 1. Find your scale: run this, then step on the scale.
docker compose run --rm scalebridge scan

# 2. Put its MAC address and your details in config.yaml.

# 3. Log in to Garmin once (asks for your password and, if enabled, the 2FA code).
docker compose run --rm scalebridge login alice

# 4. Check everything, then start.
docker compose run --rm scalebridge check
docker compose up -d
docker compose logs -f
```

Garmin tokens are stored in `data/garmin/<user>/` and refresh automatically. If Garmin
ever invalidates them, you get an `error` notification; run `login` again.

## How a reading is attributed

1. **Tracking.** A scale repeats its result for minutes. scalebridge reports each
   weigh-in once, and ignores results it only sees after the person stepped off
   (leftovers from before a restart).
2. **Matching.** A weight belongs to the user whose last weigh-in is closest, if it's
   within `tolerance_kg` (3 kg by default) and inside their optional `min/max_weight_kg`.
   On first start, the last weight is read from Garmin.
3. **Rejected weights** are not uploaded; you get a notification. If you really changed
   more than the tolerance (say, after a long break), weigh twice: `confirm_after`
   similar readings within `confirm_window_hours` are accepted. This only happens when a
   single user could match, so a guest can't move your baseline in a shared household.

Everything is configured in [`config.example.yaml`](config.example.yaml).

## Commands

```
scalebridge scan [--seconds N] [--raw] [--all]   find scales and see live readings
scalebridge login USER                           log USER in to Garmin, save tokens
scalebridge check                                validate config, test every sink
scalebridge run                                  the service (default in Docker)
```

`-c/--config` (or `$SCALEBRIDGE_CONFIG`) selects the config file, `-v` turns on debug logs.

## Set up with an AI agent

Paste this into your agent (Claude Code, Codex, ...):

```text
Help me set up scalebridge on this machine: https://github.com/antomanc/scalebridge
Ask me about the config.
```

## Without Docker

```sh
uv tool install git+https://github.com/antomanc/scalebridge   # or: pipx install ...
scalebridge -c ~/.config/scalebridge/config.yaml run
```

## Architecture

```
 Source ──► Decoder ──► SessionTracker ──► Matcher ──► Sinks ──► Notifier
 (BLE)      (bytes→kg)  (one per weigh-in) (which user) (Garmin, jsonl)
```

| Module | Role | Extend by |
|---|---|---|
| `sources/` | delivers raw advertisements | implementing `Source` (e.g. an ESP32 relay) |
| `decoders/` | turns service data into a `Reading` | adding a `Decoder` to `DECODERS` |
| `tracker.py` | collapses repeats into one result per weigh-in | |
| `matching.py` | assigns weights to users, rejects outliers | |
| `sinks/` | delivers `WeighIn`s | implementing `Sink` + a config model |
| `notify.py` | Apprise notifications | |

`spec/vectors/` holds language-neutral test vectors. The Python package and the C port
in [`firmware/esp32/`](firmware/esp32/) are both tested against them; that directory
also describes the plan for a standalone ESP32 version.

## Contributing

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format .
```

To add a scale: capture its advertisements with `scalebridge scan --all --raw`, add them
to `spec/vectors/decoders.json`, then write the decoder until the tests pass.

## Caveats

Garmin has no public API for personal accounts. The Garmin sink uses the unofficial
[python-garminconnect](https://github.com/cyberjunky/python-garminconnect), which can
break when Garmin changes its login. Keep the image updated.

## Credits

Byte layouts from [ESPHome](https://esphome.io/components/sensor/xiaomi_miscale/) and
[lolouk44/xiaomi_mi_scale](https://github.com/lolouk44/xiaomi_mi_scale). Inspired by
[export2garmin](https://github.com/RobertWojtowicz/export2garmin).

## License

MIT
