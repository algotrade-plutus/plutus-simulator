"""Unit tests for `band_lock_decision`: BAND_LOCK as a fill-path decision.

Task 1 of the BAND_LOCK admission -> fill migration. This is the *only*
consumer of the function today -- no policy calls it yet (that is later
tasks). The four cases mirror `book_walk.py`'s `_lock_refusal`, which this
function ports: same side test, same marketability test, same
UNKNOWN -> INDETERMINATE / known -> NO_FILL split, read off
`interval.state.{locked_side, ceiling, floor, lock_evidence}`.
"""

from datetime import datetime
from decimal import Decimal

from plutus.market.protocol import (LockEvidence, MarketState, Order,
                                    OrderType, Resolution, Side)
from plutus.market.session.fills import band_lock_decision
from plutus.market.session.types import (FillOutcome, MarketInterval,
                                         OrderRecord, OrderState,
                                         TimeInForce, Venue)


def _order(side, price):
    return OrderRecord(
        order_id="o1", venue=Venue.HSX, state=OrderState.RESTING,
        time_in_force=TimeInForce.DAY, submitted_at=datetime(2022, 11, 16),
        updated_at=datetime(2022, 11, 16), fills=(),
        order=Order(ticker="HPG", side=side, quantity=1000,
                    order_type=OrderType.LIMIT, limit_price=price))


def _interval(*, locked_side, ceiling, floor, evidence):
    state = MarketState(ticker="HPG", ts=datetime(2022, 11, 16),
                        ceiling=ceiling, floor=floor, last=ceiling,
                        locked_side=locked_side, lock_evidence=evidence)
    return MarketInterval(ticker="HPG", start=datetime(2022, 11, 16),
                          end=datetime(2022, 11, 17), resolution=Resolution.DAILY,
                          state=state, close=ceiling)


def test_buy_into_known_ceiling_lock_is_no_fill():
    d = band_lock_decision(
        _order(Side.BUY, Decimal("13.35")),
        _interval(locked_side=Side.BUY, ceiling=Decimal("13.35"),
                  floor=Decimal("11.65"), evidence=LockEvidence.BAR_PROXY))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_sell_into_known_floor_lock_is_no_fill():
    d = band_lock_decision(
        _order(Side.SELL, Decimal("11.65")),
        _interval(locked_side=Side.SELL, ceiling=Decimal("13.35"),
                  floor=Decimal("11.65"), evidence=LockEvidence.BAR_PROXY))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_tick_book_evidence_is_honoured_the_same_way():
    d = band_lock_decision(
        _order(Side.BUY, Decimal("13.35")),
        _interval(locked_side=Side.BUY, ceiling=Decimal("13.35"),
                  floor=Decimal("11.65"), evidence=LockEvidence.TICK_BOOK))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason
    assert "tick_book" in d.reason


def test_unknown_lock_evidence_is_indeterminate():
    d = band_lock_decision(
        _order(Side.BUY, Decimal("13.35")),
        _interval(locked_side=Side.BUY, ceiling=Decimal("13.35"),
                  floor=Decimal("11.65"), evidence=LockEvidence.UNKNOWN))
    assert d is not None and d.outcome is FillOutcome.INDETERMINATE


def test_unlocked_side_returns_none():
    # a SELL on a buy-locked (limit-up) day is fillable -- not our concern
    d = band_lock_decision(
        _order(Side.SELL, Decimal("13.35")),
        _interval(locked_side=Side.BUY, ceiling=Decimal("13.35"),
                  floor=Decimal("11.65"), evidence=LockEvidence.BAR_PROXY))
    assert d is None


def test_limit_below_ceiling_not_marketable_returns_none():
    d = band_lock_decision(
        _order(Side.BUY, Decimal("13.00")),   # below the cap, not crossing the lock
        _interval(locked_side=Side.BUY, ceiling=Decimal("13.35"),
                  floor=Decimal("11.65"), evidence=LockEvidence.BAR_PROXY))
    assert d is None
