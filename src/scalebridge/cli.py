"""Command line: `scalebridge run | scan | login | check`."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import signal
import sys
from pathlib import Path

from scalebridge.config import Config, GarminSinkConfig, load_config


def _config(args: argparse.Namespace) -> Config:
    return load_config(Path(args.config))


def cmd_run(args: argparse.Namespace) -> None:
    from scalebridge.app import Bridge
    from scalebridge.sources.ble import BleSource

    cfg = _config(args)

    async def run() -> None:
        # As PID 1 in a container, SIGTERM is ignored unless handled: stop cleanly instead
        # of being killed after the stop timeout.
        task = asyncio.current_task()
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, task.cancel)
        with contextlib.suppress(asyncio.CancelledError):
            await Bridge(cfg, BleSource(cfg.ble.adapter)).run()
        logging.getLogger("scalebridge").info("stopped")

    asyncio.run(run())


def cmd_scan(args: argparse.Namespace) -> None:
    """Print every supported scale in range, to find its MAC address. Needs no config."""
    from scalebridge.decoders import decode
    from scalebridge.sources.ble import BleSource

    def show(adv):
        raw = " ".join(f"{uuid[4:8]}:{data.hex()}" for uuid, data in adv.service_data.items())
        reading = decode(adv)
        if reading:
            flags = " ".join(
                f for f, on in [("stable", reading.stable), ("removed", reading.load_removed)] if on
            )
            imp = f" {reading.impedance_ohm} Ω" if reading.impedance_ohm else ""
            print(
                f"{adv.address}  {adv.rssi or 0:>4} dBm  {reading.model:<34} "
                f"{reading.weight_kg:6.2f} kg{imp}  {flags}" + (f"  [{raw}]" if args.raw else ""),
                flush=True,
            )
        elif args.all:
            print(
                f"{adv.address}  {adv.rssi or 0:>4} dBm  {adv.name or '?':<34} [{raw}]", flush=True
            )

    async def scan() -> None:
        source = BleSource(args.adapter)
        await source.start(show)
        print(f"Scanning for {args.seconds} s. Step on the scale.", file=sys.stderr)
        try:
            await asyncio.sleep(args.seconds)
        finally:
            await source.stop()

    asyncio.run(scan())


def cmd_login(args: argparse.Namespace) -> None:
    from scalebridge.sinks.garmin import interactive_login

    cfg = _config(args)
    user = cfg.user(args.user)
    garmin = [s for s in user.sinks if isinstance(s, GarminSinkConfig)]
    if not garmin:
        sys.exit(f"user {user.name!r} has no garmin sink")
    tokens = cfg.data_dir / (garmin[0].tokens or f"garmin/{user.name}")
    name = interactive_login(tokens, is_cn=garmin[0].is_cn)
    print(f"Logged in as {name}. Tokens saved to {tokens}.")


def cmd_check(args: argparse.Namespace) -> None:
    """Validate the config and ask every sink for the user's latest weight."""
    from scalebridge.sinks import SinkError, build_sink

    cfg = _config(args)
    print(f"Config OK: {len(cfg.users)} user(s), {len(cfg.scales)} scale(s)")
    print(f"Data directory: {cfg.data_dir}")

    async def check() -> bool:
        ok = True
        for user in cfg.users:
            for sc in user.sinks:
                sink = build_sink(sc, user.name, cfg.data_dir)
                try:
                    latest = await sink.latest_weight()
                    shown = f"latest {latest[0]:.1f} kg on {latest[1]:%Y-%m-%d}" if latest else "OK"
                    print(f"  {user.name} -> {sink.name}: {shown}")
                except SinkError as e:
                    ok = False
                    print(f"  {user.name} -> {sink.name}: FAILED: {e}")
        return ok

    if not asyncio.run(check()):
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="scalebridge", description=__doc__)
    parser.add_argument(
        "-c",
        "--config",
        default=os.environ.get("SCALEBRIDGE_CONFIG", "config.yaml"),
        help="config file (default: $SCALEBRIDGE_CONFIG or ./config.yaml)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="listen and forward weigh-ins").set_defaults(func=cmd_run)
    p = sub.add_parser("scan", help="show supported scales in range")
    p.add_argument("-s", "--seconds", type=int, default=60)
    p.add_argument("-a", "--adapter", default=None, help="e.g. hci0")
    p.add_argument("--raw", action="store_true", help="also print raw service data")
    p.add_argument("--all", action="store_true", help="also print unsupported devices")
    p.set_defaults(func=cmd_scan)
    p = sub.add_parser("login", help="log a user in to Garmin Connect and save tokens")
    p.add_argument("user")
    p.set_defaults(func=cmd_login)
    sub.add_parser("check", help="validate config and sink access").set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    level = logging.DEBUG if args.verbose else os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # DEBUG is for scalebridge only: HTTP and OAuth libraries log tokens at that level.
    root = logging.getLogger()
    logging.getLogger("scalebridge").setLevel(root.level)
    root.setLevel(max(root.level, logging.INFO))
    for noisy in ("bleak", "garminconnect", "urllib3", "apprise"):
        logging.getLogger(noisy).setLevel(max(logging.getLogger().level, logging.WARNING))
    with contextlib.suppress(KeyboardInterrupt):
        args.func(args)
