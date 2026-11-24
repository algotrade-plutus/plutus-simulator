"""The ASSUMED band-lock tier resolves through the fill policy floor (table 1c).

A collapse+volume>0 band bar is passed through by band_lock_decision, so the
active policy decides: soft fills at the edge, hard is INDETERMINATE (time
priority unrecoverable), probabilistic draws with its p.
"""
from datetime import datetime
from decimal import Decimal

from plutus.market.exchanges.equity import HSX_EXCHANGE
from plutus.market.protocol import (MarketState, Order, OrderType, Resolution,
                                    SessionPhase, Side)
from plutus.market.session.fills import (HardFillPolicy, ProbabilisticFillPolicy,
                                         SoftFillPolicy)
from plutus.market.session.types import (DataField, FillOutcome, MarketInterval,
                                         OrderRecord, OrderState, TimeInForce,
                                         Venue)

CEIL = Decimal("13.35")


def _order():
    return OrderRecord(
        order_id="o1", venue=Venue.HSX, state=OrderState.RESTING,
        time_in_force=TimeInForce.DAY, submitted_at=datetime(2022, 1, 4),
        updated_at=datetime(2022, 1, 4), fills=(),
        order=Order(ticker="HPG", side=Side.BUY, quantity=1000,
                    order_type=OrderType.LIMIT, limit_price=CEIL))


def _collapsed_bar():
    state = MarketState(ticker="HPG", ts=datetime(2022, 1, 4), ceiling=CEIL,
                        floor=Decimal("11.65"), last=CEIL,
                        session=SessionPhase.CONTINUOUS)
    return MarketInterval(ticker="HPG", start=datetime(2022, 1, 4),
                          end=datetime(2022, 1, 5), resolution=Resolution.DAILY,
                          state=state, open=CEIL, high=CEIL, low=CEIL,
                          close=CEIL, volume=7000)


def test_soft_fills_the_assumed_band_lock_at_the_edge():
    d = SoftFillPolicy().evaluate(_order(), _collapsed_bar(), HSX_EXCHANGE)
    assert d.outcome is FillOutcome.FILL and d.price == CEIL


def test_hard_is_indeterminate_on_the_assumed_band_lock():
    d = HardFillPolicy().evaluate(_order(), _collapsed_bar(), HSX_EXCHANGE)
    assert d.outcome is FillOutcome.INDETERMINATE
    # This is the touch/time-priority INDETERMINATE, not a participation-cap
    # (VOLUME) one: missing names FILL_UNOBSERVABLE_AT_RESOLUTION and nothing
    # else -- DataField.VOLUME (the cap's own indeterminate field) is absent.
    assert d.missing == frozenset({DataField.FILL_UNOBSERVABLE_AT_RESOLUTION})


def test_probabilistic_draws_on_the_assumed_band_lock():
    # seed positional; max_participation keyword-required; p_touch=1 always fills
    pol = ProbabilisticFillPolicy(1, max_participation=None, p_touch=Decimal("1"))
    d = pol.evaluate(_order(), _collapsed_bar(), HSX_EXCHANGE)
    assert d.outcome is FillOutcome.FILL   # grade is MODELLED
