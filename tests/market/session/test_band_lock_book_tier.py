"""Dense ask/bid book tier of band_lock_decision (rows B1-B3 / S1-S3)."""
from datetime import datetime
from decimal import Decimal

from plutus.market.protocol import (BookLevel, MarketState, Order, OrderBook,
                                    OrderType, Resolution, SessionPhase, Side)
from plutus.market.session.fills import band_lock_decision
from plutus.market.session.types import (FillOutcome, MarketInterval,
                                         OrderRecord, OrderState, TimeInForce,
                                         Venue)

CEIL = Decimal("13.35")
FLOOR = Decimal("11.65")


def _order(side, price):
    return OrderRecord(
        order_id="o1", venue=Venue.HSX, state=OrderState.RESTING,
        time_in_force=TimeInForce.DAY, submitted_at=datetime(2022, 11, 16),
        updated_at=datetime(2022, 11, 16), fills=(),
        order=Order(ticker="HPG", side=side, quantity=1000,
                    order_type=OrderType.LIMIT, limit_price=price))


def _interval(*, asks=(), bids=(), volume=None):
    book = OrderBook(asks=tuple(BookLevel(price=p) for p in asks),
                     bids=tuple(BookLevel(price=p) for p in bids),
                     as_of=datetime(2022, 11, 16))
    state = MarketState(ticker="HPG", ts=datetime(2022, 11, 16),
                        ceiling=CEIL, floor=FLOOR, last=CEIL,
                        session=SessionPhase.CONTINUOUS, book=book)
    return MarketInterval(ticker="HPG", start=datetime(2022, 11, 16),
                          end=datetime(2022, 11, 17), resolution=Resolution.TICK,
                          state=state, close=CEIL, volume=volume, book=book)


def test_b1_ask_below_ceiling_is_passthrough():
    d = band_lock_decision(_order(Side.BUY, CEIL),
                           _interval(asks=[Decimal("13.30")], volume=100))
    assert d is None


def test_b3_all_asks_at_or_above_ceiling_zero_volume_is_no_fill():
    d = band_lock_decision(_order(Side.BUY, CEIL),
                           _interval(asks=[CEIL], bids=[CEIL], volume=0))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_b3_locked_ladder_absent_volume_is_no_fill():
    # option B (2026-09-11): a locked ask ladder with no volume figure is still
    # trắng bên bán -- the empty offer side is the direct evidence.
    d = band_lock_decision(_order(Side.BUY, CEIL),
                           _interval(asks=[CEIL], bids=[CEIL], volume=None))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_b2_asks_at_ceiling_with_volume_is_passthrough_to_policy():
    d = band_lock_decision(_order(Side.BUY, CEIL),
                           _interval(asks=[CEIL], bids=[CEIL], volume=200))
    assert d is None


def test_s1_bid_above_floor_is_passthrough():
    d = band_lock_decision(_order(Side.SELL, FLOOR),
                           _interval(bids=[Decimal("11.70")], volume=100))
    assert d is None


def test_s3_all_bids_at_or_below_floor_zero_volume_is_no_fill():
    d = band_lock_decision(_order(Side.SELL, FLOOR),
                           _interval(bids=[FLOOR], asks=[FLOOR], volume=0))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_s3_locked_ladder_absent_volume_is_no_fill():
    # option B (2026-09-11): a locked bid ladder with no volume figure is still
    # trắng bên mua -- the empty bid side is the direct evidence.
    d = band_lock_decision(_order(Side.SELL, FLOOR),
                           _interval(bids=[FLOOR], asks=[FLOOR], volume=None))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_s2_bids_at_floor_with_volume_is_passthrough_to_policy():
    d = band_lock_decision(_order(Side.SELL, FLOOR),
                           _interval(bids=[FLOOR], asks=[FLOOR], volume=200))
    assert d is None


def test_book_tier_engages_via_interval_state_book_fallback():
    # Every other test in this file passes the same book to both
    # MarketInterval(book=...) and MarketState(book=...), so interval.book is
    # never None and band_lock_decision's `else interval.state.book` fallback
    # never runs. Here interval.book IS None; only state.book carries the
    # locked ladder, so this only passes if the fallback actually fires.
    book = OrderBook(asks=(BookLevel(price=CEIL),), bids=(BookLevel(price=CEIL),),
                     as_of=datetime(2022, 11, 16))
    state = MarketState(ticker="HPG", ts=datetime(2022, 11, 16),
                        ceiling=CEIL, floor=FLOOR, last=CEIL,
                        session=SessionPhase.CONTINUOUS, book=book)
    interval = MarketInterval(ticker="HPG", start=datetime(2022, 11, 16),
                              end=datetime(2022, 11, 17),
                              resolution=Resolution.TICK, state=state,
                              close=CEIL, volume=None, book=None)
    assert interval.book is None  # the condition this test exists to exercise

    d = band_lock_decision(_order(Side.BUY, CEIL), interval)
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason
