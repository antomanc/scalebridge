"""Decide which user a weight belongs to, or reject it.

A user is a candidate when the weight is inside their optional min/max limits and within
tolerance of their last accepted weigh-in (their baseline). Among candidates with a
baseline, the closest wins. A user without a baseline is chosen only when they are the
sole candidate. A rejected weight is remembered; when enough similar rejected weights
arrive within the confirm window and exactly one user's limits allow it, it is accepted
for that user, so a real change (e.g. after a long break) can't lock someone out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from scalebridge.config import MatchingConfig, UserConfig
from scalebridge.state import Sample, State

Reason = Literal["matched", "first", "confirmed", "rejected", "ambiguous"]


@dataclass(frozen=True)
class Decision:
    user: str | None
    reason: Reason
    baseline_kg: float | None = None  # the chosen user's (or closest user's) previous weight


class Matcher:
    def __init__(self, users: list[UserConfig], cfg: MatchingConfig, state: State) -> None:
        self.users = users
        self.cfg = cfg
        self.state = state

    def tolerance(self, user: UserConfig) -> float:
        return user.tolerance_kg if user.tolerance_kg is not None else self.cfg.tolerance_kg

    def assign(self, weight: float, at: datetime) -> Decision:
        allowed = [u for u in self.users if _in_limits(u, weight)]
        with_base, without_base = [], []
        for u in allowed:
            base = self.state.baselines.get(u.name)
            if base is None:
                without_base.append(u)
            elif abs(weight - base.weight_kg) <= self.tolerance(u):
                with_base.append((abs(weight - base.weight_kg), u, base))

        if with_base:
            _, user, base = min(with_base, key=lambda t: t[0])
            return self._accept(user, weight, at, "matched", base.weight_kg)
        if len(without_base) == 1:
            return self._accept(without_base[0], weight, at, "first", None)
        if len(without_base) > 1:
            return Decision(None, "ambiguous")

        if self.cfg.confirm_after and len(allowed) == 1:
            user = allowed[0]
            window = timedelta(hours=self.cfg.confirm_window_hours)
            similar = [
                s
                for s in self.state.pending
                if at - s.at <= window and abs(s.weight_kg - weight) <= self.tolerance(user)
            ]
            if len(similar) + 1 >= self.cfg.confirm_after:
                old = self.state.baselines[user.name].weight_kg
                return self._accept(user, weight, at, "confirmed", old)

        self._remember(weight, at)
        return Decision(None, "rejected", self._closest_baseline(weight))

    def _accept(
        self, user: UserConfig, weight: float, at: datetime, reason: Reason, base: float | None
    ) -> Decision:
        self.state.baselines[user.name] = Sample(weight, at)
        tol = self.tolerance(user)
        self.state.pending = [s for s in self.state.pending if abs(s.weight_kg - weight) > tol]
        return Decision(user.name, reason, base)

    def _remember(self, weight: float, at: datetime) -> None:
        window = timedelta(hours=self.cfg.confirm_window_hours)
        self.state.pending = [s for s in self.state.pending if at - s.at <= window]
        self.state.pending.append(Sample(weight, at))

    def _closest_baseline(self, weight: float) -> float | None:
        bases = [b.weight_kg for b in self.state.baselines.values()]
        return min(bases, key=lambda b: abs(b - weight)) if bases else None


def _in_limits(user: UserConfig, weight: float) -> bool:
    if user.min_weight_kg is not None and weight < user.min_weight_kg:
        return False
    return not (user.max_weight_kg is not None and weight > user.max_weight_kg)
