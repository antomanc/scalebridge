"""Notifications through Apprise, which speaks Telegram, ntfy, Discord, email and many more."""

from __future__ import annotations

import asyncio
import logging

import apprise

from scalebridge.config import NotifyConfig, NotifyEvent

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, cfg: NotifyConfig) -> None:
        self.events = set(cfg.events)
        self._apprise = apprise.Apprise()
        for url in cfg.urls:
            if not self._apprise.add(url):
                raise ValueError("an apprise URL in notify.urls is invalid")

    async def send(self, event: NotifyEvent, title: str, body: str) -> None:
        if event not in self.events or not len(self._apprise):
            return
        ok = await asyncio.to_thread(self._apprise.notify, title=title, body=body)
        if not ok:
            log.warning("could not deliver %s notification", event)
