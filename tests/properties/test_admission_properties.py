"""Admission properties: tick grid, band edges, HOSE round lot (T8.2).

Each property is stated against an oracle written from the rulebook document
(``_harness.py``), and judged through ``ExchangeSession.submit`` -- the public
entry point -- on a session standing at a generated, dated instant. Hypothesis
draws the instant, the venue and the price; the explicit ``@example`` rows pin
the boundaries a random draw would rarely hit (the 10.00 and 50.00 HOSE tier
breaks, the 2021-01-04 lot change, the first day each widened band is in force).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from plutus.core.order import Side
from plutus.market.session import Accepted, Rejected
from plutus.market.session.rulebook import Rulebook, UnresolvedRule
from plutus.market.session.types import Venue
from plutus.market.verdicts import AdmissionRule, Verdict

from ._harness import (COVERAGE_END, COVERAGE_START, HSX_LOT_CHANGE, TICKER,
                       TICK_REVISION_2016, WIDENED, at, band_edges, limit,
                       next_down, next_up, on_grid, oracle_band, oracle_lot,
                       session, state, weekday_on_or_after)

D = Decimal
BOOK = Rulebook()

VENUES = st.sampled_from(['HSX', 'HNX', 'UPCOM'])


def dates(start: date, end: date):
    """Weekdays in ``[start, end]`` (a weekend draw moves back to Friday;
    every ``start`` used here is a weekday)."""
    assert start.weekday() < 5
    return st.dates(min_value=start, max_value=end).map(
        lambda d: d - timedelta(days=max(0, d.weekday() - 4)))


#: Prices in thousand VND at 1d resolution -- a tenth of the finest matched
#: tick, so most draws are off-grid -- mixed with 100d multiples, which are on
#: every venue's grid, so both sides of the iff are hit often.
PRICES = st.one_of(
    st.integers(min_value=1_000, max_value=150_000).map(lambda n: D(n) / 1000),
    st.integers(min_value=10, max_value=1_500).map(lambda n: D(n) / 10))


def submit_once(venue, day, price, *, qty=100, ceiling=None, floor=None,
                reference=None):
    ticker = TICKER[venue]
    rows = {(ticker, day): state(ticker, day,
                                 reference if reference is not None else price,
                                 ceiling=ceiling, floor=floor)}
    s = session(rows, day)
    s.advance_to(at(day))
    return s.submit(limit(ticker, Side.BUY, qty, price))


# --------------------------------------------------------------------------
# Tick grid
# --------------------------------------------------------------------------

@settings(max_examples=500, deadline=None)
@given(venue=VENUES, day=dates(COVERAGE_START, COVERAGE_END), price=PRICES)
@example(venue='HSX', day=date(2020, 1, 2), price=D('9.99'))
@example(venue='HSX', day=date(2020, 1, 2), price=D('10.00'))
@example(venue='HSX', day=date(2020, 1, 2), price=D('10.01'))
@example(venue='HSX', day=date(2021, 7, 5), price=D('49.95'))
@example(venue='HSX', day=date(2021, 7, 5), price=D('50.05'))
@example(venue='HSX', day=date(2025, 5, 5), price=D('50.00'))
@example(venue='HNX', day=date(2022, 3, 31), price=D('10.05'))
def test_admitted_iff_on_the_dated_grid(venue, day, price):
    """Inside the rulebook window: admitted <=> on the venue's dated grid.

    Lot (100) and band (unbinding) are held fixed so the grid is the only rule
    that can speak; a refusal must name ``TICK_GRID`` and the tick that bound.
    """
    ack = submit_once(venue, day, price)
    if on_grid(venue, price):
        assert isinstance(ack, Accepted), ack
    else:
        assert isinstance(ack, Rejected), ack
        assert ack.rule is AdmissionRule.TICK_GRID
        assert ack.verdict is Verdict.REJECTED
        assert price % ack.binding_constraint != 0


@settings(max_examples=100, deadline=None)
@given(day=st.one_of(
           dates(date(2012, 1, 2), TICK_REVISION_2016 - timedelta(days=1)),
           dates(TICK_REVISION_2016, COVERAGE_START - timedelta(days=1))),
       venue=VENUES, price=PRICES)
@example(day=date(2016, 9, 9), venue='HSX', price=D('45.55'))
@example(day=date(2016, 9, 12), venue='HSX', price=D('45.55'))
@example(day=date(2016, 9, 12), venue='HSX', price=D('45.53'))
def test_before_the_window_nothing_is_admitted_on_either_side_of_2016_09_12(
        day, venue, price):
    """Both sides of the 2016-09-12 tick revision: **no grid is carried**.

    The rulebook starts 2020-01-01, and the pre-2016 HOSE grid was never
    sourced (``measurements/dated_rules.py``). The engine does not guess one:
    every order before the window is refused ``INDETERMINATE``, on- or
    off-grid alike, so a data gap is never reported as a market rule. This is
    the strongest grid property the engine supports on those dates -- the
    paper's "dated 2016-09-12 revision" is not an engine feature.
    """
    ack = submit_once(venue, day, price)
    assert isinstance(ack, Rejected)
    assert ack.verdict is Verdict.INDETERMINATE


# --------------------------------------------------------------------------
# Band edges
# --------------------------------------------------------------------------

REFERENCES = st.integers(min_value=2_000, max_value=120_000).map(
    lambda n: D(n) / 1000)


@settings(max_examples=300, deadline=None)
@given(venue=VENUES, day=dates(COVERAGE_START, COVERAGE_END),
       reference=REFERENCES)
@example(venue='HSX', day=date(2024, 6, 3), reference=D('46.75'))  # ceiling 50.0
@example(venue='HSX', day=date(2024, 6, 3), reference=D('10.75'))  # floor 9.99
def test_at_the_band_admitted_one_tick_beyond_refused(venue, day, reference):
    """Ceiling and floor admitted; the next grid price outward refused BAND_LIMIT.

    The published band is the oracle's (reference x (1 +/- width), truncated
    inward to the tick of the result) and the rulebook must agree on the
    width at this date.
    """
    if not on_grid(venue, reference):
        reference = next_up(venue, reference)
    width = oracle_band(venue)
    assert BOOK.at(at(day)).daily_trading_limit(Venue(venue)) == width
    ceiling, floor = band_edges(venue, reference, width)
    above, below = next_up(venue, ceiling), next_down(venue, floor)

    def go(price):
        return submit_once(venue, day, price, ceiling=ceiling, floor=floor,
                           reference=reference)

    assert isinstance(go(ceiling), Accepted)
    assert isinstance(go(floor), Accepted)
    for beyond in (above, below):
        ack = go(beyond)
        assert isinstance(ack, Rejected), (beyond, ack)
        assert ack.rule is AdmissionRule.BAND_LIMIT
        assert ack.verdict is Verdict.REJECTED


CASES = sorted(WIDENED)


@settings(max_examples=200, deadline=None)
@given(case=st.sampled_from(CASES), data=st.data(), reference=REFERENCES)
@example(case=('first_trading_day', 'HSX'), data=None,
         reference=D('20.00'))  # the first day each band is in force
def test_first_day_and_resumption_bands_admit_beyond_the_ordinary_band(
        case, data, reference):
    """The widened band: beyond the ordinary ceiling yet admitted; one tick
    beyond the widened ceiling refused.

    The engine has no security-state axis -- nothing in it decides that a
    ticker-day *is* a first day (FEATURES.md section 4,
    ``WIDENED_TRADING_LIMIT`` PARTIAL). So the exception is honoured exactly
    when the published state carries the widened band, and the rulebook must
    agree on the widened width from its in-force date.
    """
    kind, venue = case
    width, since = WIDENED[case]
    if data is None:
        day = weekday_on_or_after(since)
    else:
        day = data.draw(dates(since, COVERAGE_END), label='day')
    if not on_grid(venue, reference):
        reference = next_up(venue, reference)
    assert BOOK.at(at(day)).widened_trading_limit(Venue(venue), kind) == width

    ordinary_ceiling, ordinary_floor = band_edges(venue, reference,
                                                  oracle_band(venue))
    ceiling, floor = band_edges(venue, reference, width)

    def go(price):
        return submit_once(venue, day, price, ceiling=ceiling, floor=floor,
                           reference=reference)

    assert isinstance(go(next_up(venue, ordinary_ceiling)), Accepted)
    assert isinstance(go(next_down(venue, ordinary_floor)), Accepted)
    assert isinstance(go(ceiling), Accepted)
    assert isinstance(go(floor), Accepted)
    for beyond in (next_up(venue, ceiling), next_down(venue, floor)):
        ack = go(beyond)
        assert isinstance(ack, Rejected) and ack.rule is AdmissionRule.BAND_LIMIT


@settings(max_examples=50, deadline=None)
@given(case=st.sampled_from(CASES), data=st.data())
def test_a_widened_band_before_its_source_date_is_unknown_not_ordinary(
        case, data):
    """Before the widened band is sourced, the rulebook says UNKNOWN -- it
    does not fall back to the ordinary width (T8.1 open edge)."""
    kind, venue = case
    _, since = WIDENED[case]
    day = data.draw(dates(COVERAGE_START, since - timedelta(days=1)))
    with pytest.raises(UnresolvedRule):
        BOOK.at(at(day)).widened_trading_limit(Venue(venue), kind)


# --------------------------------------------------------------------------
# HOSE round lot, 10 -> 100 on 2021-01-04
# --------------------------------------------------------------------------

LOT_WINDOW = dates(date(2020, 1, 2), date(2022, 6, 30))


@settings(max_examples=500, deadline=None)
@given(venue=VENUES, day=LOT_WINDOW,
       qty=st.integers(min_value=1, max_value=5_000))
@example(venue='HSX', day=date(2020, 12, 31), qty=10)
@example(venue='HSX', day=date(2021, 1, 4), qty=10)
@example(venue='HSX', day=date(2021, 1, 4), qty=100)
@example(venue='HSX', day=date(2020, 12, 31), qty=110)
@example(venue='HSX', day=date(2021, 1, 4), qty=110)
@example(venue='HNX', day=date(2020, 12, 31), qty=10)
def test_round_lot_is_dated(venue, day, qty):
    """Admitted <=> quantity is a multiple of the lot in force at that date.

    HOSE: 10 before 2021-01-04, 100 from it. HNX and UPCoM: 100 throughout.
    A refusal names ``ROUND_LOT`` and the lot that bound.
    """
    lot = oracle_lot(venue, day)
    ack = submit_once(venue, day, D('20.00'), qty=qty)
    if qty % lot == 0:
        assert isinstance(ack, Accepted), ack
    else:
        assert isinstance(ack, Rejected), ack
        assert ack.rule is AdmissionRule.ROUND_LOT
        assert ack.binding_constraint == lot
