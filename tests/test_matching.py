from datetime import timedelta

from scalebridge.config import MatchingConfig, UserConfig
from scalebridge.matching import Matcher
from scalebridge.state import Sample, State

from .conftest import T0

SINKS = [{"type": "jsonl"}]


def user(name, **kw):
    return UserConfig(name=name, sinks=SINKS, **kw)


def matcher(tmp_path, users, baselines=None, **cfg):
    state = State(tmp_path / "state.json", baselines=baselines or {})
    return Matcher(users, MatchingConfig(**cfg), state)


def at(hours):
    return T0 + timedelta(hours=hours)


def test_single_user_first_reading_sets_baseline(tmp_path):
    m = matcher(tmp_path, [user("a")])
    d = m.assign(70.0, at(0))
    assert (d.user, d.reason) == ("a", "first")
    assert m.state.baselines["a"].weight_kg == 70.0


def test_within_tolerance_is_accepted_and_moves_baseline(tmp_path):
    m = matcher(tmp_path, [user("a")], {"a": Sample(70.0, at(0))})
    assert m.assign(72.5, at(24)).user == "a"
    assert m.assign(74.9, at(48)).user == "a"


def test_far_reading_is_rejected_then_confirmed(tmp_path):
    m = matcher(tmp_path, [user("a")], {"a": Sample(70.0, at(0))}, confirm_after=2)
    d = m.assign(45.0, at(1))
    assert (d.user, d.reason, d.baseline_kg) == (None, "rejected", 70.0)
    d = m.assign(45.4, at(2))
    assert (d.user, d.reason) == ("a", "confirmed")
    assert m.state.pending == []


def test_confirmation_needs_readings_inside_window(tmp_path):
    m = matcher(tmp_path, [user("a")], {"a": Sample(70.0, at(0))}, confirm_window_hours=24)
    assert m.assign(60.0, at(1)).user is None
    assert m.assign(60.0, at(30)).user is None  # first one expired
    assert m.assign(60.0, at(31)).user == "a"


def test_confirmation_disabled(tmp_path):
    m = matcher(tmp_path, [user("a")], {"a": Sample(70.0, at(0))}, confirm_after=0)
    for h in range(5):
        assert m.assign(60.0, at(h)).user is None


def test_two_users_closest_baseline_wins(tmp_path):
    bases = {"a": Sample(70.0, at(0)), "b": Sample(73.0, at(0))}
    m = matcher(tmp_path, [user("a"), user("b")], bases)
    assert m.assign(71.0, at(1)).user == "a"
    assert m.assign(72.8, at(2)).user == "b"


def test_two_users_no_auto_confirm(tmp_path):
    bases = {"a": Sample(70.0, at(0)), "b": Sample(90.0, at(0))}
    m = matcher(tmp_path, [user("a"), user("b")], bases)
    assert m.assign(50.0, at(1)).user is None
    assert m.assign(50.0, at(2)).user is None


def test_limits_disambiguate_users_without_baselines(tmp_path):
    users = [user("kid", max_weight_kg=40), user("adult", min_weight_kg=40)]
    m = matcher(tmp_path, users)
    assert m.assign(25.0, at(0)).user == "kid"
    assert m.assign(80.0, at(0)).user == "adult"


def test_ambiguous_without_baselines_or_limits(tmp_path):
    m = matcher(tmp_path, [user("a"), user("b")])
    assert m.assign(70.0, at(0)).reason == "ambiguous"


def test_per_user_tolerance(tmp_path):
    m = matcher(tmp_path, [user("a", tolerance_kg=1)], {"a": Sample(70.0, at(0))})
    assert m.assign(71.5, at(1)).user is None
