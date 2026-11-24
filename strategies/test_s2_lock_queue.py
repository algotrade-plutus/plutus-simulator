"""S2 lock-queue measurement: was the broker's floor sale blocked on DIG's lock days?

The daily S2 run can only *assume* the forced sale filled on a day DIG sat at its
floor (TOUCHED_AT_LIMIT, see ``test_s2_equity_margin_momentum.py``): a daily bar
cannot see the sell queue. This test reads the queue itself, from a minimal book
slice, through ``measurements/s2_lock_queue.py``, and pins what it shows.

A sale at the floor submitted at S2's 10:00 decision mark joins the back of the
floor queue. Under price-time priority it fills only if the volume traded at
the floor afterwards (closing auction included) exceeds the queue ahead of it.

Data: ``strategies/fixtures/s2_lock/`` (DIG, Algotrade Vietnam market dataset;
see the DATA-MANIFEST.md files there).
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "s2_lock_queue", _REPO / "measurements" / "s2_lock_queue.py")
lq = importlib.util.module_from_spec(_spec)
sys.modules["s2_lock_queue"] = lq
_spec.loader.exec_module(lq)

FIXTURE = _REPO / "strategies" / "fixtures" / "s2_lock"
START, END = date(2022, 9, 5), date(2022, 11, 15)    # S2's own window (END exclusive)


@pytest.fixture(scope="module")
def rows():
    return {r.day: r for r in lq.measure(FIXTURE / "daily", FIXTURE / "book",
                                         "DIG", START, END)}


def test_every_floor_close_day_in_s2s_window_is_measured(rows):
    days = lq.floor_close_days(FIXTURE / "daily", "DIG", START, END)
    assert [d.day for d in days] == sorted(rows)
    assert len(days) == 14
    # Only two of them were pinned at the floor all session (high == floor).
    assert [d.day for d in days if d.full_floor] == [date(2022, 11, 7),
                                                     date(2022, 11, 8)]


@pytest.mark.parametrize("day", [date(2022, 11, 7), date(2022, 11, 8)])
def test_the_floor_sale_was_blocked_on_the_full_lock_days(rows, day):
    r = rows[day]
    assert r.verdict == "blocked", r
    assert r.ask_at_floor and r.prints_only_at_floor
    # The queue ahead dwarfs everything that traded afterwards.
    assert r.queue_ahead > 10 * r.volume_after, r
    # So the sale fills only if >90% of the queue ahead cancelled first.
    assert r.cancel_share_needed > 0.9


def test_a_close_at_the_floor_is_not_a_lock_at_ten(rows):
    # 2022-10-24 closed at its floor but at 10:00 the best ask was above it.
    r = rows[date(2022, 10, 24)]
    assert r.verdict == "not locked"
    assert not r.ask_at_floor


def test_a_floor_queue_that_the_tape_clears_is_not_called_blocked(rows):
    # 2022-10-25: offers sat at the floor at 10:00, but far more traded
    # afterwards than was queued ahead -- the sale could have filled.
    r = rows[date(2022, 10, 25)]
    assert r.ask_at_floor
    assert r.volume_after > r.queue_ahead
    assert r.verdict != "blocked"


def test_the_book_request_covers_only_the_floor_close_days():
    days = lq.floor_close_days(FIXTURE / "daily", "DIG", START, END)
    req = lq.book_request(days, "DIG")
    for f in req["files"]:
        spans = f["tickers"]["DIG"]
        assert len(spans) == len(days), f["file"]
        assert all(len(s) == 2 for s in spans)
