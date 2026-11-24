"""Unit tests for `band_lock_decision`: the phase-aware daily evidence ladder.

`band_lock_decision` (session/fills.py) is the shared, override-only band-lock
rule every fill policy applies via `BaseFillPolicy._dispatch`. It is a pure
function of (order, interval): it returns `None` to defer to the ordinary fill
path, a definite `NO_FILL` on a proven full lock with zero volume, or an
`INDETERMINATE` where the marketable-into-the-edge order's fate cannot be
established. It never returns a FILL -- a fill is sized by the policy.

Rows below are the daily OHLC+volume tier of the design's ladder
(docs/superpowers/specs/2026-09-10-band-lock-fillability-design.md, tables 1a/1b):
B4/S4 traded-through -> passthrough; B5/S5 collapse+vol==0-or-absent ->
NO_FILL (the corpus never stores a literal 0, so an absent row proves the
no-trade fact just as zero would -- owner decision 2026-09-11); B6/S6
collapse+vol>0 -> passthrough (the policy floor decides); B7/S7 no OHLC signal
at all -> INDETERMINATE; plus the phase instant (continuous low/high, ATO
open, ATC close) and the not-applicable (unmarketable / no band) cases.
"""

from datetime import datetime
from decimal import Decimal

from plutus.market.protocol import (MarketState, Order, OrderType, Resolution,
                                    SessionPhase, Side)
from plutus.market.session.fills import band_lock_decision
from plutus.market.session.types import (DataField, FillOutcome,
                                         MarketInterval, OrderRecord,
                                         OrderState, TimeInForce, Venue)

CEIL = Decimal("13.35")
FLOOR = Decimal("11.65")


def _order(side, price, order_type=OrderType.LIMIT):
    return OrderRecord(
        order_id="o1", venue=Venue.HSX, state=OrderState.RESTING,
        time_in_force=(TimeInForce.AUCTION_ONLY
                       if order_type in (OrderType.AT_THE_OPENING,
                                         OrderType.AT_THE_CLOSE)
                       else TimeInForce.DAY),
        submitted_at=datetime(2022, 11, 16),
        updated_at=datetime(2022, 11, 16), fills=(),
        order=Order(ticker="HPG", side=side, quantity=1000,
                    order_type=order_type, limit_price=price))


def _interval(*, phase=SessionPhase.CONTINUOUS, ceiling=CEIL, floor=FLOOR,
              open=None, high=None, low=None, close=None, volume=None,
              missing=()):
    state = MarketState(ticker="HPG", ts=datetime(2022, 11, 16),
                        ceiling=ceiling, floor=floor, last=close,
                        session=phase)
    miss = set(missing)
    if volume is None:
        miss.add(DataField.VOLUME)
    return MarketInterval(
        ticker="HPG", start=datetime(2022, 11, 16),
        end=datetime(2022, 11, 17), resolution=Resolution.DAILY, state=state,
        open=open, high=high, low=low, close=close, volume=volume,
        missing=frozenset(miss))


# ---- BUY into the ceiling (limit-up), continuous ----------------------------

def test_b4_buy_traded_below_cap_is_passthrough():
    # session low is under the cap: a buyer could obtain shares -> ordinary path
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(high=CEIL, low=Decimal("13.00"), close=CEIL, volume=5000))
    assert d is None


def test_b5_buy_full_collapse_zero_volume_is_no_fill():
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(high=CEIL, low=CEIL, close=CEIL, volume=0))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_b6_buy_collapse_with_volume_is_passthrough_to_policy():
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(high=CEIL, low=CEIL, close=CEIL, volume=7000))
    assert d is None


def test_collapse_volume_absent_is_no_fill():
    # The corpus never records a literal volume==0 -- "nothing traded" is an
    # absent row (volume=None). A bar collapsed on the edge with volume absent
    # is therefore the same trắng-bên-bán proof as B5, not a volume-unknown
    # INDETERMINATE (owner decision 2026-09-11).
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(high=CEIL, low=CEIL, close=CEIL, volume=None))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_b7_buy_no_low_signal_is_indeterminate():
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(high=None, low=None, close=CEIL, volume=0,
                  missing={DataField.LOW, DataField.HIGH, DataField.OPEN}))
    assert d is not None and d.outcome is FillOutcome.INDETERMINATE
    assert "BAND_LOCK" in d.reason


def test_buy_no_low_but_close_below_cap_is_passthrough():
    # The low is absent, but a trade strictly below the ceiling is on record
    # (low <= close < ceiling), so the session left the edge: traded through.
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(high=None, low=None, close=Decimal("13.00"), volume=None,
                  missing={DataField.LOW, DataField.HIGH, DataField.OPEN}))
    assert d is None


