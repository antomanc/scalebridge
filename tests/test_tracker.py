from datetime import timedelta

from scalebridge.tracker import SessionTracker

from .conftest import T0, reading


def feed_all(tracker, readings):
    out = []
    for r in readings:
        out += tracker.feed(r)
    return out


def test_one_result_per_weigh_in_despite_repeats():
    t = SessionTracker()
    out = feed_all(
        t,
        [
            reading(74.85, 0, stable=False),
            reading(75.10, 2),
            reading(75.10, 3),
            reading(75.10, 5, removed=True),
            *(reading(75.10, 10 + s, removed=True) for s in range(0, 300, 5)),
        ],
    )
    assert [r.weight_kg for r in out] == [75.10]


def test_stepping_on_again_starts_a_new_weigh_in():
    t = SessionTracker()
    first = feed_all(t, [reading(75.1, 0), reading(75.1, 5, removed=True)])
    second = feed_all(t, [reading(35.0, 60, stable=False), reading(75.1, 62)])
    assert len(first) == 1 and len(second) == 1


def test_repeat_window_expires():
    t = SessionTracker(repeat_window=timedelta(minutes=10))
    assert t.feed(reading(75.1, 0))
    assert not t.feed(reading(75.1, 60))
    assert t.feed(reading(75.1, 60 + 11 * 60))


def test_waits_for_impedance_then_closes():
    t = SessionTracker(settle=timedelta(seconds=10))
    assert not t.feed(reading(70.0, 0, complete=False))
    [r] = t.feed(reading(70.0, 3, impedance=500))
    assert r.impedance_ohm == 500


def test_settle_timeout_closes_without_impedance():
    t = SessionTracker(settle=timedelta(seconds=10))
    assert not t.feed(reading(70.0, 0, complete=False))
    assert not t.tick(T0 + timedelta(seconds=5))
    [r] = t.tick(T0 + timedelta(seconds=10))
    assert r.weight_kg == 70.0 and r.impedance_ohm is None


def test_flicker_around_reported_weight_is_not_a_new_weigh_in():
    t = SessionTracker()
    out = feed_all(t, [reading(75.1, 0), reading(75.0, 1, stable=False), reading(75.1, 2)])
    assert len(out) == 1


def test_leftover_result_after_restart_is_ignored():
    t = SessionTracker()
    out = feed_all(t, [reading(75.1, s, removed=True) for s in range(0, 120, 5)])
    assert out == []
    # ...but the next real weigh-in still comes through.
    assert feed_all(t, [reading(30.0, 200, stable=False), reading(69.5, 202)])


def test_weigh_in_whose_stable_readings_were_missed_is_still_reported():
    # BlueZ can drop the few "stable, still on the scale" advertisements. The scale then
    # only shows the result after you step off, right after we saw it settling.
    t = SessionTracker()
    out = feed_all(
        t,
        [
            reading(40.2, 0, stable=False),
            reading(68.9, 2, stable=False),
            reading(0.1, 6, stable=False, removed=True),
            *(reading(69.1, 7 + s, removed=True) for s in range(0, 120, 5)),
        ],
    )
    assert [r.weight_kg for r in out] == [69.1]


def test_leftover_long_after_settling_is_still_ignored():
    t = SessionTracker()
    out = feed_all(t, [reading(68.9, 0, stable=False), reading(69.1, 600, removed=True)])
    assert out == []


def test_empty_scale_after_stepping_off_does_not_start_a_new_weigh_in():
    t = SessionTracker()
    out = feed_all(
        t,
        [
            reading(68.9, 0, stable=False),
            reading(69.1, 2),
            reading(0.1, 4, stable=False, removed=True),
            reading(69.1, 5, removed=True),
            reading(0.1, 6, stable=False, removed=True),
            reading(69.1, 7, removed=True),
        ],
    )
    assert [r.weight_kg for r in out] == [69.1]


# Scales that report their own clock (Mi Scale 2): it is fixed while the scale repeats a
# result, and changes with a new measurement and again when the person steps off.


def test_clock_repeats_of_one_weigh_in_are_reported_once():
    t = SessionTracker()
    out = feed_all(
        t,
        [
            reading(70.6, 0, stable=False, clock=10),
            reading(70.6, 2, clock=10),
            reading(70.6, 3, clock=10),
            *(reading(70.6, 4 + s, removed=True, clock=14) for s in range(0, 450, 5)),
        ],
    )
    assert [r.weight_kg for r in out] == [70.6]


def test_clock_weighing_again_at_the_same_weight_is_a_new_weigh_in():
    t = SessionTracker()
    first = feed_all(t, [reading(70.6, 0, clock=10), reading(70.6, 3, removed=True, clock=14)])
    again = feed_all(
        t, [reading(70.6, 470, clock=480), reading(70.6, 473, removed=True, clock=484)]
    )
    assert len(first) == 1 and len(again) == 1


def test_clock_new_result_after_stepping_off_is_reported_without_settling():
    # Yesterday's result was seen; this morning only the new result after stepping off.
    t = SessionTracker()
    assert not feed_all(t, [reading(68.75, 0, removed=True, clock=100)])
    [r] = feed_all(t, [reading(68.9, 86_400 + s, removed=True, clock=86_500) for s in range(5)])
    assert r.weight_kg == 68.9


def test_clock_result_replayed_on_waking_up_is_ignored():
    t = SessionTracker()
    assert feed_all(t, [reading(70.6, 0, clock=10)])
    assert not feed_all(t, [reading(70.6, 3, removed=True, clock=14)])
    assert not feed_all(t, [reading(70.6, 7200, removed=True, clock=14)])


def test_clock_leftover_after_restart_is_ignored():
    t = SessionTracker()
    assert not feed_all(t, [reading(70.6, s, removed=True, clock=14) for s in range(0, 60, 5)])
