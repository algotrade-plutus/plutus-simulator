"""Settlement properties: unsettled cash and shares are never spendable early.

Judged through ``ExchangeSession`` -- ``submit``, ``advance_to``, ``holdings``,
``cash`` -- with the settlement instant written from the rulebook, not read
from the engine:

* from 2022-08-29 (VSD QD 109 Art. 4): **13:00 on T+2**;
* before it (VSD QD 211, T+2 completing after the close): the **open of T+3**,
  09:00 on HOSE.

The probe instant is drawn from every continuous-session time between the fill
and that settlement instant, so "early" covers the trade day itself, T+1, and
T+2's morning.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from hypothesis import example, given, settings
from hypothesis import strategies as st

from plutus.core.order import Side
from plutus.market.session import Accepted, Rejected, StatefulRule

from ._harness import (COVERAGE_END, COVERAGE_START, SETTLEMENT_1300_FROM,
                       at, limit, session, state)

D = Decimal
TICKER = 'FPT'

#: Continuous-session clock times on HOSE that are inside both the pre- and
#: post-2021-07-05 schedules.
PROBE_TIMES = (time(9, 30), time(10, 0), time(11, 0), time(13, 15),
               time(14, 10))


def add_weekdays(day: date, n: int) -> date:
    while n:
        day += timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


def oracle_settles_at(trade: date) -> datetime:
    if trade >= SETTLEMENT_1300_FROM:
        return datetime.combine(add_weekdays(trade, 2), time(13, 0))
    return datetime.combine(add_weekdays(trade, 3), time(9, 0))


def early_probes(trade: date):
    """Every probe instant after the 14:00 fill and before settlement."""
    fill = at(trade, 14, 0)
    settles = oracle_settles_at(trade)
    out = []
    day = trade
    while day <= settles.date():
        if day.weekday() < 5:
            for clock in PROBE_TIMES:
                ts = datetime.combine(day, clock)
                if fill < ts < settles:
                    out.append(ts)
        day += timedelta(days=1)
    return out


TRADE_DAYS = st.dates(min_value=COVERAGE_START,
                      max_value=COVERAGE_END - timedelta(days=10)).filter(
    lambda d: d.weekday() < 5)
PRICES = st.integers(min_value=100, max_value=1_000).map(lambda n: D(n) / 10)
LOTS = st.integers(min_value=1, max_value=50).map(lambda n: n * 100)
#: The sale is at least two lots, so half of it (rounded down to a lot) is
#: a buy the net proceeds can fund once they settle.
SALES = st.integers(min_value=2, max_value=50).map(lambda n: n * 100)


def rows_from(trade: date, price: Decimal):
    return {(TICKER, trade + timedelta(days=i)):
            state(TICKER, trade + timedelta(days=i), price)
            for i in range(8)}


@settings(max_examples=250, deadline=None)
@given(trade=TRADE_DAYS, price=PRICES, qty=LOTS, data=st.data())
@example(trade=date(2022, 8, 26), price=D('45.5'), qty=1000, data=None)
@example(trade=date(2022, 8, 29), price=D('45.5'), qty=1000, data=None)
def test_bought_shares_are_not_sellable_before_settlement(trade, price, qty,
                                                          data):
    """At any instant before settlement the bought shares cannot be sold;
    at the settlement instant they can, in full."""
    probes = early_probes(trade)
    probe = probes[0] if data is None else data.draw(st.sampled_from(probes))
    s = session(rows_from(trade, price), trade, cash=10**12)
    s.advance_to(at(trade, 10))
    assert isinstance(s.submit(limit(TICKER, Side.BUY, qty, price)), Accepted)
    s.advance_to(at(trade, 14))
    assert s.holdings(TICKER).unsettled_quantity == qty

    s.advance_to(probe)
    assert s.holdings(TICKER).sellable == 0
    ack = s.submit(limit(TICKER, Side.SELL, qty, price))
    assert isinstance(ack, Rejected), (probe, ack)
    assert ack.rule is StatefulRule.UNSETTLED_HOLDING
    assert ack.sellable_from >= oracle_settles_at(trade)

    s.advance_to(oracle_settles_at(trade))
    assert s.holdings(TICKER).sellable == qty
    assert isinstance(s.submit(limit(TICKER, Side.SELL, qty, price)),
                      Accepted)


@settings(max_examples=250, deadline=None)
@given(trade=TRADE_DAYS, price=PRICES, qty=SALES, data=st.data())
@example(trade=date(2022, 8, 26), price=D('45.5'), qty=1000, data=None)
@example(trade=date(2022, 8, 29), price=D('45.5'), qty=1000, data=None)
def test_sale_proceeds_are_not_spendable_before_settlement(trade, price, qty,
                                                           data):
    """An account with no cash sells settled shares: the proceeds are pending
    until settlement, ``Cash.available`` stays zero, and a buy they would fund
    is refused ``INSUFFICIENT_CASH``; at the settlement instant the same buy
    -- half the shares sold, so the net proceeds cover it -- is funded.

    Advance on sale is off (the default ``BrokerTerms``), so this is the
    exchange rule, not a broker loan.
    """
    probes = early_probes(trade)
    probe = probes[-1] if data is None else data.draw(st.sampled_from(probes))
    s = session(rows_from(trade, price), trade, cash=0,
                holdings={TICKER: qty})
    s.advance_to(at(trade, 10))
    assert isinstance(s.submit(limit(TICKER, Side.SELL, qty, price)),
                      Accepted)
    s.advance_to(at(trade, 14))
    proceeds = s.cash().pending_total
    assert proceeds > 0

    s.advance_to(probe)
    assert s.cash().available == 0
    buy = limit(TICKER, Side.BUY, (qty // 200) * 100, price)
    ack = s.submit(buy)
    assert isinstance(ack, Rejected), (probe, ack)
    assert ack.rule is StatefulRule.INSUFFICIENT_CASH

    s.advance_to(oracle_settles_at(trade))
    assert s.cash().available == proceeds
    assert isinstance(s.submit(buy), Accepted)