def test_sell_no_high_but_close_above_floor_is_passthrough():
    # The daily-mark-only shape (no OHLC extreme, no book, no volume) a forced
    # close at the floor meets: close > floor proves high > floor.
    d = band_lock_decision(
        _order(Side.SELL, FLOOR),
        _interval(high=None, low=None, close=Decimal("12.00"), volume=None,
                  missing={DataField.LOW, DataField.HIGH, DataField.OPEN}))
    assert d is None


def test_sell_no_high_close_on_floor_is_indeterminate():
    # SELL mirror of B7: a close on the edge says nothing about the high.
    d = band_lock_decision(
        _order(Side.SELL, FLOOR),
        _interval(high=None, low=None, close=FLOOR, volume=0,
                  missing={DataField.LOW, DataField.HIGH, DataField.OPEN}))
    assert d is not None and d.outcome is FillOutcome.INDETERMINATE


# ---- SELL into the floor (limit-down), continuous ---------------------------

def test_s4_sell_traded_above_floor_is_passthrough():
    d = band_lock_decision(
        _order(Side.SELL, FLOOR),
        _interval(high=Decimal("12.00"), low=FLOOR, close=FLOOR, volume=5000))
    assert d is None


def test_s5_sell_full_collapse_zero_volume_is_no_fill():
    d = band_lock_decision(
        _order(Side.SELL, FLOOR),
        _interval(high=FLOOR, low=FLOOR, close=FLOOR, volume=0))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_s6_sell_collapse_with_volume_is_passthrough_to_policy():
    d = band_lock_decision(
        _order(Side.SELL, FLOOR),
        _interval(high=FLOOR, low=FLOOR, close=FLOOR, volume=7000))
    assert d is None


def test_collapse_volume_absent_is_no_fill_sell():
    # SELL-side mirror of test_collapse_volume_absent_is_no_fill: a collapsed
    # floor bar with volume absent is the same trắng-bên-mua proof as S5, not
    # a volume-unknown INDETERMINATE (owner decision 2026-09-11).
    d = band_lock_decision(
        _order(Side.SELL, FLOOR),
        _interval(high=FLOOR, low=FLOOR, close=FLOOR, volume=None))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


# ---- phase: ATO tests the open, ATC tests the close (Case D) -----------------

def test_ato_buy_opened_locked_then_fell_is_no_fill_for_the_ato():
    # opened at the ceiling with no opening trade, even though it later fell:
    # the ATO only saw the opening auction.
    d = band_lock_decision(
        _order(Side.BUY, None, order_type=OrderType.AT_THE_OPENING),
        _interval(phase=SessionPhase.OPENING_AUCTION,
                  open=CEIL, high=CEIL, low=Decimal("13.00"),
                  close=Decimal("13.10"), volume=0))
    assert d is not None and d.outcome is FillOutcome.NO_FILL


def test_ato_buy_opened_below_cap_is_passthrough():
    d = band_lock_decision(
        _order(Side.BUY, None, order_type=OrderType.AT_THE_OPENING),
        _interval(phase=SessionPhase.OPENING_AUCTION,
                  open=Decimal("13.00"), high=CEIL, low=Decimal("13.00"),
                  close=CEIL, volume=5000))
    assert d is None


def test_atc_buy_closed_locked_zero_volume_is_no_fill():
    d = band_lock_decision(
        _order(Side.BUY, None, order_type=OrderType.AT_THE_CLOSE),
        _interval(phase=SessionPhase.CLOSING_AUCTION,
                  open=Decimal("13.00"), high=CEIL, low=Decimal("13.00"),
                  close=CEIL, volume=0))
    assert d is not None and d.outcome is FillOutcome.NO_FILL


# ---- not applicable: unmarketable / wrong-way / no band ---------------------

def test_limit_below_ceiling_is_not_marketable_returns_none():
    d = band_lock_decision(
        _order(Side.BUY, Decimal("13.00")),
        _interval(high=CEIL, low=CEIL, close=CEIL, volume=0))
    assert d is None


def test_sell_on_a_limit_up_day_is_not_a_lock_question_returns_none():
    # a SELL when only the ceiling is pinned (floor untouched) -> ordinary path
    d = band_lock_decision(
        _order(Side.SELL, FLOOR),
        _interval(high=CEIL, low=Decimal("13.00"), close=CEIL, volume=5000))
    assert d is None


def test_no_ceiling_band_returns_none():
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(ceiling=None, high=CEIL, low=CEIL, close=CEIL, volume=0))
    assert d is None
