# Product

## What it is
scalebridge forwards weigh-ins from Bluetooth bathroom scales to Garmin Connect (and other
sinks), with no phone app in the loop. You step on the scale; seconds later the weight is
in Garmin and you get a notification.

## Who it's for
People with a cheap BLE scale (Xiaomi Mi Scale today) and a Garmin account, who already run
an always-on Linux box at home (home server, NAS, Raspberry Pi) and are comfortable with Docker.

## Principles
- **Clean install.** One unprivileged container, one config file, one data directory. Nothing
  scattered on the host besides BlueZ.
- **Never upload bad data.** A guest stepping on the scale must not land in your Garmin history.
  When unsure, skip and notify; a human can always weigh again.
- **Never lose good data.** Failed uploads are queued and retried.
- **General, not personal.** Multiple users, multiple scales, pluggable sources, decoders and
  sinks. Nothing hard-coded for one household.
- **One behaviour, many implementations.** The language-neutral vectors in `spec/` define
  decoding, so a future standalone ESP32 firmware behaves exactly like the Python service.

## Out of scope (for now)
- A web UI or dashboard.
- Body-composition estimates (body fat, muscle) from impedance.
- Two-way sync, or editing data already in Garmin.

## Known risk
Garmin has no public API for personal accounts. The Garmin sink depends on the unofficial
python-garminconnect and can break when Garmin changes its login.
